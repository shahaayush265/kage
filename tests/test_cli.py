"""Tests for Kage CLI commands."""

from typer.testing import CliRunner

from kage.cli.main import app
from kage.core.config import get_settings
from kage.core.instance import InstanceConfig, InstancePorts, InstanceStatus

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Kage version" in result.output


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Multi-Instance Agentic VM Engine" in result.output
    assert "init" in result.output
    assert "up" in result.output
    assert "list" in result.output
    assert "connect" in result.output


def test_cli_init_skip_download(tmp_path, monkeypatch):
    settings = get_settings()
    settings.kage_home = tmp_path / ".kage"
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["init", "--skip-download"])
    assert result.exit_code == 0
    assert "Host Capabilities" in result.output


def test_cli_list_empty(tmp_path, monkeypatch):
    settings = get_settings()
    settings.kage_home = tmp_path / ".kage"
    settings.ensure_directories()
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No Kage instances found" in result.output


def test_cli_list_with_instance(tmp_path, monkeypatch):
    settings = get_settings()
    settings.kage_home = tmp_path / ".kage"
    settings.ensure_directories()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("COLUMNS", "200")

    ports = InstancePorts(
        ssh=2222,
        vnc=5900,
        novnc=6080,
        api=8000,
        guest_agent=9000,
        qmp=4444,
    )
    inst = InstanceConfig(
        name="cli-test-vm",
        status=InstanceStatus.RUNNING,
        ports=ports,
    )
    inst.save()

    result = runner.invoke(app, ["list"], env={"COLUMNS": "200"})
    assert result.exit_code == 0
    assert "cli-test-vm" in result.output
    assert "2222" in result.output


def test_cli_config_show(tmp_path, monkeypatch):
    settings = get_settings()
    settings.kage_home = tmp_path / ".kage"
    settings.ensure_directories()
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "default_cpus" in result.output


def test_cli_destroy(tmp_path, monkeypatch):
    settings = get_settings()
    settings.kage_home = tmp_path / ".kage"
    settings.ensure_directories()
    monkeypatch.setenv("HOME", str(tmp_path))

    ports = InstancePorts(
        ssh=2222,
        vnc=5900,
        novnc=6080,
        api=8000,
        guest_agent=9000,
        qmp=4444,
    )
    inst = InstanceConfig(
        name="destroy-me-vm",
        status=InstanceStatus.STOPPED,
        ports=ports,
    )
    inst.save()

    result = runner.invoke(app, ["destroy", "destroy-me-vm", "--force"])
    assert result.exit_code == 0
    assert "destroyed cleanly" in result.output
    assert InstanceConfig.load("destroy-me-vm") is None
