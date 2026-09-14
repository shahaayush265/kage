"""Qcow2 Copy-on-Write (CoW) overlay disk management and backing chain validation."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


class DiskManager:
    """Manages QEMU qcow2 copy-on-write overlay disks."""

    @staticmethod
    def get_qemu_img_bin() -> str:
        qemu_img = shutil.which("qemu-img")
        if not qemu_img:
            raise RuntimeError("qemu-img binary not found in PATH")
        return qemu_img

    @classmethod
    def create_overlay(
        cls,
        base_image: Path,
        overlay_path: Path,
        size_gb: Optional[int] = None,
    ) -> Path:
        """Create a lightweight copy-on-write qcow2 overlay based on base_image."""
        qemu_img = cls.get_qemu_img_bin()

        if not base_image.exists():
            raise FileNotFoundError(f"Base image not found at '{base_image}'")

        overlay_path.parent.mkdir(parents=True, exist_ok=True)

        # qemu-img create -f qcow2 -b <base_image> -F qcow2 <overlay_path>
        # Use absolute path for backing file
        cmd = [
            qemu_img,
            "create",
            "-f",
            "qcow2",
            "-b",
            str(base_image.resolve()),
            "-F",
            "qcow2",
            str(overlay_path.resolve()),
        ]

        if size_gb is not None:
            cmd.append(f"{size_gb}G")

        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(f"Failed to create qcow2 overlay: {res.stderr.strip()}")

        return overlay_path

    @classmethod
    def inspect_disk(cls, disk_path: Path) -> Dict[str, Any]:
        """Inspect disk image details via `qemu-img info --output=json`."""
        qemu_img = cls.get_qemu_img_bin()

        if not disk_path.exists():
            raise FileNotFoundError(f"Disk image not found at '{disk_path}'")

        cmd = [qemu_img, "info", "--output=json", str(disk_path.resolve())]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(f"Failed to inspect disk '{disk_path}': {res.stderr.strip()}")

        try:
            return json.loads(res.stdout)
        except Exception as e:
            raise RuntimeError(f"Could not parse qemu-img output as JSON: {e}")
