"""CLI主入口"""

import typer
from rich.console import Console

from src import __version__
from src.cli.commands import analyze, cache, config, fetch, report

app = typer.Typer(
    name="fault-analyzer",
    help="AI驱动的故障复盘分析工具",
    add_completion=False,
)

console = Console()

app.add_typer(fetch.app, name="fetch")
app.add_typer(analyze.app, name="analyze")
app.add_typer(report.app, name="report")
app.add_typer(config.app, name="config")
app.add_typer(cache.app, name="cache")


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="显示版本信息",
    ),
) -> None:
    if version:
        console.print(f"[bold green]fault-analyzer[/bold green] version: {__version__}")
        raise typer.Exit()


if __name__ == "__main__":
    app()
