import pytest

from prefab.cli import cli


def test_dry_run(caplog, prefab_yaml_path):
    args = [
        "--dry-run",
        "--monochrome",
        "--config",
        prefab_yaml_path,
        "--repo",
        "quay.io/lexsca/prefab",
        "--target",
        "a:a",
        "--push",
    ]
    cli(args)
    target_digest_log_message = (
        "[a] target_digest sha256:b65daad29dc4b3d2efec"
        "c50e7cdd1a6f0c1f526670778013a995a5c89627640c"
    )

    assert caplog.records[-11].message == "[a] quay.io/lexsca/prefab:a Build succeeded"
    assert caplog.records[-3].message == "[a] quay.io/lexsca/prefab:a Pushed"
    assert target_digest_log_message in caplog.text


def test_tag_duplicates_disallowed(capsys, prefab_yaml_path):
    args = [
        "--config",
        prefab_yaml_path,
        "--repo",
        "quay.io/lexsca/prefab",
        "--target",
        "a:app",
        "--target",
        "b:app",
    ]
    with pytest.raises(SystemExit) as system_exit:
        cli(args)

    assert capsys.readouterr().err.splitlines()[-1] == "Duplicate tag: app"
    assert system_exit.value.code == 2


def test_bad_arg_exits_non_zero():
    with pytest.raises(SystemExit) as system_exit:
        cli(["--not-valid-arg"])

    assert system_exit.value.code == 2
