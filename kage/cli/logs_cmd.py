"""Implementation of `kage logs` CLI command."""

from __future__ import annotations

import typer
from rich.console import Console

from kage.core.instance import InstanceConfig

console = Console()


def logs_command(
    instance_name: str = typer.Argument(..., help="Name of the VM instance."),
    log_type: str = typer.Option("qemu", "--type", "-t", help="Log type: qemu, serial, or api."),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of trailing lines to display."),
) -> None:
    """View runtime logs for QEMU, guest serial console, or Host Bridge API."""
    inst = InstanceConfig.load(instance_name)
    if not inst:
        console.print(f"[red]Instance '{instance_name}' not found.[/red]")
        raise typer.Exit(code=1)

    if log_type == "serial":
        log_file = inst.serial_log
    elif log_type == "api":
        log_file = inst.api_log
    else:
        log_file = inst.qemu_log

    if not log_file.exists():
        console.print(f"[yellow]Log file '{log_file.name}' not found or empty.[/yellow]")
        return

    content = log_file.read_text(encoding="utf-8", errors="replace")
    all_lines = content.splitlines()
    selected = all_lines[-lines:] if len(all_lines) > lines else all_lines

    console.print(f"[bold cyan]=== {inst.name} ({log_file.name}) ===[/bold cyan]")
    for line in selected:
        print(line)
