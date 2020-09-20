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

DEFAULT_ALLOW_PULL_ERRORS: List[str] = [
    "ImageAccessError",
    "ImageNotFoundError",
    "ImageValidationError",
]
DEFAULT_BUILD_OPTIONS: Dict[str, Any] = {
    "decode": True,
    "forcerm": True,
    "path": ".",
    "rm": True,
}
DEFAULT_BUILDARG_PREFIX = "prefab_"
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


class ImageValidationError(DockerPrefabError):
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

    def get_target(self, name: str) -> Dict[str, Any]:
        target = self.data.get("targets", {}).get(name)

        if target is None:
            raise TargetNotFoundError(f"Target [{name}] not found in build config")

        for key in ["depends_on", "watch_files"]:
            if key not in target:
                target[key] = []

        if "build_options" not in target:
            target["build_options"] = {}

        return target

    @property
    def allow_pull_errors(self) -> Tuple[Any, ...]:
        allow_names = self.get_option("allow_pull_errors", DEFAULT_ALLOW_PULL_ERRORS)
        symbols = globals()
        return tuple(symbols[name] for name in allow_names if name in symbols)

    @property
    def buildarg_prefix(self) -> str:
        return str(self.get_option("buildarg_prefix", DEFAULT_BUILDARG_PREFIX))

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

    def validate_target_config(self, target: str, config: Dict[str, Any]) -> None:
        if not isinstance(config.get("depends_on", []), list):
            raise InvalidConfigError(f"{target}: list expected for target depends_on")

        if not isinstance(config.get("watch_files", []), list):
            raise InvalidConfigError(f"{target}: list expected for target watch_files")

        if not isinstance(config.get("build_options", {}), dict):
            raise InvalidConfigError(
                f"{target}: dict expected for target build_options"
            )

    def validate_target(self, target: str) -> None:
        config = self.data["targets"][target]

        if not isinstance(config, dict):
            raise InvalidConfigError(f"{target}: dict expected for target config")

        if "dockerfile" not in config or not isinstance(config["dockerfile"], str):
            raise InvalidConfigError(f"{target}: dockerfile required in target config")

        self.validate_target_config(target, config)

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
        self._loaded: Optional[bool] = None
        self.was_pulled: bool = False
        self.was_built: bool = False

        if docker_client is None:
            docker_client = docker.from_env(version="auto")

        self.docker_client: docker.client.DockerClient = docker_client

    def _log_transfer_message(self, log_entry) -> None:
        if "id" in log_entry:
            message = f"{log_entry.get('id')}: {log_entry.get('status')}"
        else:
            message = str(log_entry["status"])

        self.logger.info(message)

    def _process_transfer_log_stream(
        self, log_stream: Generator[Dict[str, Any], None, None]
    ) -> None:
        for log_entry in log_stream:
            if "error" in log_entry:
                raise ImageAccessError(log_entry["error"])

            if "status" not in log_entry or log_entry.get("progressDetail"):
                continue

            self._log_transfer_message(log_entry)

    def _get_docker_image(self) -> Optional[docker.models.images.Image]:
        docker_image = None

        for image in self.docker_client.images.list(name=self.repo):
            if self.name in image.tags:
                docker_image = image
                break

        return docker_image

    @property
    def name(self) -> str:
        return f"{self.repo}:{self.tag}"

    @property
    def loaded(self) -> bool:
        if self._loaded is None:
            self._loaded = bool(self._get_docker_image())

        return self._loaded

    def pull(self) -> None:
        try:
            log_stream = self.docker_client.api.pull(
                self.name, self.tag, stream=True, decode=True
            )
            self._process_transfer_log_stream(log_stream)
            self._loaded = True
            self.was_pulled = True
        except docker.errors.NotFound as error:
            raise ImageNotFoundError(error.explanation)
        except docker.errors.APIError as error:
            raise ImageAccessError(error.explanation)

    def validate(self) -> None:
        docker_image = self._get_docker_image()

        if docker_image is None:
            raise ImageNotFoundError(f"{self.name} unable to find for validation")

        for name, expected in self.build_options["labels"].items():
            result = docker_image.labels.get(name)
            if result != expected:
                raise ImageValidationError(
                    f"label {name} expected {expected}, got {result}"
                )

    def _build(self) -> Generator[Dict[str, Any], None, None]:
        try:
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

        self.was_built = True
        self._loaded = True
        self._prune_dangling_images()

    def _prune_dangling_images(self):
        try:
            self.docker_client.api.prune_images(filters={"dangling": True})
        except Exception as error:
            self.logger.warning(f"Prune dangling images failed: {error}")

    def push(self) -> None:
        try:
            log_stream = self.docker_client.images.push(
                repository=self.repo, tag=self.tag, stream=True, decode=True
            )
            self._process_transfer_log_stream(log_stream)
        except docker.errors.APIError as error:
            raise ImagePushError(str(error))


class ImageFactory:
    def __init__(
        self,
        config: Config,
        repo: str,
        tags: Dict[str, str],
        image_constructor: Callable = Image,
    ) -> None:
        self.config: Config = config
        self.repo: str = repo
        self.tags: Dict[str, str] = tags
        self.image_constructor: Callable = image_constructor
        self.digests: Dict[str, str] = dict()

    def __call__(self, target: str) -> Image:
        return self.image_constructor(
            repo=self.repo,
            tag=self.get_target_tag(target),
            build_options=self.get_target_build_options(target),
            logger=self.get_target_logger(target),
        )

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
        target_logger = self.get_target_logger(target)

        for path in self.config.get_target(target)["watch_files"]:
            digest = self.get_file_digest(path)
            hasher.update(digest.encode())
            target_logger.info(f"watch_files {path} {hasher.name}:{digest}")

        for dependent in self.config.get_target(target)["depends_on"]:
            hasher.update(self.digests[dependent].encode())
            target_logger.info(
                f"depends_on {dependent} {hasher.name}:{self.digests[dependent]}"
            )

        digest = hasher.hexdigest()
        target_logger.info(f"target_digest {hasher.name}:{digest}")

        return digest

    def get_target_digest(self, target: str) -> Optional[str]:
        if target not in self.digests and self.config.get_target(target)["watch_files"]:
            self.digests[target] = self._get_target_digest(target)

        return self.digests.get(target)

    def get_target_tag(self, target: str) -> str:
        if target not in self.tags:
            digest = self.get_target_digest(target)
            if digest is not None:
                self.tags[target] = digest[: self.config.short_digest_size]
            else:
                raise TargetTagError(
                    f"Target [{target}] has no watch_files and no explicit tag"
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

        for dependent in self.config.get_target(target)["depends_on"]:
            arg = f"{self.config.buildarg_prefix}{dependent}"
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

        for key, value in build_config.get("build_options", {}).items():
            if key in {"labels", "buildargs"}:
                build_options[key].update(value)
            else:
                build_options[key] = value

        return build_options


class ImageTree:
    def __init__(self, config: Config, image_factory: Callable) -> None:
        self.config: Config = config
        self.image_factory: Callable = image_factory
        self.images: Dict[str, Image] = {}
        self.targets: Dict[str, List[Image]] = {}

    def configure_target_image(self, target: str) -> Image:
        if target not in self.images:
            image = self.images[target] = self.image_factory(target)
            image.logger.info(f"target_image {image.name}")

        return self.images[target]

    def _resolve_target_images(
        self, target: str, images: List[Image], vectors: List[Tuple[str, str]]
    ) -> List[Image]:
        # use a depth-first search to unroll dependencies and detect loops.
        # targets have a directed dependency stream. if an upstream target
        # dependency changes, downstream dependencies also change.
        for dependent in self.config.get_target(target).get("depends_on", []):
            vector = (target, dependent)
            if vector in vectors:
                raise TargetCyclicError(f"Target [{target}] has circular dependencies")
            else:
                checkpoint = len(vectors)
                vectors.append(vector)
                self._resolve_target_images(dependent, images, vectors)
                del vectors[checkpoint:]

        image = self.configure_target_image(target)
        if image not in images:
            images.append(image)

        return images

    def resolve_target_images(self, target: str) -> List[Image]:
        return self._resolve_target_images(target=target, images=[], vectors=[])

    def pull_target_image(self, image: Image) -> None:
        try:
            image.logger.info(f"{image.name} Trying pull...")
            image.pull()
        except Exception as error:
            if not isinstance(error, self.config.allow_pull_errors):
                raise
            else:
                error_name = type(error).__name__
                image.logger.info(f"{image.name} {error_name}: {error}")
                image.logger.info(
                    f"{image.name} {error_name} in allow_pull_errors, continuing..."
                )

    def load_target_image(self, image: Image) -> bool:
        if image.loaded:
            image.logger.info(f"{image.name} Image loaded")
        else:
            image.logger.info(f"{image.name} Image not loaded")
            self.pull_target_image(image)

        if image.loaded:
            image.validate()
            image.logger.info(f"{image.name} Image validated")

        return image.loaded

    @staticmethod
    def display_image_build_options(image: Image) -> None:
        json_text = json.dumps(image.build_options, sort_keys=True, indent=4)
        json_lines = json_text.splitlines()
        image.logger.info(f"{image.name} build_options {json_lines.pop(0)}")

        for line in json_lines:
            image.logger.info(line)

    def should_load_target_image(self, target: str) -> bool:
        # only load images if no upstream dependencies were (re)built
        return not any(image for image in self.targets[target] if image.was_built)

    def build_target_image(self, target: str) -> None:
        for image in self.targets[target]:
            if self.should_load_target_image(target):
                self.load_target_image(image)

            if not image.loaded:
                image.logger.info(f"{image.name} Trying build...")
                self.display_image_build_options(image)
                image.build()

    def build(self, targets: List[str]) -> None:
        logger.info("\nResolving dependency graph...")
        for target in targets:
            self.targets[target] = self.resolve_target_images(target)

        for target in targets:
            logger.info(f"\nBuilding [{target}] target...")
            self.build_target_image(target)

    def push(self) -> None:
        logger.info("\nPushing images...")
        for image in self.images.values():
            if image.loaded:
                if image.was_pulled:
                    image.logger.info(f"{image.name} Skipping push of pulled image")
                else:
                    image.logger.info(f"{image.name} Trying push...")
                    image.push()


def parse_options(args: List[str]) -> argparse.Namespace:
    description = "Efficiently build container images"
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
        if tag:
            options.tags[target] = tag

    return options


def elapsed_time(monotonic_start: float) -> str:
    elapsed_time = datetime.timedelta(seconds=time.monotonic() - monotonic_start)
    return str(elapsed_time)[:-4]


def main(args: List[str]) -> None:
    build_start_time = time.monotonic()

    options = parse_options(args)
    logger.info(f"Called with args: {' '.join(args)}")
    config = Config.from_yaml_filepath(options.config_file)

    image_factory = ImageFactory(config, options.repo, options.tags)
    image_tree = ImageTree(config, image_factory)
    image_tree.build(options.targets)
    logger.info(f"\nBuild elapsed time: {elapsed_time(build_start_time)}")

    if options.push:
        push_start_time = time.monotonic()
        image_tree.push()
        logger.info(f"\nPush elapsed time: {elapsed_time(push_start_time)}")
        logger.info(f"\nTotal elapsed time: {elapsed_time(build_start_time)}")


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
