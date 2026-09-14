"""Tests for In-Guest agent components and cloud config generation."""

from kage.core.instance import InstanceConfig, InstancePorts
from kage.guest.atspi_tree import AccessibilityNode
from kage.guest.cloud_config import CloudConfigGenerator
from kage.guest.shell_exec import GuestShellExecutor


def test_accessibility_node_serialization():
    root = AccessibilityNode(
        node_id="root",
        name="Main Window",
        role="window",
        states=["active", "visible"],
        bounds={"x": 0, "y": 0, "width": 800, "height": 600},
    )
    child = AccessibilityNode(
        node_id="btn_1",
        name="Submit",
        role="push_button",
        states=["enabled"],
        bounds={"x": 50, "y": 50, "width": 100, "height": 30},
    )
    root.children.append(child)

    d = root.to_dict()
    assert d["node_id"] == "root"
    assert len(d["children"]) == 1
    assert d["children"][0]["name"] == "Submit"
    assert child.center == {"x": 100, "y": 65}

    compact = root.to_compact_str()
    assert "[root] <window>" in compact
    assert "[btn_1] <push_button>" in compact


def test_guest_shell_executor():
    res = GuestShellExecutor.execute("echo 'Hello Kage Agent'")
    assert res["exit_code"] == 0
    assert "Hello Kage Agent" in res["stdout"]
    assert not res["timed_out"]


def test_cloud_config_generator():
    ports = InstancePorts(
        ssh=2222,
        vnc=5900,
        novnc=6080,
        api=8000,
        guest_agent=9000,
        qmp=4444,
    )
    inst = InstanceConfig(name="test-cloud-vm", ports=ports)
    user_data = CloudConfigGenerator.generate_user_data(inst)
    meta_data = CloudConfigGenerator.generate_meta_data("test-cloud-vm")

    assert "#cloud-config" in user_data
    assert "kage-guest-agent.service" in user_data
    assert "instance-id: kage-test-cloud-vm" in meta_data
