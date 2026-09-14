"""Implementation of `kage config` CLI command."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from kage.core.config import get_settings

console = Console()
config_app = typer.Typer(name="config", help="View or update Kage engine configuration.")


@config_app.command("show")
def show_config():
    """Display current Kage configuration settings."""
    settings = get_settings()
    table = Table(title="Kage Configuration", show_header=True, header_style="bold cyan")
    table.add_column("Key", style="bold")
    table.add_column("Value")

    for k, v in settings.model_dump().items():
        table.add_row(k, str(v))

    console.print(table)


@config_app.command("set")
def set_config(
    key: str = typer.Argument(..., help="Configuration key to update."),
    value: str = typer.Argument(..., help="New value for configuration key."),
):
    """Set a configuration setting."""
    settings = get_settings()
    data = settings.model_dump()
    if key not in data:
        console.print(f"[red]Unknown configuration key '{key}'[/red]")
        raise typer.Exit(code=1)

    # Cast type
    orig_val = data[key]
    if isinstance(orig_val, int):
        val = int(value)
    elif isinstance(orig_val, bool):
        val = value.lower() in ("true", "1", "yes")
    else:
        val = value

    setattr(settings, key, val)
    settings.save()
    console.print(f"[green]✓ Set {key} = {val}[/green]")
