"""QEMU command construction, VM execution, and hypervisor lifecycle management."""

from __future__ import annotations

from typing import List, Optional

from kage.core.instance import InstanceConfig, InstanceStatus
from kage.core.process import ProcessManager
from kage.hypervisor.detector import HypervisorCapabilities, HypervisorDetector
from kage.hypervisor.qmp import graceful_shutdown
from kage.hypervisor.shared_folder import SharedFolderManager


class QEMURunner:
    """Orchestrates QEMU subprocess launching, argument assembly, and teardown."""

    @classmethod
    def build_cmd(
        cls,
        instance: InstanceConfig,
        capabilities: Optional[HypervisorCapabilities] = None,
    ) -> List[str]:
        """Assemble the complete QEMU invocation command line."""
        caps = capabilities or HypervisorDetector.detect()
        if not caps.qemu_bin:
            raise RuntimeError("Cannot construct QEMU command: QEMU binary not found on host")

        if not instance.ports:
            raise ValueError(f"Instance '{instance.name}' has no allocated ports")

        cmd: List[str] = [caps.qemu_bin]

        # Machine and Accelerator configuration
        if caps.accel == "kvm":
            cmd.extend(["-enable-kvm", "-cpu", "host"])
        elif caps.accel == "hvf":
            cmd.extend(["-accel", "hvf", "-cpu", "host"])
        else:
            cmd.extend(["-accel", "tcg", "-cpu", "max"])

        # Resource limits
        cmd.extend(["-smp", str(instance.cpus)])
        cmd.extend(["-m", f"{instance.memory_mb}M"])

        # Storage: Primary Qcow2 CoW Overlay
        cmd.extend(
            [
                "-drive",
                f"file={instance.overlay_disk.resolve()},format=qcow2,if=virtio,cache=writeback",
            ]
        )

        # Cloud-init Seed ISO if present
        if instance.cloud_init_iso.exists():
            cmd.extend(
                [
                    "-drive",
                    f"file={instance.cloud_init_iso.resolve()},media=cdrom,readonly=on",
                ]
            )

        # Networking: User-mode NAT with dynamic host port forwardings
        # Forward SSH (guest 22) and Guest Agent (guest 9000)
        p = instance.ports
        net_hostfwd = f"user,id=net0,hostfwd=tcp::{p.ssh}-:22,hostfwd=tcp::{p.guest_agent}-:9000"
        cmd.extend(
            [
                "-netdev",
                net_hostfwd,
                "-device",
                "virtio-net-pci,netdev=net0",
            ]
        )

        # Display and VNC configuration
        vnc_display_num = max(0, p.vnc - 5900)
        cmd.extend(
            [
                "-vnc",
                f"127.0.0.1:{vnc_display_num}",
                "-vga",
                "std",
                "-usb",
                "-device",
                "usb-tablet",
            ]
        )

        # Fast RNG device
        cmd.extend(["-device", "virtio-rng-pci"])

        # QMP Control Socket
        # Remove stale socket if exists
        if instance.qmp_socket.exists():
            try:
                instance.qmp_socket.unlink()
            except Exception:
                pass
        cmd.extend(
            [
                "-qmp",
                f"unix:{instance.qmp_socket.resolve()},server,nowait",
            ]
        )

        # Serial Console Log
        cmd.extend(
            [
                "-serial",
                f"file:{instance.serial_log.resolve()}",
            ]
        )

        # Shared Folder (Virtio-9p)
        if instance.shared_dir:
            shared_args = SharedFolderManager.get_qemu_args(
                host_path=instance.shared_dir,
                mount_tag="workspace",
            )
            cmd.extend(shared_args)

        return cmd

    @classmethod
    def start(
        cls,
        instance: InstanceConfig,
        capabilities: Optional[HypervisorCapabilities] = None,
    ) -> int:
        """Start VM instance daemonized in background, returning PID."""
        instance.ensure_dir()
        cmd = cls.build_cmd(instance, capabilities)

        pid = ProcessManager.spawn_daemon(
            cmd=cmd,
            log_file=instance.qemu_log,
            cwd=instance.instance_dir,
        )

        instance.qemu_pid = pid
        instance.status = InstanceStatus.STARTING
        instance.save()
        return pid

    @classmethod
    def stop(cls, instance: InstanceConfig, timeout_seconds: float = 8.0) -> bool:
        """Gracefully halt VM via QMP, falling back to process termination."""
        # 1. Attempt ACPI shutdown via QMP
        if instance.qmp_socket.exists():
            try:
                graceful_shutdown(instance.qmp_socket, timeout_seconds=timeout_seconds / 2)
            except Exception:
                pass

        # 2. Terminate PID if still active
        if instance.qemu_pid and ProcessManager.is_alive(instance.qemu_pid):
            ProcessManager.stop_process(instance.qemu_pid, timeout_seconds=timeout_seconds / 2)

        # 3. Clean up QMP socket
        if instance.qmp_socket.exists():
            try:
                instance.qmp_socket.unlink()
            except Exception:
                pass

        instance.status = InstanceStatus.STOPPED
        instance.qemu_pid = None
        instance.save()
        return True
