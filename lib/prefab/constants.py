from typing import Any, Dict, List, Optional


DEFAULT_ALLOWED_PULL_ERRORS: List[str] = [
    "ImageAccessError",
    "ImageNotFoundError",
    "ImageValidationError",
]
DEFAULT_BUILD_OPTIONS: Dict[str, Any] = {
    "forcerm": True,
    "path": ".",
    "rm": True,
    "squash": False,
}
DEFAULT_BUILDARG_PREFIX = "PREFAB_"
DEFAULT_BUILD_ON_VALIDATE_ERROR = True
DEFAULT_COLOR_STYLE: Dict[str, Optional[int]] = {
    "config": 2,
    "elapsed": 11,
    "error": 1,
    "header": None,
    "image": 3,
    "target": 6,
    "warning": 1,
}
DEFAULT_CONFIG_FILE = "prefab.yml"
DEFAULT_DIGEST_LABEL = "prefab.digest"
DEFAULT_ENVFILES: Dict[str, str] = {
    "REGISTRY_AUTH": "/auth.json",
}
DEFAULT_HASH_ALGORITHM = "sha256"
DEFAULT_HASH_CHUNK_SIZE = 65535
DEFAULT_IGNORE_FILES: List[str] = []
DEFAULT_PRUNE_AFTER_BUILD = True
DEFAULT_SHORT_DIGEST_SIZE = 12
DEFAULT_TARGET_LABEL = "prefab.target"
DEFAULT_VALIDATE_IMAGE = True
