import logging
from typing import Any, Dict, Tuple

from .color import color


logger = logging.getLogger("prefab")
logger.handlers = [logging.StreamHandler()]
logger.setLevel(logging.INFO)


class TargetLoggerAdapter(logging.LoggerAdapter):
    def process(
        self, message: str, kwargs: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        prefix = color.target(f"[{self.extra.get('target', '<none>')}]")
        return f"{prefix} {message}", kwargs
