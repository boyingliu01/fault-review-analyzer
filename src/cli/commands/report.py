"""report命令 - 生成分析报告"""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.cache import CacheManager
from src.config import ConfigManager
from src.report import ReportGenerator

app = typer.Typer(help="生成分析报告")
console = Console()


@app.command()
def generate(
    task_id: int | None = typer.Argument(None, help="任务ID"),
    cluster_id: int | None = typer.Option(None, "--cluster", "-c", help="聚类ID"),
    output: Path = typer.Option(Path("./output/"), "--output", "-o", help="输出目录"),
    format: str = typer.Option("markdown", "--format", "-f", help="输出格式"),
    config_path: Path | None = typer.Option(None, "--config", help="配置文件路径"),
) -> None:
    """生成分析报告"""
    try:
        config_manager = ConfigManager(config_path)
        config = config_manager.load()
    except ValueError as e:
        console.print(f"[red]配置错误: {e}[/red]")
        console.print("[yellow]请设置 .env 文件或 config/config.yaml 中的必要配置项[/yellow]")
        raise typer.Exit(1) from None

    cache_path = Path(config.cache.db_path)
    generator = ReportGenerator()

    with CacheManager(db_path=cache_path) as cache_manager:
        if task_id is not None:
            console.print(f"[cyan]生成任务 {task_id} 的分析报告...[/cyan]")
            task_data = cache_manager.load_task(task_id)
            if not task_data:
                console.print(f"[red]任务 {task_id} 不在缓存中[/red]")
                console.print("[yellow]请先使用 fetch 命令获取任务数据[/yellow]")
                return
            report = generator.generate_single(
                task_data=task_data,
                segments=task_data.get("segments", []),
                labels=task_data.get("labels", []),
                root_causes=task_data.get("root_causes", []),
            )
            output_path = output / f"task_{task_id}_report.md"
            output.mkdir(parents=True, exist_ok=True)
            generator.save_report(report, output_path)
            console.print(f"[green]报告已生成: {output_path}[/green]")
        elif cluster_id is not None:
            console.print(f"[cyan]生成聚类 {cluster_id} 的分析报告...[/cyan]")
            all_tasks = cache_manager.get_all_tasks()
            cluster_tasks = [t for t in all_tasks if t.get("cluster_id") == cluster_id]
            if not cluster_tasks:
                console.print(f"[yellow]聚类 {cluster_id} 中没有任务[/yellow]")
                return
            from src.report.models import ClusterReport

            cluster_report = ClusterReport(
                cluster_id=cluster_id,
                task_count=len(cluster_tasks),
                labels=[],
                common_root_causes=[],
                summary="聚类分析报告",
                suggestions=["建议优化代码质量", "加强测试覆盖"],
            )
            report = generator.generate_cluster(cluster_report)
            output_path = output / f"cluster_{cluster_id}_report.md"
            output.mkdir(parents=True, exist_ok=True)
            generator.save_report(report, output_path)
            console.print(f"[green]报告已生成: {output_path}[/green]")
        else:
            console.print("[yellow]批量生成报告...[/yellow]")
            all_tasks = cache_manager.get_all_tasks()
            if not all_tasks:
                console.print("[yellow]缓存中没有任务数据[/yellow]")
                return
            output.mkdir(parents=True, exist_ok=True)
            for task in all_tasks:
                tid = task.get("task_id")
                if tid:
                    report = generator.generate_single(
                        task_data=task,
                        segments=task.get("segments", []),
                        labels=task.get("labels", []),
                        root_causes=task.get("root_causes", []),
                    )
                    task_output = output / f"task_{tid}_report.md"
                    generator.save_report(report, task_output)
            console.print(f"[green]已为 {len(all_tasks)} 个任务生成报告[/green]")


@app.command("list")
def list_reports(
    output: Path = typer.Option(Path("./output/"), "--output", "-o", help="输出目录"),
) -> None:
    """列出已生成的报告"""
    if not output.exists():
        console.print("[yellow]输出目录不存在[/yellow]")
        return

    md_files = list(output.glob("*.md"))

    if not md_files:
        console.print("[yellow]没有找到报告文件[/yellow]")
        return

    table = Table(title="已生成的报告")
    table.add_column("文件名", style="cyan")
    table.add_column("大小", style="white")

    for f in sorted(md_files):
        size_kb = f.stat().st_size / 1024
        table.add_row(f.name, f"{size_kb:.1f} KB")

    console.print(table)
