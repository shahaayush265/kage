"""Tests for FastAPI Host Bridge API routes."""

from fastapi.testclient import TestClient

from kage.core.config import get_settings
from kage.core.instance import InstanceConfig, InstancePorts, InstanceStatus
from kage.server.app import create_app


def test_api_endpoints(tmp_path, monkeypatch):
    settings = get_settings()
    settings.kage_home = tmp_path / ".kage"
    settings.ensure_directories()

    # Create mock instance
    ports = InstancePorts(
        ssh=2222,
        vnc=5900,
        novnc=6080,
        api=8000,
        guest_agent=9000,
        qmp=4444,
    )
    inst = InstanceConfig(
        name="api-test-vm",
        cpus=2,
        memory_mb=4096,
        status=InstanceStatus.RUNNING,
        ports=ports,
    )
    inst.save()

    app = create_app()
    client = TestClient(app)

    # Test list instances
    resp = client.get("/api/v1/instances")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "api-test-vm"
    assert data[0]["status"] == "Running"

    # Test get instance details
    resp2 = client.get("/api/v1/instances/api-test-vm")
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "api-test-vm"

    # Test VNC info
    resp3 = client.get("/api/v1/instances/api-test-vm/vnc/info")
    assert resp3.status_code == 200
    assert resp3.json()["vnc_port"] == 5900
    assert resp3.json()["novnc_port"] == 6080

    # Test static /
    resp_root = client.get("/")
    assert resp_root.status_code == 200
    assert "Kage" in resp_root.text
