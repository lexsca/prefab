import pytest

from prefab import errors as E
from prefab.config import Config
from prefab.image import FakeImage, ImageFactory, ImageGraph


def resolve_graph(targets, target):
    config = Config({"targets": targets})
    tags = {target: target for target in targets}
    image_factory = ImageFactory(config, "repo", tags, FakeImage)
    image_graph = ImageGraph(config, image_factory)
    images = image_graph.resolve_target_images(target)

    return [image.tag for image in images]


def test_single_target():
    targets = {
        "a": {
            "dockerfile": "Dockerfile.a",
        }
    }

    assert resolve_graph(targets, "a") == ["a"]


def test_line_graph():
    targets = {
        "a": {
            "dockerfile": "Dockerfile.a",
            "depends_on": ["b"],
        },
        "b": {
            "dockerfile": "Dockerfile.b",
            "depends_on": ["c"],
        },
        "c": {
            "dockerfile": "Dockerfile.c",
            "depends_on": ["d"],
        },
        "d": {
            "dockerfile": "Dockerfile.d",
        },
    }

    assert resolve_graph(targets, "a") == ["d", "c", "b", "a"]


def test_diamond_graph():
    targets = {
        "a": {
            "dockerfile": "Dockerfile.a",
            "depends_on": ["b", "c"],
        },
        "b": {
            "dockerfile": "Dockerfile.b",
            "depends_on": ["d"],
        },
        "c": {
            "dockerfile": "Dockerfile.c",
            "depends_on": ["d"],
        },
        "d": {
            "dockerfile": "Dockerfile.d",
        },
    }

    assert resolve_graph(targets, "a") == ["d", "b", "c", "a"]


def test_fake_app_test_graph():
    targets = {
        "test": {
            "dockerfile": "Dockerfile.test",
            "depends_on": ["app", "test_pkgs"],
        },
        "app": {
            "dockerfile": "Dockerfile.app",
            "depends_on": ["base", "app_pkgs"],
        },
        "app_pkgs": {
            "dockerfile": "Dockerfile.app_pkgs",
            "depends_on": ["tools"],
        },
        "test_pkgs": {
            "dockerfile": "Dockerfile.test_pkgs",
            "depends_on": ["tools"],
        },
        "tools": {
            "dockerfile": "Dockerfile.tools",
            "depends_on": ["base"],
        },
        "base": {
            "dockerfile": "Dockerfile.base",
        },
    }

    assert resolve_graph(targets, "test") == [
        "base",
        "tools",
        "app_pkgs",
        "app",
        "test_pkgs",
        "test",
    ]


def test_self_loop():
    targets = {
        "a": {
            "dockerfile": "Dockerfile.a",
            "depends_on": ["a"],
        }
    }

    with pytest.raises(E.TargetCyclicError):
        resolve_graph(targets, "a")


def test_short_loop():
    targets = {
        "a": {
            "dockerfile": "Dockerfile.a",
            "depends_on": ["b"],
        },
        "b": {
            "dockerfile": "Dockerfile.b",
            "depends_on": ["a"],
        },
    }

    for target in targets:
        with pytest.raises(E.TargetCyclicError):
            resolve_graph(targets, target)


def test_long_loop():
    targets = {
        "a": {
            "dockerfile": "Dockerfile.a",
            "depends_on": ["b"],
        },
        "b": {
            "dockerfile": "Dockerfile.b",
            "depends_on": ["c"],
        },
        "c": {
            "dockerfile": "Dockerfile.c",
            "depends_on": ["d"],
        },
        "d": {
            "dockerfile": "Dockerfile.d",
            "depends_on": ["a"],
        },
    }

    for target in targets:
        with pytest.raises(E.TargetCyclicError):
            resolve_graph(targets, target)
