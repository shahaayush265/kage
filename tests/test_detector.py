"""Tests for hypervisor capability detector."""

from kage.hypervisor.detector import HypervisorDetector


def test_detector_basic():
    caps = HypervisorDetector.detect()
    assert caps.os_type in ("linux", "darwin", "windows")
    assert caps.arch in ("x86_64", "aarch64", "arm64")
    assert caps.accel in ("kvm", "hvf", "tcg")
    assert isinstance(caps.warnings, list)
