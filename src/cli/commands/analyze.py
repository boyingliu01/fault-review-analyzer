"""analyze命令 - 分析故障数据"""

from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.analyzer import AnalysisPipeline, PipelineConfig, PipelineResult
from src.cache import CacheManager
from src.config import ConfigManager

app = typer.Typer(help="分析故障数据")
console = Console()


@app.command("single")
def analyze_single(
    task_id: int = typer.Argument(..., help="任务ID"),
    output: Path | None = typer.Option(None, "--output", "-o", help="输出报告路径"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
    use_llm: bool = typer.Option(True, "--llm/--no-llm", help="是否使用LLM分析"),
    use_cache: bool = typer.Option(True, "--cache/--no-cache", help="是否使用缓存"),
) -> None:
    """分析单个任务"""
    console.print(f"[cyan]分析任务 {task_id}...[/cyan]")

    try:
        config_manager = ConfigManager(config_path)
        config_manager.load()
    except ValueError as e:
        console.print(f"[red]配置错误: {e}[/red]")
        console.print("[yellow]请设置 .env 文件或 config/config.yaml 中的必要配置项[/yellow]")
        raise typer.Exit(1) from None

    pipeline_config = PipelineConfig(
        use_cache=use_cache,
        use_llm=use_llm,
        generate_report=True,
    )

    pipeline = AnalysisPipeline(config_manager, pipeline_config)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("正在分析...", total=None)
        import asyncio

        async def run_analysis() -> PipelineResult:
            try:
                return await pipeline.run_single(task_id)
            finally:
                await pipeline.close()

        result = asyncio.run(run_analysis())

    if result.error:
        console.print(f"[red]分析失败: {result.error}[/red]")
        raise typer.Exit(1) from None

    console.print("[green]分析完成![/green]")

    table = Table(title="分析结果")
    table.add_column("项目", style="cyan")
    table.add_column("值", style="white")

    if result.preprocessed:
        table.add_row("文本段数", str(len(result.preprocessed.get("segments", []))))

    if result.labels:
        label_names = [label.get("name", "") for label in result.labels]
        table.add_row("标签", ", ".join(label_names[:3]))

    if result.root_causes:
        table.add_row("根因数", str(len(result.root_causes)))

    if result.violations:
        table.add_row("规范违规", str(len(result.violations)))

    console.print(table)

    if output:
        if output.suffix:
            output_path = output
        else:
            output.mkdir(parents=True, exist_ok=True)
            output_path = output / f"task_{task_id}_report.md"
        output_path.write_text(result.report, encoding="utf-8")
        console.print(f"[green]报告已保存到: {output_path}[/green]")


@app.command("batch")
def analyze_batch(
    from_cache: bool = typer.Option(True, "--from-cache/--no-cache", help="从缓存读取"),
    cluster: bool = typer.Option(True, "--cluster/--no-cluster", help="是否进行聚类分析"),
    min_cluster_size: int = typer.Option(3, "--min-size", help="最小聚类大小"),
    output: Path | None = typer.Option(None, "--output", "-o", help="输出报告路径"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
    excel: Path | None = typer.Option(
        None, "--excel", help="从 Excel 文件读取故障单号列表（替代缓存）"
    ),
) -> None:
    """批量分析缓存或 Excel 中的任务"""
    console.print("[cyan]批量分析任务...[/cyan]")

    # G16: 支持从 Excel 读取故障单号列表
    if excel is not None:
        from src.utils.excel_reader import read_task_ids_from_excel

        try:
            task_ids = read_task_ids_from_excel(excel)
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from None

        if not task_ids:
            console.print("[yellow]Excel 中未找到有效的故障单号[/yellow]")
            return

        console.print(f"[cyan]从 Excel 读取到 {len(task_ids)} 个故障单号[/cyan]")
        try:
            config_manager = ConfigManager(config_path)
            config = config_manager.load()
        except ValueError as e:
            console.print(f"[red]配置错误: {e}[/red]")
            raise typer.Exit(1) from None

        _run_batch_analysis(
            task_ids=task_ids,
            cluster=cluster,
            from_cache=from_cache,
            config_manager=config_manager,
            output=output,
            console=console,
        )
        return

    try:
        config_manager = ConfigManager(config_path)
        config = config_manager.load()
    except ValueError as e:
        console.print(f"[red]配置错误: {e}[/red]")
        console.print("[yellow]请设置 .env 文件或 config/config.yaml 中的必要配置项[/yellow]")
        raise typer.Exit(1) from None

    cache_path = Path(config.cache.db_path)
    with CacheManager(db_path=cache_path) as cache_manager:
        all_tasks = cache_manager.get_all_tasks()

    if not all_tasks:
        console.print("[yellow]缓存中没有任务数据[/yellow]")
        console.print("[yellow]请先使用 fetch 命令获取任务数据[/yellow]")
        return

    console.print(f"[cyan]找到 {len(all_tasks)} 个缓存任务[/cyan]")

    task_ids = [task["task_id"] for task in all_tasks]

    _run_batch_analysis(
        task_ids=task_ids,
        cluster=cluster,
        from_cache=from_cache,
        config_manager=config_manager,
        output=output,
        console=console,
    )


def _run_batch_analysis(
    *,
    task_ids: list[int],
    cluster: bool,
    from_cache: bool,
    config_manager: ConfigManager,
    output: Path | None,
    console: Console,
) -> None:
    """执行批量分析（缓存或 Excel 来源共用）。"""
    pipeline_config = PipelineConfig(
        use_cache=from_cache,
        use_llm=True,
        generate_report=True,
    )

    pipeline = AnalysisPipeline(config_manager, pipeline_config)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("正在批量分析...", total=None)

        if cluster:
            import asyncio

            async def run_clustering() -> dict[str, Any]:
                try:
                    return await pipeline.run_clustering(task_ids)
                finally:
                    await pipeline.close()

            result = asyncio.run(run_clustering())

            if "error" in result:
                console.print(f"[red]聚类分析失败: {result['error']}[/red]")
            else:
                console.print("[green]聚类分析完成![/green]")
                console.print(f"  聚类数量: {result.get('cluster_count', 0)}")
                console.print(f"  噪声点: {result.get('noise_count', 0)}")
        else:
            import asyncio

            async def run_batch() -> list[PipelineResult]:
                try:
                    return await pipeline.run_batch(task_ids)
                finally:
                    await pipeline.close()

            results = asyncio.run(run_batch())

            console.print(f"[green]批量分析完成! 共处理 {len(results)} 个任务[/green]")

    if output:
        if output.suffix:
            output_path = output
        else:
            output.mkdir(parents=True, exist_ok=True)
            output_path = output / "batch_analysis_report.md"
        output_path.write_text(f"# 批量分析报告\n\n共分析 {len(task_ids)} 个任务", encoding="utf-8")
        console.print(f"[green]报告已保存到: {output_path}[/green]")


@app.command("clusters")
def analyze_clusters(
    output: Path | None = typer.Option(None, "--output", "-o", help="输出报告路径"),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
) -> None:
    """对缓存中的任务进行聚类分析"""
    console.print("[cyan]聚类分析...[/cyan]")

    config_manager = ConfigManager(config_path)
    try:
        config = config_manager.load()
    except ValueError as e:
        console.print(f"[red]配置错误: {e}[/red]")
        console.print("[yellow]请设置 .env 文件或 config/config.yaml 中的必要配置项[/yellow]")
        raise typer.Exit(1) from None

    cache_path = Path(config.cache.db_path)
    with CacheManager(db_path=cache_path) as cache_manager:
        all_tasks = cache_manager.get_all_tasks()

    if not all_tasks:
        console.print("[yellow]缓存中没有任务数据[/yellow]")
        return

    task_ids = [task["task_id"] for task in all_tasks]

    import asyncio

    from src.analyzer import AnalysisPipeline, PipelineConfig

    pipeline_config = PipelineConfig(use_cache=True, use_llm=False)
    pipeline = AnalysisPipeline(config_manager, pipeline_config)

    async def run_clustering() -> dict[str, Any]:
        try:
            return await pipeline.run_clustering(task_ids)
        finally:
            await pipeline.close()

    result = asyncio.run(run_clustering())

    tasks_by_cluster: dict[int, list[int]] = {}
    if "error" in result:
        console.print(f"[red]聚类分析失败: {result['error']}[/red]")
    else:
        console.print("[green]聚类分析完成![/green]")
        console.print(f"  任务总数: {len(task_ids)}")
        console.print(f"  聚类数量: {result.get('cluster_count', 0)}")
        console.print(f"  噪声点: {result.get('noise_count', 0)}")

        for task in result.get("tasks", []):
            cluster_id = task.get("cluster_id", -1)
            if cluster_id not in tasks_by_cluster:
                tasks_by_cluster[cluster_id] = []
            tasks_by_cluster[cluster_id].append(task["task_id"])

        table = Table(title="聚类分布")
        table.add_column("聚类ID", style="cyan")
        table.add_column("任务数量", style="white")

        for cid, tids in sorted(tasks_by_cluster.items()):
            table.add_row(str(cid), str(len(tids)))

        console.print(table)

    if output:
        if output.suffix:
            output_path = output
        else:
            output.mkdir(parents=True, exist_ok=True)
            output_path = output / "cluster_analysis_report.md"

        report_lines = [
            "# 聚类分析报告\n\n",
            f"任务总数: {len(task_ids)}\n",
            f"聚类数量: {result.get('cluster_count', 0)}\n",
            f"噪声点: {result.get('noise_count', 0)}\n\n",
            "## 聚类详情\n\n",
        ]

        for cluster_id in sorted(tasks_by_cluster.keys()):
            task_ids_in_cluster = tasks_by_cluster[cluster_id]
            cluster_label = f"聚类 {cluster_id}" if cluster_id != -1 else "噪声点"
            report_lines.append(f"### {cluster_label} ({len(task_ids_in_cluster)} 个任务)\n\n")

            for tid in task_ids_in_cluster:
                task_info = next(
                    (t for t in result.get("tasks", []) if t.get("task_id") == tid),
                    None,
                )
                title = task_info.get("title", "") if task_info else ""
                report_lines.append(f"- **{tid}**: {title}\n")

            report_lines.append("\n")

        output_path.write_text("".join(report_lines), encoding="utf-8")
        console.print(f"[green]报告已保存到: {output_path}[/green]")
