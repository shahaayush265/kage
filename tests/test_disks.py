"""Tests for disk manager and qcow2 overlays."""

import subprocess

import pytest

from kage.hypervisor.disks import DiskManager


def test_qcow2_overlay_creation(tmp_path):
    try:
        qemu_img = DiskManager.get_qemu_img_bin()
    except Exception:
        pytest.skip("qemu-img not found")

    base_raw = tmp_path / "base.qcow2"
    # Create empty base qcow2
    subprocess.run(
        [qemu_img, "create", "-f", "qcow2", str(base_raw), "100M"],
        check=True,
    )

    overlay = tmp_path / "overlay.qcow2"
    DiskManager.create_overlay(base_raw, overlay)

    assert overlay.exists()

    info = DiskManager.inspect_disk(overlay)
    assert info["format"] == "qcow2"
    assert "backing-filename" in info or "backing_file" in info or "backing-filename-format" in info
