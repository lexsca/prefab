import pytest

from prefab import errors as E
from prefab.color import color
from prefab.config import Config
from prefab.image import FakeImage, ImageFactory, ImageGraph


def create_graph(targets):
    config = Config({"targets": targets}, "prefab.yaml")
    image_factory = ImageFactory(
        config, "repo", tags=dict(), image_constructor=FakeImage
    )

    return ImageGraph(config, image_factory)


@pytest.fixture(autouse=True)
def disable_color(monkeypatch):
    monkeypatch.setattr(color, "enabled", False)


@pytest.fixture
def a_graph(chdir_fixtures):
    targets = {
        "a": {
            "dockerfile": "Dockerfile.a",
        }
    }

    return create_graph(targets)


@pytest.fixture
def abc_graph(chdir_fixtures):
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
        },
    }

    return create_graph(targets)


def resolve_graph(targets, target):
    config = Config({"targets": targets})
    image_factory = ImageFactory(
        config, "repo", tags=dict(), image_constructor=FakeImage
    )
    image_factory.digests = {target: target for target in targets}
    image_graph = ImageGraph(config, image_factory)

    return image_graph.resolve_target_dependencies(target)


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


def test_build_on_validation_error(caplog, a_graph):
    a_graph.images = {
        "a": FakeImage(
            "repo",
            "tag",
            build_options=dict(),
            loaded=True,
            validate=E.ImageValidationError,
        )
    }
    a_graph.build(["a"])

    assert caplog.messages[2:] == [
        "repo:tag Image loaded",
        "repo:tag ImageValidationError: ",
        "repo:tag build_on_validate_error enabled, continuing...",
        "repo:tag Trying build...",
        "repo:tag build_options {}",
        "repo:tag Build succeeded",
    ]


def test_build_on_allowed_pull_error(caplog, a_graph):
    a_graph.images = {
        "a": FakeImage(
            "repo",
            "tag",
            build_options=dict(),
            loaded=False,
            pull=E.ImageNotFoundError,
        )
    }
    a_graph.build(["a"])

    assert caplog.messages[2:] == [
        "repo:tag Image not loaded",
        "repo:tag Trying pull...",
        "repo:tag ImageNotFoundError: ",
        "repo:tag ImageNotFoundError in allowed_pull_errors, continuing...",
        "repo:tag Trying build...",
        "repo:tag build_options {}",
        "repo:tag Build succeeded",
    ]


def test_target_a_image_pull_stops_graph_traversal(caplog, abc_graph):
    abc_graph.build(["a"])

    assert caplog.messages[-4:] == [
        "\nBuilding [a] target with dependencies: [b], [c]",
        "[a] repo:33cb9338a826 Image not loaded",
        "[a] repo:33cb9338a826 Trying pull...",
        "[a] repo:33cb9338a826 Image validated",
    ]


def test_target_b_image_pull_stops_graph_traversal(caplog, abc_graph):
    abc_graph.resolve_build_targets(["a"])
    abc_graph.images["a"].raise_on.pull = E.ImageNotFoundError
    abc_graph.build(["a"])

    assert caplog.messages[-25:-21] == [
        "\nBuilding [a] target with dependencies: [b], [c]",
        "[a] repo:33cb9338a826 Image not loaded",
        "[a] repo:33cb9338a826 Trying pull...",
        "[a] repo:33cb9338a826 ImageNotFoundError: ",
    ]
    assert caplog.messages[-20:-16] == [
        "[b] repo:a413f339464a Image not loaded",
        "[b] repo:a413f339464a Trying pull...",
        "[b] repo:a413f339464a Image validated",
        "[a] repo:33cb9338a826 Trying build...",
    ]
    assert caplog.messages[-1] == "[a] repo:33cb9338a826 Build succeeded"
