"""fetch命令 - 获取故障数据"""

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.api import APIClient
from src.cache import CacheManager
from src.config import ConfigManager

app = typer.Typer(help="获取故障数据")
console = Console()


@app.command("single")
def fetch_single(
    task_id: int = typer.Argument(..., help="任务ID"),
    force: bool = typer.Option(False, "--force", "-f", help="强制刷新缓存"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
) -> None:
    """获取单个任务数据"""
    config_manager = ConfigManager(config_path)
    config = config_manager.load()

    # 从配置中获取缓存路径
    cache_path = Path(config.cache.db_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    cache_manager = CacheManager(
        db_path=cache_path,
        ttl=config.cache.ttl,
    )

    if not force:
        cached = cache_manager.get_task(task_id)
        if cached:
            console.print(f"[green]从缓存加载任务 {task_id}[/green]")
            return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"正在获取任务 {task_id}...", total=None)

        async def _fetch():
            async with APIClient(
                base_url=config.api.base_url,
                token=config.api.api_key,
                timeout=config.api.timeout,
                retry=config.api.retry,
            ) as client:
                return await client.get_full_task(task_id)

        import asyncio
        task = asyncio.run(_fetch())

        if task:
            cache_manager.save_task(task_id, task.model_dump())
            console.print(f"[green]成功获取并缓存任务 {task_id}[/green]")
        else:
            console.print(f"[red]获取任务 {task_id} 失败[/red]")


@app.command("batch")
def fetch_batch(
    query: str = typer.Option("", "--query", "-q", help="查询条件"),
    limit: int = typer.Option(100, "--limit", "-l", help="最大获取数量"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
) -> None:
    """批量获取任务数据"""
    console.print(f"[yellow]批量获取任务: query={query}, limit={limit}[/yellow]")
    console.print("[yellow]此功能需要API支持批量查询接口[/yellow]")


@app.command("status")
def cache_status(
    task_id: int | None = typer.Argument(None, help="任务ID"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
) -> None:
    """查看缓存状态"""
    config_manager = ConfigManager(config_path)
    config = config_manager.load()

    # 从配置中获取缓存路径
    cache_path = Path(config.cache.db_path)

    cache_manager = CacheManager(db_path=cache_path)

    if task_id:
        status = cache_manager.get_status(task_id)
        console.print(f"任务 {task_id} 缓存状态: [bold]{status.value}[/bold]")
    else:
        stats = cache_manager.get_stats()
        console.print("[bold]缓存统计:[/bold]")
        console.print(f"  总条目: {stats['total_entries']}")
        console.print(f"  有效条目: {stats['valid_entries']}")
        console.print(f"  过期条目: {stats['expired_entries']}")
