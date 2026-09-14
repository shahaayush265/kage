"""Host virtualization capability detection (KVM, HVF, TCG, QEMU binaries)."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class HypervisorCapabilities:
    """Detected virtualization capabilities on the host."""

    os_type: str  # "linux", "darwin", "windows"
    arch: str  # "x86_64", "arm64", etc.
    accel: str  # "kvm", "hvf", "tcg"
    qemu_bin: Optional[str]
    qemu_img_bin: Optional[str]
    is_hardware_accelerated: bool
    warnings: List[str]

    @property
    def is_usable(self) -> bool:
        return self.qemu_bin is not None and self.qemu_img_bin is not None


class HypervisorDetector:
    """Detects available hypervisors and QEMU binaries."""

    @classmethod
    def detect(cls) -> HypervisorCapabilities:
        system = platform.system().lower()
        machine = platform.machine().lower()

        # Normalize architecture
        if machine in ("x86_64", "amd64"):
            arch = "x86_64"
        elif machine in ("aarch64", "arm64"):
            arch = "aarch64"
        else:
            arch = machine

        warnings: List[str] = []

        # Find QEMU binary
        qemu_target = f"qemu-system-{arch}"
        qemu_bin = shutil.which(qemu_target)
        if not qemu_bin:
            # Fallback check for x86_64
            qemu_bin = shutil.which("qemu-system-x86_64")
        if not qemu_bin:
            warnings.append(f"QEMU system binary '{qemu_target}' not found. Please install QEMU.")

        # Find qemu-img
        qemu_img_bin = shutil.which("qemu-img")
        if not qemu_img_bin:
            warnings.append("qemu-img binary not found. Please install QEMU utilities.")

        accel = "tcg"
        is_hw = False

        if system == "linux":
            if os.path.exists("/dev/kvm"):
                if os.access("/dev/kvm", os.R_OK | os.W_OK):
                    accel = "kvm"
                    is_hw = True
                else:
                    warnings.append(
                        "KVM is present at /dev/kvm, but the current user does not have read/write access. "
                        "Add your user to the 'kvm' group: sudo usermod -aG kvm $USER"
                    )
            else:
                warnings.append(
                    "/dev/kvm not found. Hardware virtualization (VT-x/AMD-V) might be disabled in BIOS or nested virtualization is off. Falling back to TCG emulation."
                )
        elif system == "darwin":
            # Check macOS Hypervisor.framework support
            try:
                out = subprocess.check_output(
                    ["sysctl", "-n", "kern.hv_support"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()
                if out == "1":
                    accel = "hvf"
                    is_hw = True
                else:
                    warnings.append(
                        "macOS Hypervisor.framework not supported on this CPU. Falling back to TCG."
                    )
            except Exception:
                warnings.append("Could not query macOS Hypervisor support. Falling back to TCG.")
        else:
            warnings.append(f"Operating system '{system}' is not officially supported. Using TCG.")

        return HypervisorCapabilities(
            os_type=system,
            arch=arch,
            accel=accel,
            qemu_bin=qemu_bin,
            qemu_img_bin=qemu_img_bin,
            is_hardware_accelerated=is_hw,
            warnings=warnings,
        )
