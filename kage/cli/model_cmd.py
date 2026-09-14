"""Implementation of `kage model` CLI commands for provider onboarding and model discovery."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from kage.agent.providers import PROVIDER_PRESETS, ModelProviderService
from kage.core.config import ProviderConfig, get_settings

console = Console()
model_app = typer.Typer(
    name="model",
    help="Onboard, configure, test, and switch LLM providers & models (OmniRoute, Anthropic, OpenAI, Ollama, DeepSeek).",
)


@model_app.command("onboard")
def onboard_provider(
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-p",
        help="Provider identifier: omniroute, anthropic, openai, deepseek, ollama, openrouter, custom.",
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key", "-k", help="API key for authentication."
    ),
    api_base: Optional[str] = typer.Option(None, "--api-base", "-b", help="Base API endpoint URL."),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Default model name to select."
    ),
    no_test: bool = typer.Option(False, "--no-test", help="Skip connectivity test completion."),
) -> None:
    """Interactively onboard an AI provider and discover active models."""
    console.print(
        Panel.fit(
            "[bold cyan]⚡ Kage Model & Provider Onboarding[/bold cyan]\n"
            "[dim]Configure any LLM provider (OmniRoute, Anthropic, OpenAI, DeepSeek, Ollama) for your agent VMs.[/dim]",
            border_style="cyan",
        )
    )

    settings = get_settings()

    # 1. Select Provider
    selected_provider = provider
    if not selected_provider:
        console.print("\n[bold]Select an AI Provider:[/bold]")
        choices = [
            (
                "omniroute",
                "OmniRoute (Universal Gateway — Claude 3.7, GPT-4o, DeepSeek, Gemini) [Recommended]",
            ),
            ("anthropic", "Anthropic (Direct Claude 3.7 / 3.5 Sonnet)"),
            ("openai", "OpenAI (Direct GPT-4o, o3-mini)"),
            ("ollama", "Ollama (Local private models on host GPU/CPU)"),
            ("deepseek", "DeepSeek (Direct DeepSeek V3 / R1)"),
            ("openrouter", "OpenRouter (Unified API)"),
            ("custom", "Custom OpenAI-Compatible (vLLM, LocalAI, LiteLLM proxy)"),
        ]

        for idx, (key, desc) in enumerate(choices, start=1):
            if key == "omniroute":
                console.print(f"  [bold green]{idx}. {desc}[/bold green]")
            else:
                console.print(f"  [bold cyan]{idx}.[/bold cyan] {desc}")

        choice_idx = Prompt.ask(
            "\nEnter choice number or name",
            default="1",
        )

        # Parse choice
        if choice_idx.isdigit() and 1 <= int(choice_idx) <= len(choices):
            selected_provider = choices[int(choice_idx) - 1][0]
        else:
            selected_provider = choice_idx.strip().lower()

    selected_provider = selected_provider.lower()
    preset = PROVIDER_PRESETS.get(selected_provider, PROVIDER_PRESETS["custom"])
    display_name = preset.get("display_name", selected_provider.capitalize())

    console.print(f"\n[bold green]✓ Selected Provider:[/bold green] [bold]{display_name}[/bold]")
    if preset.get("description"):
        console.print(f"[dim]{preset['description']}[/dim]")

    # 2. Configure API Base URL
    default_base = preset.get("default_api_base", "")
    target_api_base = api_base
    if not target_api_base:
        if not sys.stdin.isatty():
            target_api_base = default_base or "http://localhost:8000/v1"
        else:
            if default_base:
                target_api_base = Prompt.ask("\nAPI Base URL", default=default_base)
            else:
                target_api_base = Prompt.ask("\nAPI Base URL", default="http://localhost:8000/v1")

    # 3. Configure API Key
    target_api_key = api_key
    if target_api_key is None and selected_provider != "ollama":
        # Check existing in config or environment
        existing_provider = settings.get_provider(selected_provider)
        existing_key = existing_provider.api_key if existing_provider else None
        env_key = preset.get("env_key")
        env_val = os.getenv(env_key) if env_key else None

        initial_val = existing_key or env_val

        if initial_val and sys.stdin.isatty():
            masked = (
                initial_val[:6] + "..." + initial_val[-4:] if len(initial_val) > 12 else "********"
            )
            use_existing = Prompt.ask(
                f"Use existing API key ({masked})?",
                choices=["y", "n"],
                default="y",
            )
            if use_existing.lower() == "y":
                target_api_key = initial_val
        elif initial_val:
            target_api_key = initial_val

        if not target_api_key and sys.stdin.isatty():
            target_api_key = Prompt.ask(f"Enter {display_name} API Key", password=True)

    # 4. Fetch available models from provider endpoint
    console.print(
        f"\n[bold blue]Connecting to {display_name} ({target_api_base}) and discovering available models...[/bold blue]"
    )

    with console.status("[bold cyan]Querying provider endpoint...[/bold cyan]", spinner="dots"):
        try:
            available_models = asyncio.run(
                ModelProviderService.fetch_available_models(
                    provider=selected_provider,
                    api_key=target_api_key,
                    api_base=target_api_base,
                )
            )
        except Exception as e:
            console.print(f"[yellow]Could not automatically fetch models: {e}[/yellow]")
            available_models = preset.get("fallback_models", [])

    if not available_models:
        available_models = preset.get(
            "fallback_models", [preset.get("default_model", "default-model")]
        )

    # 5. Display Models Table
    model_table = Table(
        title=f"Available Models from {display_name}", show_header=True, header_style="bold cyan"
    )
    model_table.add_column("#", justify="right", style="dim")
    model_table.add_column("Model Identifier", style="bold")

    for idx, m in enumerate(available_models, start=1):
        model_table.add_row(str(idx), m)

    console.print(model_table)

    # 6. Select Default Model
    selected_model = model
    if not selected_model:
        def_choice = preset.get("default_model", available_models[0])
        if def_choice not in available_models and available_models:
            def_choice = available_models[0]

        if not sys.stdin.isatty():
            selected_model = def_choice
        else:
            choice_input = Prompt.ask(
                "\nSelect default model (enter number or model name)",
                default=def_choice,
            )

            if choice_input.isdigit() and 1 <= int(choice_input) <= len(available_models):
                selected_model = available_models[int(choice_input) - 1]
            else:
                selected_model = choice_input.strip()

    # 7. Test Connection if enabled
    if not no_test and target_api_key or selected_provider == "ollama":
        console.print(
            f"\n[bold blue]Testing completion with [cyan]{selected_model}[/cyan]...[/bold blue]"
        )
        with console.status("[bold cyan]Sending test ping...[/bold cyan]", spinner="dots"):
            success, msg = asyncio.run(
                ModelProviderService.test_connection(
                    provider=selected_provider,
                    model=selected_model,
                    api_key=target_api_key,
                    api_base=target_api_base,
                )
            )
        if success:
            console.print(f"  [bold green]✓ Connectivity Verified:[/bold green] {msg}")
        else:
            console.print(f"  [yellow]⚠ Warning:[/yellow] {msg}")
            console.print(
                "[dim]Saving configuration anyway. You can verify network or credentials later.[/dim]"
            )

    # 8. Save Provider Configuration
    prov_config = ProviderConfig(
        name=selected_provider,
        display_name=display_name,
        api_base=target_api_base,
        api_key=target_api_key,
        models=available_models,
        default_model=selected_model,
    )

    settings.set_provider(prov_config, set_active=True)
    settings.default_model = selected_model
    settings.save()

    console.print(
        Panel(
            f"[bold green]✓ Successfully onboarded {display_name}![/bold green]\n\n"
            f"• [bold]Active Provider:[/bold] {display_name}\n"
            f"• [bold]Default Model:[/bold]   [bold cyan]{selected_model}[/bold cyan]\n"
            f"• [bold]Endpoint:[/bold]        {target_api_base}\n"
            f"• [bold]Total Models:[/bold]    {len(available_models)} discovered\n\n"
            f'Run [bold cyan]kage agent run <instance> --prompt "..."[/bold cyan] to command your AI agent with this model.',
            title="[bold green]Onboarding Complete[/bold green]",
            border_style="green",
        )
    )


@model_app.command("list")
def list_models(
    refresh: bool = typer.Option(
        False, "--refresh", "-r", help="Re-fetch available models from active provider."
    ),
) -> None:
    """List configured providers, active provider, and available models."""
    settings = get_settings()

    active_prov = settings.get_provider()

    table = Table(
        title="Kage Model & Provider Configuration", show_header=True, header_style="bold cyan"
    )
    table.add_column("Provider", style="bold")
    table.add_column("Status")
    table.add_column("Endpoint")
    table.add_column("Default Model")
    table.add_column("Models Count", justify="right")

    for p_name, p_conf in settings.providers.items():
        is_active = p_name == settings.active_provider
        status_str = "[bold green]● Active[/bold green]" if is_active else "[dim]Configured[/dim]"
        table.add_row(
            p_conf.display_name or p_name.capitalize(),
            status_str,
            p_conf.api_base or "Default",
            p_conf.default_model or "-",
            str(len(p_conf.models)),
        )

    if not settings.providers:
        console.print("[yellow]No AI model providers configured yet.[/yellow]")
        console.print(
            "Run [bold cyan]kage model onboard[/bold cyan] to connect OmniRoute, Anthropic, OpenAI, or Ollama."
        )
        return

    console.print(table)

    if active_prov and active_prov.models:
        console.print(
            f"\n[bold]Discovered Models for {active_prov.display_name or active_prov.name}:[/bold]"
        )
        for m in active_prov.models:
            is_def = m == settings.default_model
            prefix = "[bold green]▶ " if is_def else "  • "
            suffix = " [bold green](Default)[/bold green]" if is_def else ""
            console.print(f"{prefix}[cyan]{m}[/cyan]{suffix}")


@model_app.command("set-default")
def set_default_model(
    model_name: str = typer.Argument(
        ..., help="Model identifier to set as default (e.g. omniroute/claude-3-7-sonnet)."
    ),
) -> None:
    """Set the active default model for AI agent tasks."""
    settings = get_settings()
    settings.default_model = model_name

    # Update on active provider as well if present
    active_prov = settings.get_provider()
    if active_prov:
        active_prov.default_model = model_name
        if model_name not in active_prov.models:
            active_prov.models.append(model_name)
        settings.set_provider(active_prov, set_active=True)
    else:
        settings.save()

    console.print(
        f"[bold green]✓ Default model set to:[/bold green] [bold cyan]{model_name}[/bold cyan]"
    )


@model_app.command("test")
def test_model(
    model_name: Optional[str] = typer.Argument(
        None, help="Model name to test. Defaults to active model."
    ),
) -> None:
    """Test model completion connectivity with a live ping."""
    settings = get_settings()
    active_prov = settings.get_provider()
    target_model = model_name or settings.default_model

    prov_name = active_prov.name if active_prov else "omniroute"
    api_key = active_prov.api_key if active_prov else None
    api_base = active_prov.api_base if active_prov else None

    console.print(
        f"[bold blue]Testing model [cyan]{target_model}[/cyan] on {prov_name}...[/bold blue]"
    )
    with console.status("[bold cyan]Sending test request...[/bold cyan]", spinner="dots"):
        success, msg = asyncio.run(
            ModelProviderService.test_connection(
                provider=prov_name,
                model=target_model,
                api_key=api_key,
                api_base=api_base,
            )
        )

    if success:
        console.print(f"[bold green]✓ Model Test Succeeded:[/bold green] {msg}")
    else:
        console.print(f"[bold red]✗ Model Test Failed:[/bold red] {msg}")
        raise typer.Exit(code=1)
