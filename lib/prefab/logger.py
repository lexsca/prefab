import logging
from typing import Any, MutableMapping, Tuple

from .color import color


logger = logging.getLogger("prefab")
logger.handlers = [logging.StreamHandler()]
logger.setLevel(logging.INFO)


class TargetLoggerAdapter(logging.LoggerAdapter):
    def process(
        self, message: str, kwargs: MutableMapping[str, Any]
    ) -> Tuple[str, MutableMapping[str, Any]]:
        extra = {} if self.extra is None else self.extra
        prefix = color.target(f"[{extra.get('target', '<none>')}]")
        return f"{prefix} {message}", kwargs
