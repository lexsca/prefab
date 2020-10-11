import sys

import pytest

from prefab.cli import main


def test_dry_run(caplog, monkeypatch, prefab_yaml_path, chdir_fixtures):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "calling_path",
            "--dry-run",
            "--monochrome",
            "--config",
            prefab_yaml_path,
            "--repo",
            "quay.io/lexsca/prefab",
            "--target",
            "a:a",
            "--push",
        ],
    )

    with pytest.raises(SystemExit) as system_exit:
        main()

    target_digest_log_message = (
        "[a] target_digest sha256:ede6e265a9d5b9c90b27"
        "c614317bd8d26ff2818390bc3d44479f07a6f6587a7f"
    )

    assert system_exit.value.code == 0
    assert caplog.records[-11].message == "[a] quay.io/lexsca/prefab:a Build succeeded"
    assert caplog.records[-3].message == "[a] quay.io/lexsca/prefab:a Pushed"
    assert target_digest_log_message in caplog.text


def test_tag_duplicates_disallowed(monkeypatch, capsys, prefab_yaml_path):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "calling_path",
            "--config",
            prefab_yaml_path,
            "--repo",
            "quay.io/lexsca/prefab",
            "--target",
            "a:app",
            "--target",
            "b:app",
        ],
    )

    with pytest.raises(SystemExit) as system_exit:
        main()

    assert capsys.readouterr().err.splitlines()[-1] == "Duplicate tag: app"
    assert system_exit.value.code == 2


def test_bad_arg_exits_non_zero(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["calling_path", "--not-valid-arg"])

    with pytest.raises(SystemExit) as system_exit:
        main()

    assert system_exit.value.code == 2


def test_exception_exits_non_zero(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["calling_path", "-r", "repo", "-t", "tag"])

    with pytest.raises(SystemExit) as system_exit:
        main()

    assert system_exit.value.code == 1
