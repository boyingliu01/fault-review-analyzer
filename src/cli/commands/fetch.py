"""fetch命令 - 获取故障数据"""

from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

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
    try:
        config_manager = ConfigManager(config_path)
        config = config_manager.load()
    except ValueError as e:
        console.print(f"[red]配置错误: {e}[/red]")
        console.print("[yellow]请设置 .env 文件或 config/config.yaml 中的必要配置项[/yellow]")
        raise typer.Exit(1) from None

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

        async def _fetch() -> Any:
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
            cache_manager.save_task(task_id, task.model_dump(mode="json"))
            console.print(f"[green]成功获取并缓存任务 {task_id}[/green]")
        else:
            console.print(f"[red]获取任务 {task_id} 失败[/red]")


@app.command("batch")
def fetch_batch(
    task_ids: str = typer.Option("", "--task-ids", "-t", help="任务ID列表，逗号分隔"),
    query: str = typer.Option("", "--query", "-q", help="查询条件"),
    limit: int = typer.Option(100, "--limit", "-l", help="最大获取数量"),
    force: bool = typer.Option(False, "--force", "-f", help="强制刷新缓存"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
) -> None:
    """批量获取任务数据"""
    try:
        config_manager = ConfigManager(config_path)
        config = config_manager.load()
    except ValueError as e:
        console.print(f"[red]配置错误: {e}[/red]")
        console.print("[yellow]请设置 .env 文件或 config/config.yaml 中的必要配置项[/yellow]")
        raise typer.Exit(1) from None

    cache_path = Path(config.cache.db_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    cache_manager = CacheManager(
        db_path=cache_path,
        ttl=config.cache.ttl,
    )

    task_id_list: list[int] = []

    if task_ids:
        try:
            task_id_list = [int(tid.strip()) for tid in task_ids.split(",") if tid.strip()]
        except ValueError:
            console.print("[red]任务ID格式无效，请使用逗号分隔的数字列表[/red]")
            return

    if query:
        console.print(f"[cyan]使用查询条件: {query}[/cyan]")
        console.print("[yellow]API批量查询需要后端支持，当前仅支持task_ids模式[/yellow]")

        if not task_id_list:
            console.print("[yellow]没有指定任务ID，请使用 --task-ids 参数指定[/yellow]")
            return

    if not task_id_list:
        console.print("[yellow]请指定任务ID列表，使用 --task-ids 参数[/yellow]")
        return

    console.print(f"[cyan]准备获取 {len(task_id_list)} 个任务...[/cyan]")

    success_count = 0
    fail_count = 0
    skip_count = 0

    import asyncio

    async def fetch_tasks() -> None:
        nonlocal success_count, fail_count, skip_count

        async with APIClient(
            base_url=config.api.base_url,
            token=config.api.api_key,
            timeout=config.api.timeout,
            retry=config.api.retry,
        ) as client:
            for task_id in task_id_list:
                if not force:
                    cached = cache_manager.get_task(task_id)
                    if cached:
                        console.print(f"  任务 {task_id}: [yellow]跳过（已在缓存中）[/yellow]")
                        skip_count += 1
                        continue

                try:
                    task = await client.get_full_task(task_id)
                    if task:
                        cache_manager.save_task(task_id, task.model_dump(mode="json"))
                        console.print(f"  任务 {task_id}: [green]成功[/green]")
                        success_count += 1
                    else:
                        console.print(f"  任务 {task_id}: [red]失败（未找到）[/red]")
                        fail_count += 1
                except Exception as e:
                    console.print(f"  任务 {task_id}: [red]失败 ({e})[/red]")
                    fail_count += 1

    asyncio.run(fetch_tasks())

    console.print("\n[bold]获取完成:[/bold]")
    console.print(f"  成功: {success_count}")
    console.print(f"  跳过: {skip_count}")
    console.print(f"  失败: {fail_count}")


@app.command("status")
def cache_status(
    task_id: int | None = typer.Argument(None, help="任务ID"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
) -> None:
    """查看缓存状态"""
    try:
        config_manager = ConfigManager(config_path)
        config = config_manager.load()
    except ValueError as e:
        console.print(f"[red]配置错误: {e}[/red]")
        console.print("[yellow]请设置 .env 文件或 config/config.yaml 中的必要配置项[/yellow]")
        raise typer.Exit(1) from None

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


@app.command("list")
def cache_list(
    limit: int = typer.Option(20, "--limit", "-n", help="显示数量"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
) -> None:
    """列出缓存中的任务"""
    try:
        config_manager = ConfigManager(config_path)
        config = config_manager.load()
    except ValueError as e:
        console.print(f"[red]配置错误: {e}[/red]")
        console.print("[yellow]请设置 .env 文件或 config/config.yaml 中的必要配置项[/yellow]")
        raise typer.Exit(1) from None

    cache_path = Path(config.cache.db_path)
    cache_manager = CacheManager(db_path=cache_path)

    all_tasks = cache_manager.get_all_tasks()

    if not all_tasks:
        console.print("[yellow]缓存中没有任务[/yellow]")
        return

    table = Table(title=f"缓存任务 (共 {len(all_tasks)} 个)")
    table.add_column("Task ID", style="cyan")
    table.add_column("标题", style="white")
    table.add_column("状态", style="yellow")

    for task in all_tasks[:limit]:
        table.add_row(
            str(task.get("task_id", "")),
            task.get("title", "")[:40],
            task.get("status", ""),
        )

    console.print(table)

    if len(all_tasks) > limit:
        console.print(f"[dim]还有 {len(all_tasks) - limit} 个任务未显示[/dim]")
