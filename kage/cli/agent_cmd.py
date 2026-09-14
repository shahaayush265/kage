"""Implementation of `kage agent` CLI commands."""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from kage.agent.runner import AgentRunner
from kage.core.config import get_settings
from kage.core.instance import InstanceConfig, InstanceStatus

console = Console()
agent_app = typer.Typer(name="agent", help="Command and run autonomous AI agents in Kage VMs.")


@agent_app.command("run")
def run_agent_cli(
    instance_name: Optional[str] = typer.Argument(None, help="Target VM instance name."),
    prompt: str = typer.Option(
        ..., "--prompt", "-p", help="Instructions or task prompt for the AI agent."
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="LiteLLM model identifier (e.g. anthropic/claude-3-7-sonnet-20250219, openai/gpt-4o, ollama/qwen2.5-coder).",
    ),
    max_steps: int = typer.Option(15, "--max-steps", help="Maximum execution loop steps."),
    temperature: float = typer.Option(0.2, "--temperature", "-t", help="Sampling temperature."),
) -> None:
    """Execute an autonomous AI agent task against a live VM instance."""
    target_name = instance_name
    if not target_name:
        running = [i for i in InstanceConfig.list_all() if i.status == InstanceStatus.RUNNING]
        if not running:
            console.print("[red]No running Kage instances found.[/red]")
            raise typer.Exit(code=1)
        target_name = running[0].name

    inst = InstanceConfig.load(target_name)
    if not inst:
        console.print(f"[red]Instance '{target_name}' not found.[/red]")
        raise typer.Exit(code=1)

    settings = get_settings()
    target_model = model or settings.default_model

    console.print(
        Panel(
            f"[bold cyan]Task:[/bold cyan] {prompt}\n"
            f"[dim]Instance:[/dim] [bold]{target_name}[/bold] | [dim]Model:[/dim] [bold green]{target_model}[/bold green]",
            title="[bold]Kage Autonomous Agent[/bold]",
            border_style="cyan",
        )
    )

    runner = AgentRunner(
        instance_name=target_name,
        model=target_model,
        max_steps=max_steps,
        temperature=temperature,
    )

    async def step_callback(step_data: dict):
        step_num = step_data.get("step", 0)
        thought = step_data.get("thought", "")
        tool_name = step_data.get("tool_name")
        tool_args = step_data.get("tool_args")
        tool_result = step_data.get("tool_result")

        console.print(f"\n[bold magenta]─── Step {step_num} ───[/bold magenta]")
        if thought:
            console.print(f"[italic]{thought}[/italic]")

        if tool_name:
            import json

            args_str = json.dumps(tool_args or {}, indent=2)
            console.print(f"[bold cyan]🛠 Tool:[/bold cyan] [bold]{tool_name}[/bold]")
            console.print(f"[dim]{args_str}[/dim]")

            if tool_result:
                res_str = (
                    json.dumps(tool_result, indent=2)
                    if isinstance(tool_result, (dict, list))
                    else str(tool_result)
                )
                if len(res_str) > 500:
                    res_str = res_str[:500] + "... [truncated]"
                console.print(f"[bold green]↳ Result:[/bold green] [dim]{res_str}[/dim]")

    try:
        result = asyncio.run(runner.run_async(prompt, step_callback=step_callback))
    except KeyboardInterrupt:
        console.print("\n[yellow]Agent task interrupted by user.[/yellow]")
        raise typer.Exit(code=130)
    except Exception as e:
        console.print(f"\n[red]Agent execution failed: {e}[/red]")
        raise typer.Exit(code=1)

    console.print("\n" + "=" * 50)
    if result["success"]:
        console.print(
            Panel(
                f"[bold green]Final Answer:[/bold green]\n{result['final_answer']}",
                title="[bold green]✓ Task Completed[/bold green]",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold yellow]Result:[/bold yellow]\n{result['final_answer']}",
                title="[bold yellow]Task Finished[/bold yellow]",
                border_style="yellow",
            )
        )
