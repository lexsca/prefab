import io
import os

import pytest

from prefab import constants as C
from prefab.image import Image


@pytest.mark.skipif(not os.path.exists("/var/run/docker.sock"), reason="docker missing")
def test_pull_alpine_image():
    image = Image(repo="alpine", tag="latest", build_options={"labels": {}})
    image.pull()

    assert image.loaded


@pytest.mark.skipif(not os.path.exists("/var/run/docker.sock"), reason="docker missing")
def test_build_from_alpine():
    fileobj = io.BytesIO(b"FROM alpine")
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

    assert image.loaded
