import logging

from .color import color


logger = logging.getLogger("prefab")
logger.handlers = [logging.StreamHandler()]
logger.setLevel(logging.INFO)


class TargetLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        target = color.target(f"[{self.extra.get('target', '<none>')}]")
        return f"{target} {msg}", kwargs
