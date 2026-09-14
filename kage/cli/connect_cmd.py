"""Implementation of `kage connect` CLI command."""

from __future__ import annotations

import webbrowser
from typing import Optional

import typer
from rich.console import Console

from kage.core.instance import InstanceConfig, InstanceStatus

console = Console()


def connect_command(
    instance_name: Optional[str] = typer.Argument(
        None, help="Name of the VM instance to connect to."
    ),
    no_browser: bool = typer.Option(
        False, "--no-browser", "-n", help="Do not automatically launch web browser."
    ),
) -> None:
    """Launch or output the browser URL for live noVNC desktop stream and Agent Web Console."""
    target_name = instance_name
    if not target_name:
        running = [i for i in InstanceConfig.list_all() if i.status == InstanceStatus.RUNNING]
        if not running:
            console.print("[red]No running Kage instances found.[/red]")
            console.print("Run [bold cyan]kage up [name][/bold cyan] to start an instance.")
            raise typer.Exit(code=1)
        target_name = running[0].name

    inst = InstanceConfig.load(target_name)
    if not inst:
        console.print(f"[red]Instance '{target_name}' not found.[/red]")
        raise typer.Exit(code=1)

    if not inst.ports:
        console.print(f"[red]Instance '{target_name}' has no allocated ports.[/red]")
        raise typer.Exit(code=1)

    url = f"http://127.0.0.1:{inst.ports.api}/view/{inst.name}"
    console.print(f"\n[bold green]Connected to {inst.name}![/bold green]")
    console.print(
        f"Live Web Console & Desktop Stream: [bold cyan underline]{url}[/bold cyan underline]\n"
    )

    if not no_browser:
        console.print("[dim]Opening web browser...[/dim]")
        try:
            webbrowser.open(url)
        except Exception:
            pass
