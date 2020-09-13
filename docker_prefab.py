import argparse
import collections
import datetime
import functools
import hashlib
import json
import logging
import sys
import time
import traceback
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, Union

import docker
import yaml


logger = logging.getLogger(__name__)
logger.handlers = [logging.StreamHandler()]
logger.setLevel(logging.INFO)

DEFAULT_ALLOW_PULL_ERRORS: List[str] = ["ImageNotFoundError", "ImageAccessError"]
DEFAULT_BUILD_OPTIONS: Dict[str, Any] = {
    "decode": True,
    "forcerm": True,
    "path": ".",
    "rm": True,
    "squash": True,
}
DEFAULT_CONFIG_FILE = "prefab.yml"
DEFAULT_DIGEST_LABEL = "prefab.digest"
DEFAULT_HASH_ALGORITHM = "sha256"
DEFAULT_HASH_CHUNK_SIZE = 65535
DEFAULT_SHORT_DIGEST_SIZE = 12
DEFAULT_TARGET_LABEL = "prefab.target"


class DockerPrefabError(Exception):
    pass


class HashAlgorithmNotFound(DockerPrefabError):
    pass


class ImageAccessError(DockerPrefabError):
    pass


class ImageBuildError(DockerPrefabError):
    pass


class ImageNotFoundError(DockerPrefabError):
    pass


class ImagePushError(DockerPrefabError):
    pass


class InvalidConfigError(DockerPrefabError):
    pass


class TargetTagError(DockerPrefabError):
    pass


class TargetCyclicError(DockerPrefabError):
    pass


class TargetNotFoundError(DockerPrefabError):
    pass


class TargetLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[{self.extra.get('target', '<none>')}] {msg}", kwargs


class Config(collections.UserDict):
    def __init__(self, config: Dict[str, str]) -> None:
        super().__init__(config)
        self.validate_config()

    @classmethod
    def from_yaml_filepath(cls, path: str) -> "Config":
        logger.info(f"Loading config: {path}")
        with open(path) as raw_config:
            return cls(yaml.safe_load(raw_config))

    def get_option(self, name: str, default: Any) -> Any:
        return self.data.get("options", {}).get(name, default)

    def get_target(self, target: str) -> Dict[str, Any]:
        targets = self.data.get("targets", {})

        if target not in targets:
            raise TargetNotFoundError(f"target '{target}' not found in build config")

        return targets[target]

    @property
    def allow_pull_errors(self) -> Tuple[Any, ...]:
        allow_names = self.get_option("allow_pull_errors", DEFAULT_ALLOW_PULL_ERRORS)
        symbols = globals()
        return tuple(symbols[name] for name in allow_names if name in symbols)

    @property
    def digest_label(self) -> str:
        return str(self.get_option("digest_label", DEFAULT_DIGEST_LABEL))

    @property
    def hash_algorithm(self) -> str:
        return str(self.get_option("hash_algorithm", DEFAULT_HASH_ALGORITHM))

    @property
    def hash_chunk_size(self) -> int:
        return int(self.get_option("hash_chunk_size", DEFAULT_HASH_CHUNK_SIZE))

    @property
    def short_digest_size(self) -> int:
        return int(self.get_option("short_digest_size", DEFAULT_SHORT_DIGEST_SIZE))

    @property
    def target_label(self) -> str:
        return str(self.get_option("target_label", DEFAULT_TARGET_LABEL))

    def validate_target(self, target: str) -> None:
        config = self.data["targets"][target]

        if not isinstance(config, dict):
            raise InvalidConfigError(f"{target}: dict expected for target config")

        if "dockerfile" not in config or not isinstance(config["dockerfile"], str):
            raise InvalidConfigError(f"{target}: dockerfile required in target config")

        if not isinstance(config.get("depends_on", []), list):
            raise InvalidConfigError(f"{target}: list expected for target depends_on")

        if not isinstance(config.get("watch_files", []), list):
            raise InvalidConfigError(f"{target}: list expected for target watch_files")

        if not isinstance(config.get("build_options", {}), dict):
            raise InvalidConfigError(
                f"{target}: dict expected for target build_options"
            )

    def validate_config(self) -> None:
        if "targets" not in self.data:
            raise InvalidConfigError("targets section missing")

        if not isinstance(self.data["targets"], dict):
            raise InvalidConfigError("dict expected for targets section")

        if not self.data["targets"]:
            raise InvalidConfigError("no targets defined")

        for target in self.data["targets"]:
            self.validate_target(target)


class Image:
    def __init__(
        self,
        repo: str,
        tag: str,
        build_options: Dict[str, Any],
        docker_client: Optional[docker.client.DockerClient] = None,
        logger: Union[logging.Logger, logging.LoggerAdapter] = logger,
    ) -> None:
        self.repo: str = repo
        self.tag: str = tag
        self.build_options: Dict[str, Any] = build_options
        self.logger: Union[logging.Logger, logging.LoggerAdapter] = logger

        if docker_client is None:
            docker_client = docker.from_env(version="auto")

        self.docker_client: docker.client.DockerClient = docker_client

    def _process_transfer_log_stream(
        self, log_stream: Generator[Dict[str, Any], None, None]
    ) -> None:
        for log_entry in log_stream:
            if "error" in log_entry:
                raise ImageAccessError(log_entry["error"])
            if "status" not in log_entry or log_entry.get("progressDetail"):
                continue
            if "id" in log_entry:
                message = f"{log_entry.get('id')}: {log_entry.get('status')}"
            else:
                message = log_entry["status"]
            self.logger.info(message)

    @property
    def name(self) -> str:
        return f"{self.repo}:{self.tag}"

    @property
    def loaded(self) -> bool:
        loaded = False

        for image in self.docker_client.images.list(name=self.repo):
            if self.name in image.attrs["RepoTags"]:
                loaded = True
                break

        return loaded

    def pull(self) -> None:
        try:
            self.logger.info(f"{self.name} Trying pull...")
            log_stream = self.docker_client.api.pull(
                self.name, self.tag, stream=True, decode=True
            )
            self._process_transfer_log_stream(log_stream)
        except docker.errors.NotFound as error:
            raise ImageNotFoundError(error.explanation)
        except docker.errors.APIError as error:
            raise ImageAccessError(error.explanation)

    def _build(self) -> Generator[Dict[str, Any], None, None]:
        try:
            self.logger.info(f"{self.name} Trying build...")
            log_stream = self.docker_client.api.build(**self.build_options)
        except docker.errors.APIError as error:
            raise ImageBuildError(str(error))
        return log_stream

    def build(self) -> None:
        log_stream = self._build()
        for log_entry in log_stream:
            if "error" in log_entry:
                raise ImageBuildError(log_entry["error"])
            if message := log_entry.get("stream", "").strip():
                self.logger.info(message)
        self._prune_dangling_images()

    def _prune_dangling_images(self):
        try:
            self.docker_client.api.prune_images(filters={"dangling": True})
        except Exception as error:
            self.logger.warning(f"prune dangling images failed: {error}")

    def push(self) -> None:
        try:
            self.logger.info(f"{self.name} Trying push...")
            log_stream = self.docker_client.images.push(
                repository=self.repo, tag=self.tag, stream=True, decode=True
            )
            self._process_transfer_log_stream(log_stream)
        except docker.errors.APIError as error:
            raise ImagePushError(str(error))


class ImageFactory:
    def __init__(self, config: Config, repo: str, tags: Dict[str, str]) -> None:
        self.config: Config = config
        self.repo: str = repo
        self.tags: Dict[str, str] = tags
        self.digests: Dict[str, str] = dict()

    def __call__(self, target: str) -> Image:
        image = Image(
            repo=self.repo,
            tag=self.get_target_tag(target),
            build_options=self.get_target_build_options(target),
            logger=self.get_target_logger(target),
        )

        lines = json.dumps(image.build_options, sort_keys=True, indent=4).splitlines()
        image.logger.info(f"build_options {lines.pop(0)}")
        for line in lines:
            image.logger.info(line)

        return image

    def get_target_logger(self, target: str) -> TargetLoggerAdapter:
        return TargetLoggerAdapter(logger, extra={"target": target})

    def get_hasher(self):
        if self.config.hash_algorithm not in hashlib.algorithms_available:
            raise HashAlgorithmNotFound(
                f"{self.config.hash_algorithm} not found in hashlib"
            )

        return getattr(hashlib, self.config.hash_algorithm)()

    def get_file_digest(self, path: str) -> str:
        hasher = self.get_hasher()
        chunk_size = self.config.hash_chunk_size

        with open(path, "rb") as file_data:
            chunker = functools.partial(file_data.read, chunk_size)
            for chunk in iter(chunker, b""):
                hasher.update(chunk)

        return hasher.hexdigest()

    def _get_target_digest(self, target: str) -> str:
        hasher = self.get_hasher()
        logger = self.get_target_logger(target)

        for path in self.config.get_target(target).get("watch_files", []):
            digest = self.get_file_digest(path)
            hasher.update(digest.encode())
            logger.info(f"watch_files {path} {hasher.name}:{digest}")
        for dependent in self.config.get_target(target).get("depends_on", []):
            hasher.update(self.digests[dependent].encode())
            logger.info(
                f"depends_on {dependent} {hasher.name}:{self.digests[dependent]}"
            )

        digest = hasher.hexdigest()
        logger.info(f"target_digest {hasher.name}:{digest}")

        return digest

    def get_target_digest(self, target: str) -> Optional[str]:
        if target not in self.digests and self.config.get_target(target).get(
            "watch_files", []
        ):
            self.digests[target] = self._get_target_digest(target)

        return self.digests.get(target)

    def get_target_tag(self, target: str) -> str:
        if target not in self.tags:
            digest = self.get_target_digest(target)
            if digest is not None:
                self.tags[target] = digest[: self.config.short_digest_size]
            else:
                raise TargetTagError(
                    f"target '{target}' has no watch_files and no explicit tag"
                )
        return self.tags[target]

    def get_target_labels(self, target: str) -> Dict[str, str]:
        labels = {self.config.target_label: target}

        if digest := self.get_target_digest(target):
            hasher = self.get_hasher()
            labels[self.config.digest_label] = f"{hasher.name}:{digest}"

        return labels

    def get_target_buildargs(self, target: str) -> Dict[str, str]:
        buildargs = {}

        for dependent in self.config.get_target(target).get("depends_on", []):
            arg = f"prefab_{dependent}"
            value = f"{self.repo}:{self.get_target_tag(dependent)}"
            buildargs[arg] = value

        return buildargs

    def get_target_build_options(self, target: str) -> Dict[str, Any]:
        build_config = self.config.get_target(target)
        build_options: Dict[str, Any] = {
            **DEFAULT_BUILD_OPTIONS,
            **{
                "dockerfile": build_config["dockerfile"],
                "labels": self.get_target_labels(target),
                "buildargs": self.get_target_buildargs(target),
                "tag": f"{self.repo}:{self.get_target_tag(target)}",
            },
        }

        for key, value in build_config.get("build_options", {}):
            if key in {"labels", "buildargs"}:
                build_options[key].update(value)
            else:
                build_options[key] = value

        return build_options


class ImageTree:
    def __init__(
        self,
        config: Config,
        image_factory: Callable,
        noop: bool = False,
    ) -> None:
        self.config: Config = config
        self.image_factory: Callable = image_factory
        self.images: Dict[str, Image] = {}
        self.noop: bool = noop

    def _resolve_target_dependencies(
        self,
        target: str,
        dependencies: List[str],
        vectors: List[Tuple[str, str]],
    ) -> List[str]:
        for dependent in self.config.get_target(target).get("depends_on", []):
            vector = (target, dependent)
            if vector in vectors:
                raise TargetCyclicError(f"target '{target}' has circular dependencies")
            else:
                checkpoint = len(vectors)
                vectors.append(vector)
                self._resolve_target_dependencies(dependent, dependencies, vectors)
                del vectors[checkpoint:]

            if dependent not in dependencies:
                dependencies.append(dependent)

        return dependencies

    def resolve_target_dependencies(self, target: str) -> List[str]:
        dependencies = self._resolve_target_dependencies(
            target=target, dependencies=[], vectors=[]
        )
        dependencies.append(target)

        return dependencies

    def resolve_target_images(self, target: str) -> Generator[Image, None, None]:
        for dependency in self.resolve_target_dependencies(target):
            if dependency not in self.images:
                self.images[dependency] = self.image_factory(dependency)
                yield self.images[dependency]

    def _build(self, image: Image) -> None:
        try:
            if image.loaded:
                image.logger.info(f"{image.name} Image loaded")
            else:
                image.logger.info(f"{image.name} Image not loaded")
                image.pull()
        except Exception as error:
            allow_errors = self.config.allow_pull_errors
            if isinstance(error, allow_errors):
                error_name = type(error).__name__
                image.logger.info(f"{image.name} {error_name}: {error}")
                image.logger.info(
                    f"{image.name} {error_name} in allow_pull_errors, continuing..."
                )
                image.build()
            else:
                raise

    def build(self, targets: List[str]) -> None:
        for target in targets:
            for image in self.resolve_target_images(target):
                if self.noop:
                    image.logger.info(f"{image.name} Trying build... [DRY RUN]")
                else:
                    self._build(image)

    def push(self) -> None:
        for image in self.images.values():
            if self.noop:
                image.logger.info(f"{image.name} Trying push... [DRY RUN]")
            else:
                image.push()


def parse_options(args: List[str]) -> argparse.Namespace:
    description = "Efficiently build docker images"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--config",
        "-c",
        dest="config_file",
        action="store",
        metavar="PATH",
        default=DEFAULT_CONFIG_FILE,
        help="Target build config file to use",
    )
    parser.add_argument(
        "--dry-run",
        dest="noop",
        action="store_true",
        help="Show images to be built or pushed",
    )
    parser.add_argument(
        "--push",
        "-p",
        action="store_true",
        help="Push images to repo after building",
    )
    parser.add_argument(
        "--repo",
        "-r",
        dest="repo",
        action="store",
        metavar="URI",
        required=True,
        help="Image repo to use (e.g. quay.io/lexsca/prefab)",
    )
    parser.add_argument(
        "--target",
        "-t",
        dest="_targets",
        action="append",
        required=True,
        metavar="NAME[:TAG]",
        help="Image target(s) to build with optional custom image tag",
    )

    options = parser.parse_args(args)
    options.tags = dict()
    options.targets = []

    for target in options._targets:
        target, _, tag = target.partition(":")
        options.targets.append(target)
        if tag is not None:
            options.tags[target] = tag

    return options


def main(args: List[str]) -> None:
    start_time = time.monotonic()

    options = parse_options(args)
    config = Config.from_yaml_filepath(options.config_file)

    image_factory = ImageFactory(config, options.repo, options.tags)
    image_tree = ImageTree(config, image_factory, options.noop)
    image_tree.build(options.targets)

    if options.push:
        image_tree.push()

    elapsed = datetime.timedelta(seconds=time.monotonic() - start_time)
    logger.info(f"Elapsed time: {str(elapsed)[:-4]}")


def _main() -> None:
    if __name__ == "__main__":
        try:
            main(sys.argv[1:])
            status = 0
        except DockerPrefabError as error:
            logger.error(f"{type(error).__name__}: {error}")
            status = 1
        except Exception:
            logger.error(traceback.format_exc())
            status = 1
        sys.exit(status)


_main()
