import os
import sys

import pytest


LIB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lib"))
FIXTURES_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures"))
sys.path.insert(0, LIB_PATH)


@pytest.fixture
def prefab_yaml_path():
    return os.path.join(FIXTURES_PATH, "prefab.yml")


@pytest.fixture
def chdir_fixtures(monkeypatch):
    monkeypatch.chdir(FIXTURES_PATH)
