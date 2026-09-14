"""Implementation of `kage up` CLI command."""

from __future__ import annotations

import re
import secrets
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kage.core.config import get_settings
from kage.core.instance import InstanceConfig, InstanceStatus
from kage.core.port_manager import PortAllocator
from kage.core.process import ProcessManager
from kage.guest.cloud_config import CloudConfigGenerator
from kage.hypervisor.cloud_init import CloudInitIsoBuilder
from kage.hypervisor.disks import DiskManager
from kage.hypervisor.image_manager import ImageManager
from kage.hypervisor.qemu import QEMURunner

console = Console()


def _parse_memory_mb(mem_str: str) -> int:
    """Convert memory string like '4G', '4096M', '2048' into integer megabytes."""
    clean = mem_str.strip().upper()
    match = re.match(r"^(\d+)\s*([GM]?)$", clean)
    if not match:
        raise ValueError(f"Invalid memory format '{mem_str}'. Use e.g. 4G or 4096M.")
    val, unit = match.groups()
    num = int(val)
    if unit == "G":
        return num * 1024
    return num


def up_command(
    instance_name: Optional[str] = typer.Argument(
        None, help="Name of the VM instance to create or start."
    ),
    cpus: int = typer.Option(2, "--cpus", "-c", help="Number of virtual CPU cores."),
    memory: str = typer.Option("4G", "--memory", "-m", help="RAM allocation (e.g. 4G, 2048M)."),
    shared_dir: Optional[str] = typer.Option(
        None, "--shared-dir", "-s", help="Host directory to mount at /workspace inside guest."
    ),
    headless: bool = typer.Option(False, "--headless", help="Run in headless background mode."),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force recreate instance if already exists."
    ),
) -> None:
    """Spin up a new VM instance with overlay disk, dynamic ports, and agent bridge."""
    settings = get_settings()
    settings.ensure_directories()

    name = instance_name or f"kage-{secrets.token_hex(3)}"
    mem_mb = _parse_memory_mb(memory)

    # Check existing instance
    existing = InstanceConfig.load(name)
    if existing and not force:
        if existing.qemu_pid and ProcessManager.is_alive(existing.qemu_pid):
            console.print(f"[bold green]Instance '{name}' is already running![/bold green]")
            _print_instance_summary(existing)
            return
        else:
            console.print(f"[yellow]Restarting stopped instance '{name}'...[/yellow]")
            # Ensure ports are still valid
            if not existing.ports or not PortAllocator.is_port_available(existing.ports.api):
                existing.ports = PortAllocator.allocate(name)
                existing.save()

            # Regenerate cloud-init ISO to ensure latest service scripts are present
            user_data = CloudConfigGenerator.generate_user_data(existing)
            meta_data = CloudConfigGenerator.generate_meta_data(existing.name)
            CloudInitIsoBuilder.create_cidata_iso(
                output_path=existing.cloud_init_iso,
                user_data=user_data,
                meta_data=meta_data,
            )

            pid = QEMURunner.start(existing)
            api_pid = _spawn_api_server(existing)
            existing.api_pid = api_pid
            existing.status = InstanceStatus.RUNNING
            existing.save()
            console.print(
                f"[bold green]✓ Instance '{name}' restarted successfully (PID {pid})[/bold green]"
            )
            _print_instance_summary(existing)
            return

    console.print(
        Panel.fit(
            f"[bold cyan]Spinning Up VM Instance: [bold white]{name}[/bold white][/bold cyan]\n"
            f"[dim]vCPUs:[/dim] {cpus} | [dim]RAM:[/dim] {memory} | [dim]Workspace:[/dim] {shared_dir or 'None'}",
            border_style="cyan",
        )
    )

    # Check base image
    base_image_path = ImageManager.get_base_image_path()
    if not base_image_path.exists():
        console.print(
            f"[yellow]Base image not found at '{base_image_path}'. Creating initial placeholder base image...[/yellow]"
        )
        try:
            qemu_img = DiskManager.get_qemu_img_bin()
            import subprocess

            base_image_path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [qemu_img, "create", "-f", "qcow2", str(base_image_path), "20G"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            console.print(
                f"[dim]Created blank base image at {base_image_path}. Note: Run `kage init` to download full Ubuntu XFCE image.[/dim]"
            )
        except Exception as e:
            console.print(f"[red]Error ensuring base image: {e}[/red]")
            raise typer.Exit(code=1)

    # 1. Allocate conflict-free ports
    console.print("[bold cyan][1/5][/bold cyan] Allocating conflict-free network ports...")
    ports = PortAllocator.allocate(name)
    console.print(
        f"  [green]✓[/green] Ports: SSH [bold]{ports.ssh}[/bold], VNC [bold]{ports.vnc}[/bold], noVNC [bold]{ports.novnc}[/bold], API [bold]{ports.api}[/bold]"
    )

    # 2. Create Instance Config
    inst = InstanceConfig(
        name=name,
        cpus=cpus,
        memory_mb=mem_mb,
        disk_size_gb=20,
        shared_dir=str(Path(shared_dir).resolve()) if shared_dir else None,
        headless=headless,
        ports=ports,
        status=InstanceStatus.STARTING,
    )
    inst.ensure_dir()

    # 3. Create CoW overlay disk
    console.print("[bold cyan][2/5][/bold cyan] Creating Copy-on-Write disk overlay...")
    with console.status("[blue]Generating qcow2 overlay disk...[/blue]", spinner="dots"):
        DiskManager.create_overlay(
            base_image=base_image_path,
            overlay_path=inst.overlay_disk,
        )
    console.print(f"  [green]✓[/green] Overlay created at [dim]{inst.overlay_disk}[/dim]")

    # 4. Generate Cloud-Init ISO
    console.print("[bold cyan][3/5][/bold cyan] Generating cloud-init NoCloud configuration ISO...")
    with console.status(
        "[blue]Building ISO 9660 CIDATA filesystem in-memory...[/blue]", spinner="dots"
    ):
        user_data = CloudConfigGenerator.generate_user_data(inst)
        meta_data = CloudConfigGenerator.generate_meta_data(inst.name)
        CloudInitIsoBuilder.create_cidata_iso(
            output_path=inst.cloud_init_iso,
            user_data=user_data,
            meta_data=meta_data,
        )
    console.print(f"  [green]✓[/green] Cloud-init ISO created at [dim]{inst.cloud_init_iso}[/dim]")

    # 5. Launch QEMU daemon
    console.print(
        f"[bold cyan][4/5][/bold cyan] Launching QEMU hypervisor ({cpus} vCPUs, {memory} RAM)..."
    )
    with console.status(
        "[bold blue]Starting VM process in background...[/bold blue]", spinner="dots"
    ):
        pid = QEMURunner.start(inst)
    console.print(f"  [green]✓[/green] QEMU running with PID [bold]{pid}[/bold]")

    # 6. Launch Host Bridge API Server
    console.print(
        "[bold cyan][5/5][/bold cyan] Spawning Host Bridge API & noVNC WebSocket server..."
    )
    with console.status(
        "[blue]Starting FastAPI bridge on port " + str(ports.api) + "...[/blue]", spinner="dots"
    ):
        api_pid = _spawn_api_server(inst)
        inst.api_pid = api_pid
        inst.status = InstanceStatus.RUNNING
        inst.save()
    console.print(f"  [green]✓[/green] Host Bridge active with PID [bold]{api_pid}[/bold]")

    console.print(f"\n[bold green]🚀 Instance '{name}' is up and ready![/bold green]\n")
    _print_instance_summary(inst)


def _spawn_api_server(instance: InstanceConfig) -> int:
    """Spawn background Host Bridge FastAPI server bound to instance API port."""
    if not instance.ports:
        return 0

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "kage.server.app:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(instance.ports.api),
        "--log-level",
        "warning",
    ]

    pid = ProcessManager.spawn_daemon(
        cmd=cmd,
        log_file=instance.api_log,
        cwd=instance.instance_dir,
    )
    return pid


def _print_instance_summary(inst: InstanceConfig) -> None:
    p = inst.ports
    if not p:
        return

    table = Table(show_header=False, box=None)
    table.add_row(
        "[bold cyan]Web Console:[/bold cyan]",
        f"[bold underline]http://127.0.0.1:{p.api}/view/{inst.name}[/bold underline]",
    )
    table.add_row("[bold cyan]Host Bridge API:[/bold cyan]", f"http://127.0.0.1:{p.api}/docs")
    table.add_row(
        "[bold cyan]SSH Access:[/bold cyan]",
        f"[bold]ssh kage@127.0.0.1 -p {p.ssh}[/bold] (password: kage)",
    )
    table.add_row("[bold cyan]VNC Port:[/bold cyan]", f"127.0.0.1:{p.vnc}")
    if inst.shared_dir:
        table.add_row("[bold cyan]Shared Folder:[/bold cyan]", f"{inst.shared_dir} -> /workspace")

    console.print(
        Panel(table, title=f"[bold green]Instance: {inst.name}[/bold green]", border_style="green")
    )
    console.print("Commands:")
    console.print(f"  • Connect to desktop: [bold cyan]kage connect {inst.name}[/bold cyan]")
    console.print(f"  • Open shell session: [bold cyan]kage shell {inst.name}[/bold cyan]")
    console.print(
        f'  • Run AI agent task:  [bold cyan]kage agent run {inst.name} --prompt "..."[/bold cyan]'
    )
    console.print(f"  • Stop instance:      [bold cyan]kage stop {inst.name}[/bold cyan]")
