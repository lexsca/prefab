import argparse
import datetime
import functools
import hashlib
import logging
import sys
import time
import traceback
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

import docker
import yaml


logger = logging.getLogger(__name__)
logger.handlers = [logging.StreamHandler()]
logger.setLevel(logging.INFO)

DEFAULT_HASH_ALGORITHM = "sha256"
DEFAULT_DIGEST_LABEL = "prefab.digest"
DEFAULT_TARGET_LABEL = "prefab.target"
DEFAULT_CHUNK_SIZE = 65535
DEFAULT_CONFIG_FILE = "prefab.yml"
SHORT_DIGEST_SIZE = 12


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
            self.logger.info(f"{self.name} pulling")
            log_stream = self.docker_client.api.pull(
                self.name, self.tag, stream=True, decode=True
            )
            self._process_transfer_log_stream(log_stream)
        except docker.errors.NotFound as error:
            raise ImageNotFoundError(str(error))
        except docker.errors.APIError as error:
            raise ImageAccessError(str(error))

    def _build(self) -> Generator[Dict[str, Any], None, None]:
        # https://docker-py.readthedocs.io/en/stable/api.html#module-docker.api.build
        build_options: Dict[str, Any] = {
            "decode": True,
            "forcerm": True,
            "path": ".",
            "rm": True,
            "squash": True,
            "tag": self.name,
        }
        if self.build_options is not None:
            build_options.update(self.build_options)
        try:
            self.logger.info(f"{self.name} building")
            log_stream = self.docker_client.api.build(**build_options)
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
            self.logger.info(f"{self.name} pushing")
            log_stream = self.docker_client.images.push(
                repository=self.repo, tag=self.tag, stream=True, decode=True
            )
            self._process_transfer_log_stream(log_stream)
        except docker.errors.APIError as error:
            raise ImagePushError(str(error))


class ImageTree:
    def __init__(
        self, repo: str, build_targets: List[str], build_config: Dict[str, Any]
    ) -> None:
        self.repo: str = repo
        self.build_targets: List[str] = []
        self.build_config: Dict[str, Any] = build_config
        self.images: Dict[str, Image] = {}
        self.digests: Dict[str, str] = {}
        self.tags: Dict[str, str] = {}

        for target in build_targets:
            target, _, tag = target.partition(":")
            self.build_targets.append(target)
            self.tags[target] = tag

    def get_target(self, target: str) -> Dict[str, Any]:
        targets = self.build_config.get("targets", {})

        if target not in targets:
            raise TargetNotFoundError(f"target '{target}' not found in build config")

        return targets[target]

    def get_hasher(self):
        build_options = self.build_config.get("options", {})
        hash_algorithm = build_options.get("hash_algorithm", DEFAULT_HASH_ALGORITHM)

        if hash_algorithm not in hashlib.algorithms_available:
            raise HashAlgorithmNotFound(f"{hash_algorithm} not found in hashlib")
        hasher = getattr(hashlib, hash_algorithm)()

        return hasher

    def get_target_labels(self, target: str) -> Dict[str, str]:
        build_options = self.build_config.get("options", {})
        digest_label = build_options.get("prefab_digest_label", DEFAULT_DIGEST_LABEL)
        target_label = build_options.get("prefab_target_label", DEFAULT_TARGET_LABEL)

        hasher = self.get_hasher()
        digest = self.get_target_digest(target)
        labels = {target_label: target}

        if hasher and digest:
            labels[digest_label] = f"{hasher.name}:{digest}"

        return labels

    def get_file_digest(self, path: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
        hasher = self.get_hasher()

        with open(path, "rb") as file_data:
            chunker = functools.partial(file_data.read, chunk_size)
            for chunk in iter(chunker, b""):
                hasher.update(chunk)

        return hasher.hexdigest()

    def _get_target_digest(self, target: str) -> str:
        hasher = self.get_hasher()
        target_logger = target_logger_factory(target)

        for path in self.get_target(target).get("watch_files", []):
            digest = self.get_file_digest(path)
            hasher.update(digest.encode())
            target_logger.info(f"watch_files {path} {hasher.name}:{digest}")
        for dependent in self.get_target(target).get("depends_on", []):
            hasher.update(self.digests[dependent].encode())
            target_logger.info(
                f"depends_on {dependent} {hasher.name}:{self.digests[dependent]}"
            )

        digest = hasher.hexdigest()
        target_logger.info(f"prefab.digest {hasher.name}:{digest}")
        return digest

    def get_target_digest(self, target: str) -> Optional[str]:
        if target not in self.digests and self.get_target(target).get(
            "watch_files", []
        ):
            self.digests[target] = self._get_target_digest(target)

        return self.digests.get(target)

    def resolve_target_dependencies(
        self,
        target: str,
        dependencies: List[str],
        vectors: List[Tuple[str, str]],
    ) -> List[str]:
        for dependent in self.get_target(target).get("depends_on", []):
            vector = (target, dependent)
            if vector in vectors:
                raise TargetCyclicError(f"target '{target}' has circular dependencies")
            else:
                checkpoint = len(vectors)
                vectors.append(vector)
                self.resolve_target_dependencies(dependent, dependencies, vectors)
                del vectors[checkpoint:]

            if dependent not in dependencies:
                dependencies.append(dependent)

        return dependencies

    def get_target_build_order(self, target: str) -> List[str]:
        build_order = self.resolve_target_dependencies(
            target=target, dependencies=[], vectors=[]
        )
        build_order.append(target)

        return build_order

    def get_target_tag(self, target: str) -> str:
        if target not in self.tags:
            digest = self.get_target_digest(target)
            if digest is not None:
                self.tags[target] = digest[:SHORT_DIGEST_SIZE]
            else:
                raise TargetTagError(
                    f"target '{target}' has no watch_files and no explicit tag"
                )
        return self.tags[target]

    def get_target_buildargs(self, target: str) -> Dict[str, str]:
        buildargs = {}

        for dependent in self.get_target(target).get("depends_on", []):
            arg = f"prefab_{dependent}"
            value = f"{self.repo}:{self.get_target_tag(dependent)}"
            buildargs[arg] = value

        return buildargs

    def get_target_build_options(self, target: str) -> Dict[str, Any]:
        build_options: Dict[str, Any] = {
            "dockerfile": self.get_target(target)["dockerfile"],
            "labels": self.get_target_labels(target),
            "buildargs": self.get_target_buildargs(target),
        }

        for key, value in self.get_target(target).get("build_options", {}):
            if key in {"labels", "buildargs"}:
                build_options[key].update(value)
            else:
                build_options[key] = value

        return build_options

    def _build_target(self, target: str) -> None:
        tag = self.get_target_tag(target)
        build_options = self.get_target_build_options(target)
        target_logger = target_logger_factory(target)
        image = Image(self.repo, tag, build_options, logger=target_logger)

        try:
            if image.loaded:
                target_logger.info(f"{image.name} loaded")
            else:
                target_logger.info(f"{image.name} not loaded")
                image.pull()
        except ImageNotFoundError:
            target_logger.info(f"{image.name} not found")
            image.build()
        self.images[target] = image

    def build_target(self, target: str) -> None:
        if target not in self.images:
            self._build_target(target)

    def build_all(self) -> None:
        for build_target in self.build_targets:
            build_order = self.get_target_build_order(build_target)
            for target in build_order:
                self.build_target(target)

    def push_all(self) -> None:
        for image in self.images.values():
            image.push()


class TargetLoggingAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[{self.extra.get('target', '<none>')}] {msg}", kwargs


def target_logger_factory(
    target: str, logger: logging.Logger = logger
) -> logging.LoggerAdapter:
    return TargetLoggingAdapter(logger, extra={"target": target})


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
        dest="targets",
        action="append",
        required=True,
        metavar="NAME[:TAG]",
        help="Image target(s) to build with optional custom image tag",
    )

    return parser.parse_args(args)


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    if "targets" not in config:
        raise InvalidConfigError("targets section missing")

    if not isinstance(config["targets"], dict):
        raise InvalidConfigError("dict expected for targets section")

    if not config["targets"]:
        raise InvalidConfigError("no targets defined")

    for target_name, target_config in config["targets"].items():
        if not isinstance(target_config, dict):
            raise InvalidConfigError(f"{target_name}: dict expected for target config")

        if "dockerfile" not in target_config or not isinstance(
            target_config["dockerfile"], str
        ):
            raise InvalidConfigError(
                f"{target_name}: str dockerfile path required in target config"
            )
        if not isinstance(target_config.get("depends_on", []), list):
            raise InvalidConfigError(
                f"{target_name}: list expected for target depends_on"
            )
        if not isinstance(target_config.get("watch_files", []), list):
            raise InvalidConfigError(
                f"{target_name}: list expected for target watch_files"
            )
        if not isinstance(target_config.get("build_options", {}), dict):
            raise InvalidConfigError(
                f"{target_name}: dict expected for target build_options"
            )

    return config


def load_config(path: str) -> Dict[str, Any]:
    with open(path) as raw_config:
        return yaml.safe_load(raw_config)


def parse_config(path: str) -> Dict[str, Any]:
    return validate_config(load_config(path))


def main(args: List[str]) -> None:
    start_time = time.monotonic()
    options = parse_options(args)
    config = parse_config(options.config_file)

    image_tree = ImageTree(options.repo, options.targets, config)
    image_tree.build_all()

    if options.push:
        image_tree.push_all()

    elapsed_time = int(time.monotonic() - start_time)
    logger.info(f"elapsed time: {datetime.timedelta(seconds=elapsed_time)}")


def _main() -> None:
    if __name__ == "__main__":
        try:
            main(sys.argv[1:])
            status = 0
        except Exception:
            logger.error(traceback.format_exc())
            status = 1
        sys.exit(status)


_main()
