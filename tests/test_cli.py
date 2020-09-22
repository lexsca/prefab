from prefab.cli import cli


def test_dry_run(caplog, prefab_yaml_path):
    args = [
        "--dry-run",
        "--config",
        prefab_yaml_path,
        "--repo",
        "quay.io/lexsca/prefab",
        "--target",
        "a:a",
    ]
    cli(args)
    expected = "[a] quay.io/lexsca/prefab:a Build succeeded"
    result = caplog.records[-2].message

    assert result == expected
