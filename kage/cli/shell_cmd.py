"""Implementation of `kage shell` CLI command."""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Optional

import httpx
import typer
from rich.console import Console

from kage.core.config import get_or_create_ssh_key
from kage.core.instance import InstanceConfig, InstanceStatus

console = Console()


def shell_command(
    instance_name: Optional[str] = typer.Argument(
        None, help="Name of the VM instance to shell into."
    ),
    command: Optional[str] = typer.Option(
        None, "--command", "-c", help="Execute single non-interactive command and exit."
    ),
) -> None:
    """Open an interactive SSH shell or execute a single command inside the VM instance."""
    target_name = instance_name
    if not target_name:
        running = [i for i in InstanceConfig.list_all() if i.status == InstanceStatus.RUNNING]
        if not running:
            console.print("[red]No running Kage instances found.[/red]")
            raise typer.Exit(code=1)
        target_name = running[0].name

    inst = InstanceConfig.load(target_name)
    if not inst or not inst.ports:
        console.print(f"[red]Instance '{target_name}' not found or has no ports configured.[/red]")
        raise typer.Exit(code=1)

    p = inst.ports
    priv_key, _ = get_or_create_ssh_key()

    # 1. Non-interactive command execution via API or SSH
    if command:
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    f"http://127.0.0.1:{p.api}/api/v1/instances/{inst.name}/shell/exec",
                    json={"command": command},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("stdout"):
                        print(data["stdout"], end="")
                    if data.get("stderr"):
                        print(data["stderr"], end="", file=sys.stderr)
                    raise typer.Exit(code=data.get("exit_code", 0))
        except (httpx.ConnectError, httpx.HTTPStatusError):
            pass

    # 2. Interactive or direct SSH
    if shutil.which("ssh"):
        ssh_cmd = [
            "ssh",
            "-p",
            str(p.ssh),
            "-i",
            str(priv_key),
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=ERROR",
            "kage@127.0.0.1",
        ]
        if command:
            res = subprocess.run(ssh_cmd + ["bash", "-s"], input=command.encode("utf-8"), check=False)
            raise typer.Exit(code=res.returncode)
        else:
            console.print(f"[dim]Connecting to {inst.name} via SSH on port {p.ssh}...[/dim]")
            res = subprocess.run(ssh_cmd, check=False)
            raise typer.Exit(code=res.returncode)
    else:
        console.print("[red]SSH client not found in PATH.[/red]")
        raise typer.Exit(code=1)
