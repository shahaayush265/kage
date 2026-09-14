"""Global configuration and path management for Kage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class KageSettings(BaseModel):
    """Global configuration settings for Kage engine."""

    version: str = "0.1.0"
    kage_home: Path = Field(default_factory=lambda: Path.home() / ".kage")
    default_cpus: int = 2
    default_memory_mb: int = 4096
    default_disk_size_gb: int = 20
    default_base_image: str = "ubuntu-24.04-minimal-xfce.qcow2"
    base_image_url: str = "https://cloud-images.ubuntu.com/minimal/releases/noble/release/ubuntu-24.04-minimal-cloudimg-amd64.img"
    default_model: str = "anthropic/claude-3-7-sonnet-20250219"
    default_host: str = "127.0.0.1"

    @property
    def instances_dir(self) -> Path:
        return self.kage_home / "instances"

    @property
    def images_dir(self) -> Path:
        return self.kage_home / "images"

    @property
    def logs_dir(self) -> Path:
        return self.kage_home / "logs"

    @property
    def config_file(self) -> Path:
        return self.kage_home / "config.json"

    def ensure_directories(self) -> None:
        """Create all essential storage directories."""
        self.kage_home.mkdir(parents=True, exist_ok=True)
        self.instances_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        """Save settings to config.json."""
        self.ensure_directories()
        data = self.model_dump(mode="json")
        # Convert Paths to strings
        for k, v in data.items():
            if isinstance(v, Path):
                data[k] = str(v)
        self.config_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> KageSettings:
        """Load settings from config file or return default."""
        target = config_path or (Path.home() / ".kage" / "config.json")
        if target.exists():
            try:
                data = json.loads(target.read_text(encoding="utf-8"))
                return cls(**data)
            except Exception:
                pass
        settings = cls()
        return settings


_global_settings: Optional[KageSettings] = None


def get_settings() -> KageSettings:
    """Get singleton KageSettings instance."""
    global _global_settings
    if _global_settings is None:
        _global_settings = KageSettings.load()
    return _global_settings


def get_or_create_ssh_key() -> tuple[Path, str]:
    """Ensure a dedicated host SSH keypair exists in ~/.kage/kage_key."""
    settings = get_settings()
    settings.ensure_directories()
    priv_key = settings.kage_home / "kage_key"
    pub_key = settings.kage_home / "kage_key.pub"

    if not priv_key.exists() or not pub_key.exists():
        try:
            import subprocess

            subprocess.run(
                [
                    "ssh-keygen",
                    "-t",
                    "ed25519",
                    "-N",
                    "",
                    "-f",
                    str(priv_key),
                    "-C",
                    "kage-agent",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            priv_key.chmod(0o600)
        except Exception:
            pass

    pub_str = pub_key.read_text().strip() if pub_key.exists() else ""
    return priv_key, pub_str
