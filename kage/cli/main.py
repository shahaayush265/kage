"""Main CLI entrypoint for Kage — The Multi-Instance Agentic VM Engine."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

import kage
from kage.cli.agent_cmd import agent_app
from kage.cli.config_cmd import config_app
from kage.cli.connect_cmd import connect_command
from kage.cli.destroy_cmd import destroy_command
from kage.cli.init_cmd import init_command
from kage.cli.list_cmd import list_command
from kage.cli.logs_cmd import logs_command
from kage.cli.model_cmd import model_app
from kage.cli.shell_cmd import shell_command
from kage.cli.stop_cmd import stop_command
from kage.cli.up_cmd import up_command

console = Console()

app = typer.Typer(
    name="kage",
    help="⚡ Kage — The Multi-Instance Agentic VM Engine. Spin up, manage, observe, and connect AI agents to local Linux GUI VMs.",
    no_args_is_help=True,
    add_completion=True,
)


def version_callback(value: bool):
    if value:
        console.print(
            f"[bold cyan]Kage[/bold cyan] version [bold green]{kage.__version__}[/bold green]"
        )
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show Kage version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
):
    """Kage — The Multi-Instance Agentic VM Engine."""
    pass


# Register CLI commands
app.command(
    name="init", help="Validate host virtualization capabilities and provision base images."
)(init_command)
app.command(
    name="up", help="Spin up a new VM instance with overlay disk, dynamic ports, and agent bridge."
)(up_command)
app.command(
    name="list", help="List all instances, runtime statuses, ports, and resource consumption."
)(list_command)
app.command(name="ls", hidden=True)(list_command)
app.command(name="connect", help="Launch live noVNC desktop stream and Web Console in browser.")(
    connect_command
)
app.command(name="shell", help="Open an interactive SSH shell or execute single command in VM.")(
    shell_command
)
app.command(name="stop", help="Halt execution of a running VM instance.")(stop_command)
app.command(name="destroy", help="Tear down VM instance, disk overlays, and state records.")(
    destroy_command
)
app.command(name="rm", hidden=True)(destroy_command)
app.command(name="logs", help="View QEMU, serial, or API logs for an instance.")(logs_command)

# Sub-apps
app.add_typer(agent_app, name="agent")
app.add_typer(model_app, name="model")
app.add_typer(config_app, name="config")


if __name__ == "__main__":
    app()
