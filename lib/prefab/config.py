import collections
import json
from typing import Any, Dict, List, Optional

from . import errors as E
from . import constants as C
from .color import color
from .logger import logger

import yaml


class ConfigBase(collections.UserDict):
    def __init__(self, config: Dict[str, str], path: Optional[str] = None) -> None:
        super().__init__(config)
        self.validate_config()
        self.path: Optional[str] = path

    @classmethod
    def from_yaml_filepath(cls, path: str):
        with open(path) as raw_config:
            return cls(yaml.safe_load(raw_config), path)

    def display_options(self) -> None:
        cls = type(self)
        names = [name for name in dir(cls) if isinstance(getattr(cls, name), property)]
        for name in sorted(names):
            value = json.dumps(getattr(self, name))
            logger.info(f"{name}: {color.config(value)}")

    def validate_config(self) -> None:
        if "targets" not in self.data:
            raise E.InvalidConfigError("targets section missing")

        if not isinstance(self.data["targets"], dict):
            raise E.InvalidConfigError("dict expected for targets section")

        if not self.data["targets"]:
            raise E.InvalidConfigError("no targets defined")

        for target in self.data["targets"]:
            self.validate_target(target)

    def validate_target(self, target: str) -> None:
        config = self.data["targets"][target]

        if not isinstance(config, dict):
            raise E.InvalidConfigError(f"{target}: dict expected")

        if "dockerfile" not in config or not isinstance(config["dockerfile"], str):
            raise E.InvalidConfigError(
                f"{target}: dockerfile required in target config"
            )

        self.validate_target_config(target, config)

    def validate_target_config(self, target: str, config: Dict[str, Any]) -> None:
        if not isinstance(config.get("depends_on", []), list):
            raise E.InvalidConfigError(f"{target}: list expected for depends_on")

        if not isinstance(config.get("watch_files", []), list):
            raise E.InvalidConfigError(f"{target}: list expected for watch_files")

        if not isinstance(config.get("build_options", {}), dict):
            raise E.InvalidConfigError(f"{target}: dict expected for build_options")


class Config(ConfigBase):
    def get_target(self, name: str) -> Dict[str, Any]:
        target = self.data.get("targets", {}).get(name)

        if target is None:
            raise E.TargetNotFoundError(f"Target [{name}] not found in build config")

        for key in ["depends_on", "watch_files"]:
            if key not in target:
                target[key] = []

        if "build_options" not in target:
            target["build_options"] = {}

        return target

    def get_option(self, name: str, default: Any) -> Any:
        return self.data.get("options", {}).get(name, default)

    @property
    def allowed_pull_errors(self) -> List[str]:
        return self.get_option("allowed_pull_errors", C.DEFAULT_ALLOWED_PULL_ERRORS)

    @property
    def buildarg_prefix(self) -> str:
        return self.get_option("buildarg_prefix", C.DEFAULT_BUILDARG_PREFIX)

    @property
    def build_on_validate_error(self) -> str:
        return self.get_option(
            "build_on_validate_error", C.DEFAULT_BUILD_ON_VALIDATE_ERROR
        )

    @property
    def color_style(self) -> Dict[str, int]:
        return self.get_option("color_style", C.DEFAULT_COLOR_STYLE)

    @property
    def digest_label(self) -> str:
        return self.get_option("digest_label", C.DEFAULT_DIGEST_LABEL)

    @property
    def hash_algorithm(self) -> str:
        return self.get_option("hash_algorithm", C.DEFAULT_HASH_ALGORITHM)

    @property
    def hash_chunk_size(self) -> int:
        return self.get_option("hash_chunk_size", C.DEFAULT_HASH_CHUNK_SIZE)

    @property
    def ignore_files(self) -> List[str]:
        return self.get_option("ignore_files", C.DEFAULT_IGNORE_FILES)

    @property
    def prune_after_build(self) -> bool:
        return self.get_option("prune_after_build", C.DEFAULT_PRUNE_AFTER_BUILD)

    @property
    def short_digest_size(self) -> int:
        return self.get_option("short_digest_size", C.DEFAULT_SHORT_DIGEST_SIZE)

    @property
    def target_label(self) -> str:
        return self.get_option("target_label", C.DEFAULT_TARGET_LABEL)

    @property
    def validate_image(self) -> bool:
        return self.get_option("validate_image", C.DEFAULT_VALIDATE_IMAGE)
