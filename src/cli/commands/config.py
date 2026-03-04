"""config命令 - 配置管理"""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.config import ConfigManager

app = typer.Typer(help="配置管理")
console = Console()


@app.command("list")
def list_config(
    config_path: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
) -> None:
    """列出当前配置"""
    manager = ConfigManager(config_path)
    config = manager.load()

    table = Table(title="当前配置")
    table.add_column("模块", style="cyan")
    table.add_column("配置项", style="green")
    table.add_column("值", style="yellow")

    table.add_row("API", "base_url", config.api.base_url or "(未设置)")
    table.add_row("API", "timeout", str(config.api.timeout))
    table.add_row("LLM", "provider", config.llm.provider)
    table.add_row("LLM", "model", config.llm.model)
    table.add_row("Embedding", "provider", config.embedding.provider)
    table.add_row("Embedding", "model", config.embedding.model)
    table.add_row("Clustering", "algorithm", config.clustering.algorithm)
    table.add_row("Cache", "enabled", str(config.cache.enabled))
    table.add_row("Cache", "ttl", str(config.cache.ttl))
    table.add_row("Output", "directory", config.output.directory)

    console.print(table)


@app.command("set")
def set_config(
    key: str = typer.Argument(..., help="配置键 (如 llm.provider)"),
    value: str = typer.Argument(..., help="配置值"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
) -> None:
    """设置配置值"""
    manager = ConfigManager(config_path)
    manager.load()

    try:
        manager.set(key, value)
        manager.save()
        console.print(f"[green]已设置 {key} = {value}[/green]")
    except KeyError:
        console.print(f"[red]无效的配置键: {key}[/red]")


@app.command("path")
def show_config_path(
    config_path: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
) -> None:
    """显示配置文件路径"""
    if config_path:
        console.print(f"配置文件: [bold]{config_path}[/bold]")
    else:
        console.print("配置文件: [bold]./config.yaml[/bold] (默认)")
