from typing import Dict

from . import constants as C


class Color:
    reset: str = "\x1b[0m"

    def __init__(self, style: Dict[str, int] = C.DEFAULT_COLOR_STYLE) -> None:
        self.enabled: bool = True
        self.style: Dict[str, int] = style.copy()

        cls = type(self)

        for style in self.style:
            if not hasattr(cls, style):

                def colorizer(this, text: str, style: str = style) -> str:
                    # https://en.wikipedia.org/wiki/ANSI_escape_code#8-bit
                    color_code = self.style.get(style)
                    color_seq = f"\x1b[38;5;{color_code}m"
                    colorize = this.enabled and color_code is not None

                    return f"{color_seq}{text}{self.reset}" if colorize else text

                setattr(cls, style, colorizer)


color = Color()
