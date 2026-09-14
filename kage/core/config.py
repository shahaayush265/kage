"""Global configuration, provider registry, and path management for Kage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """Configuration for a specific AI model provider."""

    name: str  # e.g. "omniroute", "anthropic", "openai", "deepseek", "ollama", "custom"
    display_name: str = ""
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    models: List[str] = Field(default_factory=list)
    default_model: Optional[str] = None


class KageSettings(BaseModel):
    """Global configuration settings for Kage engine."""

    version: str = "0.1.0"
    kage_home: Path = Field(default_factory=lambda: Path.home() / ".kage")
    default_cpus: int = 2
    default_memory_mb: int = 4096
    default_disk_size_gb: int = 20
    default_base_image: str = "ubuntu-24.04-minimal-xfce.qcow2"
    base_image_url: str = "https://cloud-images.ubuntu.com/minimal/releases/noble/release/ubuntu-24.04-minimal-cloudimg-amd64.img"
    active_provider: str = "omniroute"
    default_model: str = "omniroute/claude-3-7-sonnet"
    default_host: str = "127.0.0.1"
    providers: Dict[str, ProviderConfig] = Field(default_factory=dict)

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

    def get_provider(self, name: Optional[str] = None) -> Optional[ProviderConfig]:
        """Get provider config by name or active provider."""
        p_name = name or self.active_provider
        return self.providers.get(p_name.lower())

    def set_provider(self, provider_config: ProviderConfig, set_active: bool = True) -> None:
        """Register or update a provider configuration."""
        self.providers[provider_config.name.lower()] = provider_config
        if set_active:
            self.active_provider = provider_config.name.lower()
            if provider_config.default_model:
                self.default_model = provider_config.default_model
        self.save()

    def get_active_model_details(self) -> tuple[str, Optional[str], Optional[str]]:
        """Resolve (model_name, api_key, api_base) for active provider."""
        provider = self.get_provider()
        model = self.default_model
        api_key = provider.api_key if provider else None
        api_base = provider.api_base if provider else None
        return model, api_key, api_base

    def save(self) -> None:
        """Save settings to config.json."""
        self.ensure_directories()
        data = self.model_dump(mode="json")
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
