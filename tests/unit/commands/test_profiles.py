"""Tests for ``mad profiles create|list|show|delete|apply`` against the real core.

These drive the unmocked engine: ``MAD_CLI_CONFIG_DIR`` points at a scratch dir
(see the ``cli_config_dir`` / ``make_real_instance`` fixtures), so assertions read
the actual profile files and instance ``.env`` written to disk.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mad_cli.app import app
from mad_cli.core.envfile import EnvFile
from mad_cli.core.profiles import list_profiles, load_profile, save_profile


def _seed(name: str, **values: str) -> None:
    env = EnvFile.empty()
    for key, value in values.items():
        env.set(key, value)
    save_profile(name, env)


# ── create ────────────────────────────────────────────────────────────────────
def test_create_empty_profile(cli: CliRunner, cli_config_dir: Path) -> None:
    result = cli.invoke(app, ["profiles", "create", "prod"])
    assert result.exit_code == 0, result.output
    assert list_profiles() == ["prod"]


def test_create_with_set_pairs(cli: CliRunner, cli_config_dir: Path) -> None:
    result = cli.invoke(
        app,
        ["profiles", "create", "prod", "--set", "MAD_AGENT_TIMEOUT_S=900", "--set", "FOO=bar"],
    )
    assert result.exit_code == 0, result.output
    env = load_profile("prod")
    assert env.get("MAD_AGENT_TIMEOUT_S") == "900"
    assert env.get("FOO") == "bar"


def test_create_from_instance_excludes_identity_keys(cli: CliRunner, make_real_instance) -> None:
    make_real_instance(
        name="web",
        env={
            "PUID": "1000",
            "PGID": "1000",
            "MAD_VERSION": "1.2.3",
            "GITHUB_TOKEN": "ghp_copyme",
            "GIT_AUTHOR_NAME": "Ada",
            "MAD_AGENT_TIMEOUT_S": "900",
        },
    )
    result = cli.invoke(app, ["profiles", "create", "prod", "--from-instance", "web"])
    assert result.exit_code == 0, result.output

    env = load_profile("prod")
    # credentials + tuning are copied
    assert env.get("GITHUB_TOKEN") == "ghp_copyme"
    assert env.get("GIT_AUTHOR_NAME") == "Ada"
    assert env.get("MAD_AGENT_TIMEOUT_S") == "900"
    # instance-identity keys are always excluded
    for identity in (
        "MAD_INSTANCE",
        "MAD_HOST_PORT",
        "MAD_DATA_PATH",
        "PUID",
        "PGID",
        "MAD_VERSION",
    ):
        assert env.get(identity) is None
    # the copied secret is never echoed back
    assert "ghp_copyme" not in result.output


def test_create_from_missing_instance_errors(cli: CliRunner, cli_config_dir: Path) -> None:
    result = cli.invoke(app, ["profiles", "create", "prod", "--from-instance", "ghost"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_create_existing_name_errors(cli: CliRunner, cli_config_dir: Path) -> None:
    _seed("prod", A="1")
    result = cli.invoke(app, ["profiles", "create", "prod"])
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_create_bad_set_format_errors(cli: CliRunner, cli_config_dir: Path) -> None:
    result = cli.invoke(app, ["profiles", "create", "prod", "--set", "noequalsign"])
    assert result.exit_code != 0
    assert "KEY=VALUE" in result.output


def test_create_invalid_name_errors(cli: CliRunner, cli_config_dir: Path) -> None:
    result = cli.invoke(app, ["profiles", "create", "Bad_Name"])
    assert result.exit_code != 0
    assert "invalid profile name" in result.output


# ── list ──────────────────────────────────────────────────────────────────────
def test_list_empty_hints_create(cli: CliRunner, cli_config_dir: Path) -> None:
    result = cli.invoke(app, ["profiles", "list"])
    assert result.exit_code == 0, result.output
    assert "profiles create" in result.output


def test_list_shows_profiles_with_counts(cli: CliRunner, cli_config_dir: Path) -> None:
    _seed("alpha", A="1", B="2")
    _seed("beta", C="3")
    result = cli.invoke(app, ["profiles", "list"])
    assert result.exit_code == 0, result.output
    assert "alpha" in result.output
    assert "beta" in result.output


# ── show ──────────────────────────────────────────────────────────────────────
def test_show_masks_secret_values(cli: CliRunner, cli_config_dir: Path) -> None:
    _seed("prod", GITHUB_TOKEN="ghp_dontleakme", GIT_AUTHOR_NAME="Ada")
    result = cli.invoke(app, ["profiles", "show", "prod"])
    assert result.exit_code == 0, result.output
    assert "GITHUB_TOKEN" in result.output
    assert "ghp_dontleakme" not in result.output  # secret masked
    assert "Ada" in result.output  # non-secret shown verbatim


def test_show_reveal_shows_full_value(cli: CliRunner, cli_config_dir: Path) -> None:
    _seed("prod", GITHUB_TOKEN="ghp_dontleakme")
    result = cli.invoke(app, ["profiles", "show", "prod", "--reveal"])
    assert result.exit_code == 0, result.output
    assert "ghp_dontleakme" in result.output


def test_show_missing_errors(cli: CliRunner, cli_config_dir: Path) -> None:
    result = cli.invoke(app, ["profiles", "show", "ghost"])
    assert result.exit_code != 0
    assert "not found" in result.output


# ── delete ────────────────────────────────────────────────────────────────────
def test_delete_yes_removes_profile(cli: CliRunner, cli_config_dir: Path) -> None:
    _seed("prod", A="1")
    result = cli.invoke(app, ["profiles", "delete", "prod", "--yes"])
    assert result.exit_code == 0, result.output
    assert list_profiles() == []


def test_delete_without_confirmation_aborts(cli: CliRunner, cli_config_dir: Path) -> None:
    # Non-TTY: confirm() returns its default (False), so nothing is deleted.
    _seed("prod", A="1")
    result = cli.invoke(app, ["profiles", "delete", "prod"])
    assert result.exit_code == 0, result.output
    assert "Aborted" in result.output
    assert list_profiles() == ["prod"]


def test_delete_missing_errors(cli: CliRunner, cli_config_dir: Path) -> None:
    result = cli.invoke(app, ["profiles", "delete", "ghost", "--yes"])
    assert result.exit_code != 0
    assert "not found" in result.output


# ── apply ─────────────────────────────────────────────────────────────────────
def test_apply_overlays_profile_onto_instance(cli: CliRunner, make_real_instance) -> None:
    config_dir = make_real_instance(name="web")
    _seed("prod", GITHUB_TOKEN="ghp_new", GIT_AUTHOR_NAME="Grace")

    result = cli.invoke(app, ["profiles", "apply", "prod", "web"])
    assert result.exit_code == 0, result.output

    env = EnvFile.load(config_dir / ".env")
    assert env.get("GITHUB_TOKEN") == "ghp_new"
    assert env.get("GIT_AUTHOR_NAME") == "Grace"
    # instance identity is untouched (the profile never carries it)
    assert env.get("MAD_INSTANCE") == "web"
    assert "mad restart web" in result.output


def test_apply_missing_profile_errors(cli: CliRunner, make_real_instance) -> None:
    make_real_instance(name="web")
    result = cli.invoke(app, ["profiles", "apply", "ghost", "web"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_apply_missing_instance_errors(cli: CliRunner, cli_config_dir: Path) -> None:
    _seed("prod", A="1")
    result = cli.invoke(app, ["profiles", "apply", "prod", "ghost"])
    assert result.exit_code != 0
    assert "not found" in result.output
