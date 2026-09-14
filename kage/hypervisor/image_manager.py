"""Ubuntu base image downloader, cache manager, and verification."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, Optional

import httpx
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from kage.core.config import get_settings


class ImageManager:
    """Manages base Ubuntu VM images in ~/.kage/images/."""

    @classmethod
    def get_base_image_path(cls, image_name: Optional[str] = None) -> Path:
        settings = get_settings()
        name = image_name or settings.default_base_image
        return settings.images_dir / name

    @classmethod
    def is_image_available(cls, image_name: Optional[str] = None) -> bool:
        path = cls.get_base_image_path(image_name)
        return path.exists() and path.stat().st_size > 1024 * 1024

    @classmethod
    def download_base_image(
        cls,
        url: Optional[str] = None,
        destination: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        show_progress: bool = True,
    ) -> Path:
        """Download base cloud image with rich real-time progress reporting."""
        settings = get_settings()
        target_url = url or settings.base_image_url
        dest = destination or cls.get_base_image_path()
        dest.parent.mkdir(parents=True, exist_ok=True)

        temp_dest = dest.with_suffix(".download.tmp")

        timeout_config = httpx.Timeout(connect=30.0, read=600.0, write=60.0, pool=60.0)

        with httpx.Client(follow_redirects=True, timeout=timeout_config) as client:
            with client.stream("GET", target_url) as response:
                response.raise_for_status()
                total_size = int(response.headers.get("content-length", 0))

                if show_progress:
                    with Progress(
                        SpinnerColumn(spinner_name="dots"),
                        TextColumn("[bold cyan]{task.description}"),
                        BarColumn(
                            bar_width=35, complete_style="bold green", finished_style="green"
                        ),
                        TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
                        DownloadColumn(),
                        TransferSpeedColumn(),
                        TimeRemainingColumn(),
                        TimeElapsedColumn(),
                    ) as progress:
                        task_id = progress.add_task(
                            f"Downloading {dest.name}",
                            total=total_size if total_size > 0 else None,
                        )
                        with open(temp_dest, "wb") as f:
                            downloaded = 0
                            for chunk in response.iter_bytes(chunk_size=131072):
                                f.write(chunk)
                                downloaded += len(chunk)
                                progress.update(task_id, advance=len(chunk))
                                if progress_callback:
                                    progress_callback(downloaded, total_size)
                else:
                    with open(temp_dest, "wb") as f:
                        downloaded = 0
                        for chunk in response.iter_bytes(chunk_size=131072):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback:
                                progress_callback(downloaded, total_size)

        temp_dest.replace(dest)
        return dest

    @staticmethod
    def calculate_sha256(file_path: Path) -> str:
        """Compute SHA-256 hash of a file with progress updates."""
        hasher = hashlib.sha256()
        total_size = file_path.stat().st_size
        with Progress(
            SpinnerColumn(),
            TextColumn("[dim]Verifying image integrity (SHA-256)...[/dim]"),
            BarColumn(bar_width=30),
            DownloadColumn(),
        ) as progress:
            task_id = progress.add_task("Verifying", total=total_size)
            with open(file_path, "rb") as f:
                while chunk := f.read(262144):
                    hasher.update(chunk)
                    progress.update(task_id, advance=len(chunk))
        return hasher.hexdigest()
