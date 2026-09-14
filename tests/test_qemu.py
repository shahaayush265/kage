"""Tests for QEMU command builder and arguments assembly."""

from kage.core.config import get_settings
from kage.core.instance import InstanceConfig, InstancePorts, InstanceStatus
from kage.hypervisor.detector import HypervisorCapabilities
from kage.hypervisor.qemu import QEMURunner


def test_build_qemu_cmd(tmp_path):
    settings = get_settings()
    settings.kage_home = tmp_path / ".kage"
    settings.ensure_directories()

    ports = InstancePorts(
        ssh=2222,
        vnc=5901,
        novnc=6081,
        api=8001,
        guest_agent=9001,
        qmp=4445,
    )
    inst = InstanceConfig(
        name="test-build-vm",
        cpus=2,
        memory_mb=2048,
        status=InstanceStatus.STOPPED,
        ports=ports,
        shared_dir=str(tmp_path / "workspace"),
    )
    inst.ensure_dir()

    mock_caps = HypervisorCapabilities(
        os_type="linux",
        arch="x86_64",
        accel="kvm",
        qemu_bin="/usr/bin/qemu-system-x86_64",
        qemu_img_bin="/usr/bin/qemu-img",
        is_hardware_accelerated=True,
        warnings=[],
    )

    cmd = QEMURunner.build_cmd(inst, capabilities=mock_caps)

    assert "/usr/bin/qemu-system-x86_64" in cmd[0]
    assert "-enable-kvm" in cmd
    assert "-smp" in cmd
    assert "2" in cmd
    assert "-m" in cmd
    assert "2048M" in cmd
    assert "-vga" in cmd
    assert "std" in cmd
    assert "hostfwd=tcp::2222-:22" in " ".join(cmd)
    assert "hostfwd=tcp::9001-:9000" in " ".join(cmd)
    assert "hostfwd=tcp::5901-:5900" in " ".join(cmd)
    assert "-fsdev" in cmd
