import io
import os

import pytest

from prefab import constants as C
from prefab.image import Image


@pytest.mark.skipif(not os.path.exists("/var/run/docker.sock"), reason="docker missing")
def test_pull_prefab_none():
    build_options = {"labels": {"prefab.target": "none"}}
    image = Image(repo="quay.io/lexsca/prefab", tag="none", build_options=build_options)
    image.pull()
    image.validate()
    image.remove()

    assert image.loaded


@pytest.mark.skipif(not os.path.exists("/var/run/docker.sock"), reason="docker missing")
def test_build_from_scratch():
    fileobj = io.BytesIO(b"FROM scratch")
    build_options = {
        **C.DEFAULT_BUILD_OPTIONS,
        **{
            "fileobj": fileobj,
            "decode": True,
            "labels": {"pacifist-kept": "chewy-uncouth"},
            "tag": "sunlit-sing:aspect-workbag",
        },
    }
    image = Image(repo="sunlit-sing", tag="aspect-workbag", build_options=build_options)
    image.build()
    image.validate()
    image.remove()

    assert image.loaded


@pytest.mark.skipif(not os.path.exists("/var/run/docker.sock"), reason="docker missing")
def test_loaded_does_not_raise_ImageNotFoundError():
    image = Image(repo="scratch", tag=None, build_options={})

    assert not image.loaded
