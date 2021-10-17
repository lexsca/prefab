from typing import Dict, Optional

from . import constants as C


class Color:
    reset: str = "\x1b[0m"

    def __init__(
        self,
        style: Dict[str, Optional[int]] = C.DEFAULT_COLOR_STYLE,
        enabled: bool = True,
    ) -> None:
        self.enabled: bool = enabled
        self.style: Dict[str, Optional[int]] = style.copy()

    def _colorize(self, style_name: str, text: str) -> str:
        # https://en.wikipedia.org/wiki/ANSI_escape_code#8-bit
        color_code = self.style.get(style_name)
        color_seq = f"\x1b[38;5;{color_code}m"
        colorize = self.enabled and color_code is not None

        return f"{color_seq}{text}{self.reset}" if colorize else text

    def config(self, text: str) -> str:
        return self._colorize("config", text)

    def elapsed(self, text: str) -> str:
        return self._colorize("elapsed", text)

    def error(self, text: str) -> str:
        return self._colorize("error", text)

    def header(self, text: str) -> str:
        return self._colorize("header", text)

    def image(self, text: str) -> str:
        return self._colorize("image", text)

    def target(self, text: str) -> str:
        return self._colorize("target", text)

    def warning(self, text: str) -> str:
        return self._colorize("warning", text)


color = Color()
