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
        False, "--force", "-f", help="Force re-initialization and re-download base image."
    ),
    skip_download: bool = typer.Option(
        False, "--skip-download", help="Skip downloading base Ubuntu cloud image."
    ),
    image_url: Optional[str] = typer.Option(
        None, "--image-url", help="Custom base image download URL."
    ),
) -> None:
    """Validate host virtualization capabilities and provision base images."""
    console.print(
        Panel.fit(
            "[bold cyan]Kage Virtualization & Environment Initialization[/bold cyan]",
            border_style="cyan",
        )
    )

    settings = get_settings()

    # 1. Detect virtualization capabilities
    console.print(
        "\n[bold cyan][1/3][/bold cyan] [bold]Detecting host virtualization capabilities...[/bold]"
    )
    with console.status(
        "[bold blue]Inspecting hypervisor & CPU features...[/bold blue]", spinner="dots"
    ):
        caps = HypervisorDetector.detect()

    table = Table(show_header=True, header_style="bold magenta", border_style="dim")
    table.add_column("Property", style="dim")
    table.add_column("Status / Value")

    table.add_row("Operating System", caps.os_type.capitalize())
    table.add_row("Architecture", caps.arch)
    table.add_row(
        "Hypervisor Accel",
        f"[bold green]{caps.accel.upper()} (Hardware Accelerated)[/bold green]"
        if caps.is_hardware_accelerated
        else f"[yellow]{caps.accel.upper()} (Software Emulation)[/yellow]",
    )
    table.add_row("QEMU Binary", caps.qemu_bin or "[red]Not found[/red]")
    table.add_row("qemu-img Utility", caps.qemu_img_bin or "[red]Not found[/red]")

    console.print(table)

    if caps.warnings:
        for warn in caps.warnings:
            console.print(f"  [yellow]⚠ Warning:[/yellow] {warn}")

    if not caps.is_usable:
        console.print(
            "\n[bold red]Error: Essential QEMU binaries are missing. Please install qemu and qemu-utils before proceeding.[/bold red]"
        )
        raise typer.Exit(code=1)

    # 2. Workspace Directories
    console.print(
        "\n[bold cyan][2/3][/bold cyan] [bold]Configuring local storage directories...[/bold]"
    )
    settings.ensure_directories()
    settings.save()
    console.print(f"  [green]✓[/green] Storage configured at [bold]{settings.kage_home}[/bold]")
    console.print(f"    • Instances: [dim]{settings.instances_dir}[/dim]")
    console.print(f"    • Images:    [dim]{settings.images_dir}[/dim]")
    console.print(f"    • Logs:      [dim]{settings.logs_dir}[/dim]")

    # 3. Base image provisioning
    console.print(
        "\n[bold cyan][3/3][/bold cyan] [bold]Provisioning base Ubuntu 24.04 minimal image...[/bold]"
    )
    base_img_path = ImageManager.get_base_image_path()

    if base_img_path.exists() and not force:
        size_mb = round(base_img_path.stat().st_size / (1024 * 1024), 1)
        console.print(
            f"  [green]✓[/green] Base image already cached at [bold]{base_img_path}[/bold] ({size_mb} MB)"
        )
    elif skip_download:
        console.print(
            f"  [yellow]ℹ[/yellow] Skipped download. Place your custom bootable base image at [bold]{base_img_path}[/bold]"
        )
    else:
        target_url = image_url or settings.base_image_url
        console.print(f"  • Source URL: [dim]{target_url}[/dim]")
        console.print(f"  • Destination: [dim]{base_img_path}[/dim]\n")
        try:
            ImageManager.download_base_image(
                url=target_url, destination=base_img_path, show_progress=True
            )
            size_mb = round(base_img_path.stat().st_size / (1024 * 1024), 1)
            console.print(
                f"\n  [bold green]✓[/bold green] Base image downloaded and cached successfully ({size_mb} MB)"
            )
        except Exception as e:
            console.print(f"\n[red]Failed to download base image: {e}[/red]")
            console.print(
                "[dim]You can place an existing Ubuntu qcow2 image in ~/.kage/images/ or run kage init --image-url <url>[/dim]"
            )
            raise typer.Exit(code=1)

    console.print(
        Panel(
            "[bold green]✨ Kage is initialized and ready to spawn VM instances![/bold green]\n\n"
            "Run [bold cyan]kage up my-agent --memory 4G[/bold cyan] to spin up your first VM.\n"
            "Run [bold cyan]kage list[/bold cyan] to view status across all instances.",
            title="[bold green]Ready[/bold green]",
            border_style="green",
        )
    )
