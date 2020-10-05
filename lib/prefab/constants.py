from typing import Any, Dict, List


DEFAULT_ALLOWED_PULL_ERRORS: List[str] = [
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
DEFAULT_BUILD_ON_VALIDATE_ERROR = True
DEFAULT_CONFIG_FILE = "prefab.yml"
DEFAULT_DIGEST_LABEL = "prefab.digest"
DEFAULT_HASH_ALGORITHM = "sha256"
DEFAULT_HASH_CHUNK_SIZE = 65535
DEFAULT_PRUNE_AFTER_BUILD = False
DEFAULT_SHORT_DIGEST_SIZE = 12
DEFAULT_TARGET_LABEL = "prefab.target"
DEFAULT_VALIDATE_IMAGE = True
