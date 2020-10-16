import functools
import hashlib
from typing import Any, Callable, Dict

from .. import constants as C
from .. import errors as E
from ..config import Config
from ..logger import logger, TargetLoggerAdapter
from .docker import DockerImage


class ImageFactory:
    def __init__(
        self,
        config: Config,
        repo: str,
        tags: Dict[str, str],
        image_constructor: Callable = DockerImage,
    ) -> None:
        self.config: Config = config
        self.repo: str = repo
        self.tags: Dict[str, str] = tags
        self.image_constructor: Callable = image_constructor
        self.digests: Dict[str, str] = dict()

    def __call__(self, target: str) -> DockerImage:
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
            raise E.HashAlgorithmNotFound(
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
        target_config = self.config.get_target(target)

        hasher.update(target.encode())

        for path in [target_config.get("dockerfile")] + target_config["watch_files"]:
            digest = self.get_file_digest(path)
            hasher.update(digest.encode())
            target_logger.info(f"file_digest {path} {hasher.name}:{digest}")

        for dependency in target_config["depends_on"]:
            hasher.update(self.digests[dependency].encode())
            target_logger.info(
                f"depends_on {dependency} {hasher.name}:{self.digests[dependency]}"
            )

        digest = hasher.hexdigest()
        target_logger.info(f"target_digest {hasher.name}:{digest}")

        return digest

    def get_target_digest(self, target: str) -> str:
        if target not in self.digests:
            self.digests[target] = self._get_target_digest(target)

        return self.digests[target]

    def get_target_tag(self, target: str) -> str:
        if target not in self.tags:
            digest = self.get_target_digest(target)
            self.tags[target] = digest[: self.config.short_digest_size]

        return self.tags[target]

    def get_target_labels(self, target: str) -> Dict[str, str]:
        digest = self.get_target_digest(target)
        hasher = self.get_hasher()

        return {
            self.config.target_label: target,
            self.config.digest_label: f"{hasher.name}:{digest}",
        }

    def get_target_buildargs(self, target: str) -> Dict[str, str]:
        buildargs = {}

        for dependency in self.config.get_target(target)["depends_on"]:
            arg = f"{self.config.buildarg_prefix}{dependency}"
            value = f"{self.repo}:{self.get_target_tag(dependency)}"
            buildargs[arg] = value

        return buildargs

    def get_target_build_options(self, target: str) -> Dict[str, Any]:
        target_config = self.config.get_target(target)
        build_options: Dict[str, Any] = {
            **C.DEFAULT_BUILD_OPTIONS,
            **{
                "dockerfile": target_config["dockerfile"],
                "labels": self.get_target_labels(target),
                "buildargs": self.get_target_buildargs(target),
                "tag": f"{self.repo}:{self.get_target_tag(target)}",
            },
        }

        for key, value in target_config.get("build_options", {}).items():
            if key in {"labels", "buildargs"}:
                build_options[key].update(value)
            else:
                build_options[key] = value

        return build_options