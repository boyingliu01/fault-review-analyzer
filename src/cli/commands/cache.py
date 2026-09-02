"""cache命令 - 缓存管理"""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.cache import CacheManager
from src.config import ConfigManager

app = typer.Typer(help="缓存管理")
console = Console()


def _get_cache_db_path(config_path: Path | None) -> Path:
    """从配置文件获取缓存数据库路径。

    显式指定的 --config 若不存在或加载失败，必须可见地报错退出，
    不得静默回退到默认路径：静默回退曾让测试与运维操作在毫不知情的
    情况下指向真实库 data/cache/cache.db，造成缓存数据丢失事故。
    未指定 --config 时按 CLI 惯例使用默认路径。
    """
    if config_path is not None:
        if not config_path.exists():
            console.print(f"[red]配置文件不存在: {config_path}[/red]")
            raise typer.Exit(1) from None
        try:
            config = ConfigManager(config_path).load()
        except Exception as e:
            console.print(f"[red]无法加载配置文件 {config_path}: {e}[/red]")
            raise typer.Exit(1) from None
        return Path(config.cache.db_path)
    return Path("./data/cache/cache.db")


@app.command("list")
def list_cache(
    limit: int = typer.Option(20, "--limit", "-l", help="显示数量限制"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
) -> None:
    """列出缓存条目"""
    cache_db = _get_cache_db_path(config_path)
    with CacheManager(db_path=cache_db) as cache_manager:
        index = cache_manager.get_index()[:limit]

    if not index:
        console.print("[yellow]缓存为空[/yellow]")
        return

    table = Table(title=f"缓存条目 (显示前 {len(index)} 条)")
    table.add_column("任务ID", style="cyan")
    table.add_column("创建时间", style="green")
    table.add_column("过期时间", style="yellow")

    for entry in index:
        table.add_row(
            str(entry["task_id"]),
            entry["created_at"],
            entry["expires_at"],
        )

    console.print(table)


@app.command("clear")
def clear_cache(
    task_id: int | None = typer.Argument(None, help="任务ID (不指定则清空全部)"),
    force: bool = typer.Option(False, "--force", "-f", help="强制清除，不询问确认"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
) -> None:
    """清除缓存"""
    cache_db = _get_cache_db_path(config_path)
    with CacheManager(db_path=cache_db) as cache_manager:
        if task_id:
            cache_manager.invalidate(task_id)
            console.print(f"[green]已清除任务 {task_id} 的缓存[/green]")
        else:
            if not force:
                confirm = typer.confirm("确定要清空所有缓存吗？")
                if not confirm:
                    console.print("[yellow]操作已取消[/yellow]")
                    return

            cache_manager.invalidate_all()
            console.print("[green]已清空所有缓存[/green]")


@app.command("stats")
def cache_stats(
    config_path: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
) -> None:
    """显示缓存统计"""
    cache_db = _get_cache_db_path(config_path)
    with CacheManager(db_path=cache_db) as cache_manager:
        stats = cache_manager.get_stats()

    table = Table(title="缓存统计")
    table.add_column("指标", style="cyan")
    table.add_column("值", style="green")

    table.add_row("总条目", str(stats["total_entries"]))
    table.add_row("有效条目", str(stats["valid_entries"]))
    table.add_row("过期条目", str(stats["expired_entries"]))

    console.print(table)


@app.command("cleanup")
def cleanup_cache(
    config_path: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
) -> None:
    """清理过期缓存"""
    cache_db = _get_cache_db_path(config_path)
    with CacheManager(db_path=cache_db) as cache_manager:
        count = cache_manager.cleanup_expired()
    console.print(f"[green]已清理 {count} 条过期缓存[/green]")
