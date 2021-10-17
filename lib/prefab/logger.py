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
        prefix = color.target(f"[{self.extra.get('target', '<none>')}]")
        return f"{prefix} {message}", kwargs
