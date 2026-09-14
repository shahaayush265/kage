"""Implementation of `kage list` CLI command."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from kage.core.instance import InstanceConfig, InstanceStatus
from kage.core.process import ProcessManager

console = Console()


def list_command(
    json_output: bool = typer.Option(False, "--json", help="Output list in JSON format."),
) -> None:
    """Print an ASCII table of instances, runtime statuses, ports, and resource metrics."""
    instances = InstanceConfig.list_all()

    if json_output:
        import json

        out = []
        for inst in instances:
            # Sync status
            if inst.qemu_pid and not ProcessManager.is_alive(inst.qemu_pid):
                inst.status = InstanceStatus.STOPPED
            metrics = ProcessManager.get_metrics(inst.qemu_pid)
            d = inst.model_dump(mode="json")
            d["metrics"] = metrics.model_dump(mode="json")
            out.append(d)
        console.print(json.dumps(out, indent=2))
        return

    if not instances:
        console.print("[yellow]No Kage instances found.[/yellow]")
        console.print("Run [bold cyan]kage up [name][/bold cyan] to spin up a new instance.")
        return

    table = Table(
        title="Kage VM Instances",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
    )
    table.add_column("Instance Name", style="bold")
    table.add_column("Status")
    table.add_column("Specs", style="dim")
    table.add_column("SSH Port")
    table.add_column("VNC Port")
    table.add_column("Web Console & API")
    table.add_column("CPU %", justify="right")
    table.add_column("Memory (RSS)", justify="right")
    table.add_column("Uptime", justify="right")

    for inst in instances:
        is_alive = ProcessManager.is_alive(inst.qemu_pid)
        if not is_alive and inst.status == InstanceStatus.RUNNING:
            inst.status = InstanceStatus.STOPPED
            inst.save()

        metrics = ProcessManager.get_metrics(inst.qemu_pid)

        if inst.status == InstanceStatus.RUNNING:
            status_badge = "[bold green]● Running[/bold green]"
        elif inst.status == InstanceStatus.STARTING:
            status_badge = "[bold yellow]● Starting[/bold yellow]"
        else:
            status_badge = "[red]○ Stopped[/red]"

        p = inst.ports
        ssh_str = str(p.ssh) if p else "-"
        vnc_str = str(p.vnc) if p else "-"
        api_str = f"http://127.0.0.1:{p.api}" if p else "-"

        uptime_str = "-"
        if metrics.uptime_seconds > 0:
            m, s = divmod(int(metrics.uptime_seconds), 60)
            h, m = divmod(m, 60)
            uptime_str = f"{h}h {m}m" if h > 0 else f"{m}m {s}s"

        table.add_row(
            inst.name,
            status_badge,
            f"{inst.cpus} vCPU / {inst.memory_mb}MB",
            ssh_str,
            vnc_str,
            api_str,
            f"{metrics.cpu_percent}%" if is_alive else "-",
            f"{metrics.memory_rss_mb} MB" if is_alive else "-",
            uptime_str,
        )

    console.print(table)
