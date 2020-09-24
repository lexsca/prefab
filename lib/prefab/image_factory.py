import functools
import hashlib
from typing import Any, Callable, Dict, Optional

from . import constants as C
from . import errors as E
from .config import Config
from .image import Image
from .logger import logger, TargetLoggerAdapter


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
                raise E.TargetTagError(
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
