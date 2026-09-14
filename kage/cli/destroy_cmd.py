"""Implementation of `kage destroy` CLI command."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.prompt import Confirm

from kage.core.instance import InstanceConfig
from kage.core.process import ProcessManager
from kage.hypervisor.qemu import QEMURunner

console = Console()


def destroy_command(
    instance_name: str = typer.Argument(..., help="Name of the VM instance to destroy."),
    force: bool = typer.Option(False, "--force", "-f", help="Bypass confirmation prompt."),
) -> None:
    """Tear down VM instance, deleting overlay disks, cloud-init seed, and state records."""
    inst = InstanceConfig.load(instance_name)
    if not inst:
        console.print(f"[red]Instance '{instance_name}' not found.[/red]")
        raise typer.Exit(code=1)

    if not force:
        confirm = Confirm.ask(
            f"Are you sure you want to permanently destroy instance '[bold red]{instance_name}[/bold red]' and its disk overlay?"
        )
        if not confirm:
            console.print("[yellow]Destroy operation aborted.[/yellow]")
            return

    with console.status(f"[bold red]Destroying instance '{instance_name}'...[/bold red]"):
        # 1. Stop API process
        if inst.api_pid and ProcessManager.is_alive(inst.api_pid):
            ProcessManager.stop_process(inst.api_pid, timeout_seconds=2.0)

        # 2. Stop QEMU
        if inst.qemu_pid and ProcessManager.is_alive(inst.qemu_pid):
            QEMURunner.stop(inst, timeout_seconds=4.0)

        # 3. Destroy directory and overlays
        inst.destroy()

    console.print(
        f"[bold green]✓ Instance '{instance_name}' and its disk overlays destroyed cleanly.[/bold green]"
    )
