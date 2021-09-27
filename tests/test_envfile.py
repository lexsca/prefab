import base64
import os
import tempfile

import pytest

from prefab import envfile
from prefab.color import color


ENV_KEY = "REGISTRY_AUTH"


@pytest.fixture(autouse=True)
def disable_color(monkeypatch):
    monkeypatch.setattr(color, "enabled", False)


@pytest.fixture
def auth_env_key(monkeypatch):
    monkeypatch.setenv(ENV_KEY, base64.b64encode(b'{"auths":{}}\n').decode())


@pytest.fixture
def bad_env_key(monkeypatch):
    monkeypatch.setenv(ENV_KEY, "A" * 7)


@pytest.fixture
def empty_env_key(monkeypatch):
    monkeypatch.setenv(ENV_KEY, "")


@pytest.fixture
def dest_path():
    dest = tempfile.NamedTemporaryFile()
    dest.close()
    yield dest.name

    if os.path.exists(dest.name):
        os.unlink(dest.name)


@pytest.fixture
def dockerenv_path():
    dockerenv = tempfile.NamedTemporaryFile()
    yield dockerenv.name


@pytest.fixture
def no_dockerenv_path():
    dockerenv = tempfile.NamedTemporaryFile()
    dockerenv.close()
    yield dockerenv.name


def test_write_simple(auth_env_key, dest_path, dockerenv_path):
    envfile.write(ENV_KEY, dest_path, dockerenv_path)

    with open(dest_path) as dest:
        assert dest.read() == '{"auths":{}}\n'
    assert os.path.exists(dockerenv_path)


def test_no_write_if_dockernv_does_not_exist(
    auth_env_key, dest_path, no_dockerenv_path
):
    envfile.write(ENV_KEY, dest_path, no_dockerenv_path)

    assert not os.path.exists(dest_path)
    assert not os.path.exists(no_dockerenv_path)


def test_no_write_if_env_var_empty(empty_env_key, dest_path, dockerenv_path, caplog):
    envfile.write(ENV_KEY, dest_path, dockerenv_path)

    assert not os.path.exists(dest_path)
    assert os.path.exists(dockerenv_path)
    assert f"Not writing empty env REGISTRY_AUTH to {dest_path}" in caplog.text


def test_write_handles_decode_error(bad_env_key, dest_path, dockerenv_path, caplog):
    envfile.write(ENV_KEY, dest_path, dockerenv_path)

    assert not os.path.exists(dest_path)
    assert (
        f"Not writing env REGISTRY_AUTH to {dest_path}, base64 decode failed: Incorrect padding"
        in caplog.text
    )


def test_write_handles_io_error(auth_env_key, dockerenv_path, caplog):
    envfile.write(ENV_KEY, "/sys/is_a_ro_fs", dockerenv_path)

    assert "Failed to write REGISTRY_AUTH to /sys/is_a_ro_fs" in caplog.text
