"""Implementation of `kage stop` CLI command."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from kage.core.instance import InstanceConfig, InstanceStatus
from kage.core.process import ProcessManager
from kage.hypervisor.qemu import QEMURunner

console = Console()


def stop_command(
    instance_name: Optional[str] = typer.Argument(
        None, help="Name of the VM instance to stop. If omitted, stops all running instances."
    ),
    all_instances: bool = typer.Option(False, "--all", "-a", help="Stop all running VM instances."),
) -> None:
    """Halt execution of a running VM instance gracefully."""
    instances = InstanceConfig.list_all()

    if all_instances or not instance_name:
        running = [
            i
            for i in instances
            if i.status == InstanceStatus.RUNNING or ProcessManager.is_alive(i.qemu_pid)
        ]
        if not running:
            console.print("[yellow]No running instances found.[/yellow]")
            return

        for inst in running:
            _stop_single(inst)
        return

    inst = InstanceConfig.load(instance_name)
    if not inst:
        console.print(f"[red]Instance '{instance_name}' not found.[/red]")
        raise typer.Exit(code=1)

    _stop_single(inst)


def _stop_single(inst: InstanceConfig) -> None:
    with console.status(f"[bold blue]Stopping instance '{inst.name}'...[/bold blue]"):
        # Stop API server
        if inst.api_pid and ProcessManager.is_alive(inst.api_pid):
            ProcessManager.stop_process(inst.api_pid, timeout_seconds=2.0)
            inst.api_pid = None

        # Stop QEMU
        QEMURunner.stop(inst, timeout_seconds=8.0)

    console.print(f"[bold green]✓ Instance '{inst.name}' halted cleanly.[/bold green]")
