import base64
import binascii
import os
import tempfile

from .color import color
from .logger import logger


def write(env_key: str, dest_path: str, dockerenv_path: str = "/.dockerenv") -> None:
    if os.path.exists(dockerenv_path) and env_key in os.environ:
        _write(env_key, dest_path)


def _write(env_key: str, dest_path: str) -> None:
    try:
        content = base64.b64decode(os.environ.get(env_key, ""))
        if content:
            logger.info(f"Writing env {env_key} to {color.config(dest_path)}")
            return _commit(dest_path, content)
        else:
            logger.warning(
                color.warning(f"Not writing empty env {env_key} to {dest_path}")
            )
    except binascii.Error as error:
        logger.warning(
            color.warning(
                f"Not writing env {env_key} to {dest_path}, base64 decode failed: {error}"
            )
        )
    except Exception as error:
        logger.warning(color.warning(f"{type(error).__name__}: {error}"))


def _commit(dest_path: str, content: bytes) -> None:
    dest_dirname = os.path.dirname(os.path.abspath(dest_path))
    temp_fp, temp_path = tempfile.mkstemp(dir=dest_dirname)

    with open(temp_fp, "wb") as temp:
        temp.write(content)

    os.rename(temp_path, dest_path)
