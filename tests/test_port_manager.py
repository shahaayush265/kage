"""Tests for port allocation and collision prevention."""

from kage.core.instance import InstanceConfig, InstanceStatus
from kage.core.port_manager import PortAllocator


def test_is_port_available():
    # An ephemeral high port should be available
    assert PortAllocator.is_port_available(39123)


def test_allocate_ports(tmp_path, monkeypatch):
    # Mock settings to use tmp_path
    monkeypatch.setenv("HOME", str(tmp_path))
    from kage.core.config import get_settings

    settings = get_settings()
    settings.kage_home = tmp_path / ".kage"
    settings.ensure_directories()

    # Allocate for instance 1
    ports1 = PortAllocator.allocate("vm-1")
    assert ports1.ssh >= 2222
    assert ports1.vnc >= 5900
    assert ports1.novnc >= 6080
    assert ports1.api >= 8000
    assert ports1.guest_agent >= 9000
    assert ports1.qmp >= 4444

    # Save vm-1
    inst1 = InstanceConfig(
        name="vm-1",
        status=InstanceStatus.RUNNING,
        ports=ports1,
    )
    inst1.save()

    # Allocate for instance 2 - must not collide with vm-1
    ports2 = PortAllocator.allocate("vm-2")
    assert ports2.ssh != ports1.ssh
    assert ports2.vnc != ports1.vnc
    assert ports2.novnc != ports1.novnc
    assert ports2.api != ports1.api
    assert ports2.guest_agent != ports1.guest_agent
    assert ports2.qmp != ports1.qmp
