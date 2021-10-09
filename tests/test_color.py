import pytest

from prefab.color import color


@pytest.fixture(autouse=True)
def enable_color(monkeypatch):
    monkeypatch.setattr(color, "enabled", True)


@pytest.fixture
def header_color_red(monkeypatch):
    monkeypatch.setitem(color.style, "header", 1)


@pytest.fixture
def header_color_none(monkeypatch):
    monkeypatch.setitem(color.style, "header", None)


def test_header_no_color(header_color_none):
    result = color.header("decline-voguish-misty-pause")

    assert result == "decline-voguish-misty-pause"


def test_header_red_color(header_color_red):
    result = color.header("cryptic-throve-lore-edict")

    assert result == "\x1b[38;5;1mcryptic-throve-lore-edict\x1b[0m"
