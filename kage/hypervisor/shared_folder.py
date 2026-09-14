"""Host-Guest shared directory mapping via Virtio-9p."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional


class SharedFolderManager:
    """Configures 9p / Virtio-fs directory mapping for QEMU instances."""

    DEFAULT_MOUNT_TAG = "workspace"

    @classmethod
    def get_qemu_args(
        cls,
        host_path: Optional[str],
        mount_tag: str = DEFAULT_MOUNT_TAG,
        dev_id: str = "kage_fs",
    ) -> List[str]:
        """Generate QEMU command line arguments for 9p folder sharing."""
        if not host_path:
            return []

        resolved_path = Path(host_path).expanduser().resolve()
        if not resolved_path.exists():
            resolved_path.mkdir(parents=True, exist_ok=True)

        return [
            "-fsdev",
            f"local,security_model=none,id={dev_id}_dev,path={resolved_path}",
            "-device",
            f"virtio-9p-pci,id={dev_id},fsdev={dev_id}_dev,mount_tag={mount_tag}",
        ]
