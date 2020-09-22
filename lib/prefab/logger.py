import logging


logger = logging.getLogger("prefab")
logger.handlers = [logging.StreamHandler()]
logger.setLevel(logging.INFO)


class TargetLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[{self.extra.get('target', '<none>')}] {msg}", kwargs
