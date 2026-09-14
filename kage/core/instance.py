"""Instance state modeling and persistent lifecycle records."""

from __future__ import annotations

import enum
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from kage.core.config import get_settings


class InstanceStatus(str, enum.Enum):
    STOPPED = "Stopped"
    STARTING = "Starting"
    RUNNING = "Running"
    ERROR = "Error"
    UNKNOWN = "Unknown"


class InstancePorts(BaseModel):
    """Network port mapping for an instance."""

    ssh: int
    vnc: int
    novnc: int
    api: int
    guest_agent: int
    qmp: int

    def to_dict(self) -> Dict[str, int]:
        return {
            "ssh": self.ssh,
            "vnc": self.vnc,
            "novnc": self.novnc,
            "api": self.api,
            "guest_agent": self.guest_agent,
            "qmp": self.qmp,
        }


class InstanceMetrics(BaseModel):
    """Runtime resource consumption metrics."""

    cpu_percent: float = 0.0
    memory_rss_mb: float = 0.0
    uptime_seconds: float = 0.0


class InstanceConfig(BaseModel):
    """Specification and persistent state of a Kage VM instance."""

    name: str
    cpus: int = 2
    memory_mb: int = 4096
    disk_size_gb: int = 20
    shared_dir: Optional[str] = None
    headless: bool = False
    base_image: str = "ubuntu-24.04-minimal-xfce.qcow2"
    status: InstanceStatus = InstanceStatus.STOPPED
    ports: Optional[InstancePorts] = None
    qemu_pid: Optional[int] = None
    api_pid: Optional[int] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_error: Optional[str] = None

    @property
    def instance_dir(self) -> Path:
        settings = get_settings()
        return settings.instances_dir / self.name

    @property
    def state_file(self) -> Path:
        return self.instance_dir / "state.json"

    @property
    def overlay_disk(self) -> Path:
        return self.instance_dir / "overlay.qcow2"

    @property
    def cloud_init_iso(self) -> Path:
        return self.instance_dir / "cidata.iso"

    @property
    def qmp_socket(self) -> Path:
        return self.instance_dir / "qmp.sock"

    @property
    def serial_log(self) -> Path:
        return self.instance_dir / "serial.log"

    @property
    def qemu_log(self) -> Path:
        return self.instance_dir / "qemu.log"

    @property
    def api_log(self) -> Path:
        return self.instance_dir / "api.log"

    def ensure_dir(self) -> None:
        self.instance_dir.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        """Atomically persist instance state to JSON."""
        self.ensure_dir()
        self.updated_at = datetime.now(timezone.utc).isoformat()
        data = self.model_dump(mode="json")
        temp_file = self.instance_dir / "state.json.tmp"
        temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp_file.replace(self.state_file)

    def destroy(self) -> None:
        """Remove instance directory and all overlays/state."""
        if self.instance_dir.exists():
            shutil.rmtree(self.instance_dir, ignore_errors=True)

    @classmethod
    def load(cls, name: str) -> Optional[InstanceConfig]:
        """Load instance configuration from disk."""
        settings = get_settings()
        state_file = settings.instances_dir / name / "state.json"
        if not state_file.exists():
            return None
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            return cls(**data)
        except Exception:
            return None

    @classmethod
    def list_all(cls) -> List[InstanceConfig]:
        """List all registered instances."""
        settings = get_settings()
        instances: List[InstanceConfig] = []
        if not settings.instances_dir.exists():
            return instances

        for item in sorted(settings.instances_dir.iterdir()):
            if item.is_dir():
                state_file = item / "state.json"
                if state_file.exists():
                    try:
                        data = json.loads(state_file.read_text(encoding="utf-8"))
                        instances.append(cls(**data))
                    except Exception:
                        continue
        return instances
