"""Implementation of `kage init` CLI command."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kage.core.config import get_settings
from kage.hypervisor.detector import HypervisorDetector
from kage.hypervisor.image_manager import ImageManager

console = Console()


def init_command(
    force: bool = typer.Option(
        False, "--force", "-f", help="Force re-initialization and directory reset."
    ),
    skip_download: bool = typer.Option(
        False, "--skip-download", help="Skip downloading base Ubuntu cloud image."
    ),
    image_url: Optional[str] = typer.Option(
        None, "--image-url", help="Custom base image download URL."
    ),
) -> None:
    """Validate host virtualization and provision Kage environment."""
    console.print(
        Panel.fit("[bold cyan]Kage Virtualization & Environment Initialization[/bold cyan]")
    )

    settings = get_settings()
    settings.ensure_directories()
    settings.save()
    console.print(
        f"[green]✓[/green] Storage directories initialized at [bold]{settings.kage_home}[/bold]"
    )

    # 1. Detect virtualization capabilities
    with console.status("[bold blue]Checking host virtualization capabilities...[/bold blue]"):
        caps = HypervisorDetector.detect()

    table = Table(title="Host Capabilities", show_header=True, header_style="bold magenta")
    table.add_column("Property", style="dim")
    table.add_column("Value")

    table.add_row("Operating System", caps.os_type.capitalize())
    table.add_row("Architecture", caps.arch)
    table.add_row(
        "Accelerator",
        f"[bold green]{caps.accel.upper()}[/bold green]"
        if caps.is_hardware_accelerated
        else f"[yellow]{caps.accel.upper()} (Emulation)[/yellow]",
    )
    table.add_row(
        "Hardware Acceleration",
        "Enabled" if caps.is_hardware_accelerated else "Disabled / Unavailable",
    )
    table.add_row("QEMU Binary", caps.qemu_bin or "[red]Not found[/red]")
    table.add_row("qemu-img Binary", caps.qemu_img_bin or "[red]Not found[/red]")

    console.print(table)

    if caps.warnings:
        for warn in caps.warnings:
            console.print(f"[yellow]⚠ Warning:[/yellow] {warn}")

    if not caps.is_usable:
        console.print(
            "[bold red]Error: Essential QEMU binaries are missing. Please install qemu and qemu-utils.[/bold red]"
        )
        raise typer.Exit(code=1)

    # 2. Base image check and provisioning
    base_img_path = ImageManager.get_base_image_path()
    if base_img_path.exists() and not force:
        size_mb = round(base_img_path.stat().st_size / (1024 * 1024), 1)
        console.print(
            f"[green]✓[/green] Base image already present at [bold]{base_img_path}[/bold] ({size_mb} MB)"
        )
    elif skip_download:
        console.print(
            f"[yellow]ℹ Skipping base image download. Ensure base image is placed at '{base_img_path}'.[/yellow]"
        )
    else:
        console.print(f"[blue]Base image not found at {base_img_path}.[/blue]")
        target_url = image_url or settings.base_image_url
        console.print(f"Downloading base Ubuntu image from [dim]{target_url}[/dim]...")
        try:
            ImageManager.download_base_image(
                url=target_url, destination=base_img_path, show_progress=True
            )
            console.print(
                f"[bold green]✓[/bold green] Base image downloaded and cached successfully at {base_img_path}"
            )
        except Exception as e:
            console.print(f"[red]Failed to download base image: {e}[/red]")
            console.print(
                "[dim]You can manually place a bootable Ubuntu qcow2 image in ~/.kage/images/ or run kage init --image-url <url>[/dim]"
            )

    console.print(
        "\n[bold green]✨ Kage is initialized and ready to spawn VM instances![/bold green]"
    )
    console.print("Run [bold cyan]kage up my-agent-vm[/bold cyan] to launch your first instance.")
