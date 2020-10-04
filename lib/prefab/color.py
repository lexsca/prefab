from typing import Dict


class Color:
    _map: Dict[str, str] = {
        "black": "\x1b[30m",
        "red": "\x1b[31m",
        "green": "\x1b[32m",
        "yellow": "\x1b[33m",
        "blue": "\x1b[34m",
        "magenta": "\x1b[35m",
        "cyan": "\x1b[36m",
        "white": "\x1b[37m",
    }
    _reset: str = "\x1b[0m"

    def __init__(self) -> None:
        cls = type(self)

        for color, code in self._map.items():
            if not hasattr(cls, color):

                def colorizer(this, text, code=code) -> str:
                    return f"{code}{text}{self._reset}" if this.enabled else text

                setattr(cls, color, colorizer)

        self.enabled = True


color = Color()
