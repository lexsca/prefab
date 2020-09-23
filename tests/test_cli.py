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
        "--push",
    ]
    cli(args)

    assert caplog.records[-11].message == "[a] quay.io/lexsca/prefab:a Build succeeded"
    assert caplog.records[-3].message == "[a] quay.io/lexsca/prefab:a Pushed"
