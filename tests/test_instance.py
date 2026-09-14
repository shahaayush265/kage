"""Tests for InstanceConfig model, persistence, and state."""

from kage.core.config import get_settings
from kage.core.instance import InstanceConfig, InstancePorts, InstanceStatus


def test_instance_crud(tmp_path, monkeypatch):
    settings = get_settings()
    settings.kage_home = tmp_path / ".kage"
    settings.ensure_directories()

    ports = InstancePorts(
        ssh=2222,
        vnc=5900,
        novnc=6080,
        api=8000,
        guest_agent=9000,
        qmp=4444,
    )
    inst = InstanceConfig(
        name="test-alpha",
        cpus=4,
        memory_mb=8192,
        status=InstanceStatus.RUNNING,
        ports=ports,
        qemu_pid=12345,
    )
    inst.save()

    # Load back
    loaded = InstanceConfig.load("test-alpha")
    assert loaded is not None
    assert loaded.name == "test-alpha"
    assert loaded.cpus == 4
    assert loaded.memory_mb == 8192
    assert loaded.status == InstanceStatus.RUNNING
    assert loaded.ports.ssh == 2222
    assert loaded.qemu_pid == 12345

    # List all
    all_insts = InstanceConfig.list_all()
    assert len(all_insts) == 1
    assert all_insts[0].name == "test-alpha"

    # Destroy
    inst.destroy()
    assert InstanceConfig.load("test-alpha") is None
    assert len(InstanceConfig.list_all()) == 0
