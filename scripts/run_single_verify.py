"""用第一个故障单跑完全流程，验证程序能否正常获取并分析数据。

用法: python scripts/run_single_verify.py <task_id>
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.analyzer import AnalysisPipeline, PipelineConfig
from src.config.manager import ConfigManager


async def run_single(task_id: int) -> None:
    """跑单个任务全流程并打印结果。"""
    config_manager = ConfigManager()
    config = config_manager.load()

    pipeline_config = PipelineConfig(
        use_cache=True,
        use_llm=True,  # 启用 LLM 分析（标签 + 根因）
        generate_labels=True,
        analyze_root_cause=True,
        analyze_root_cause_deep=False,  # 深度根因先不开，避免额外 API 调用
        check_rules=True,
        match_standards=True,
        generate_report=True,
    )

    pipeline = AnalysisPipeline(config_manager, pipeline_config)
    async with pipeline:
        result = await pipeline.run_single(task_id)

    print("\n" + "=" * 70)
    print(f"任务: {task_id} | 处理耗时: {result.processing_time:.2f}s | error: {result.error or '无'}")
    print("=" * 70)

    if result.error:
        logger.error(f"分析失败: {result.error}")
        return

    # 任务数据
    if result.task_data:
        td = result.task_data
        print(f"\n[任务数据] task_id={td.get('task_id')}")
        print(f"  标题: {td.get('title', '')[:100]}")
        print(f"  描述: {td.get('description', '')[:100]}")
        print(f"  状态: {td.get('status')} | 优先级: {td.get('priority')}")
        dev = td.get('development')
        if dev and dev.get('commits'):
            print(f"  代码变更: {len(dev['commits'])} 个 commit")
            for c in dev['commits'][:3]:
                print(f"    - {c.get('commit_id', '')[:12]} | {c.get('message', '')[:60]} | diff_len={len(c.get('diff', ''))}")
        else:
            print("  代码变更: 无")
        fa = td.get('fault_analysis')
        if fa:
            print(f"  复盘结论: {list(fa.keys())}")
        else:
            print("  复盘结论: 无")

    # 标签
    if result.labels:
        print(f"\n[标签] {len(result.labels)} 个")
        for lb in result.labels[:5]:
            print(f"  - {lb.get('name')} (conf={lb.get('confidence', 0):.2f}) {lb.get('description', '')[:60]}")

    # 根因
    if result.root_causes:
        print(f"\n[根因] {len(result.root_causes)} 个")
        for rc in result.root_causes[:5]:
            print(f"  - [{rc.get('cause_type')}] {rc.get('description', '')[:80]}")

    # 违规
    if result.violations:
        print(f"\n[违规] {len(result.violations)} 个")
        for v in result.violations[:5]:
            print(f"  - [{v.get('rule_id')}] {v.get('rule_name', '')[:50]} ({v.get('severity')})")

    # 代码变更分析
    if result.code_change_analysis:
        cca = result.code_change_analysis
        print(f"\n[代码变更分析] summary: {str(cca.get('summary', ''))[:100]}")
        print(f"  检测模式: {cca.get('detected_patterns', [])}")

    # 改进建议
    if result.improvements:
        print(f"\n[改进建议] {len(result.improvements)} 条")
        for imp in result.improvements[:5]:
            print(f"  - [{imp.get('priority')}] {imp.get('root_cause', '')[:50]}: {imp.get('measure', '')[:50]}")

    # 报告
    if result.report:
        print(f"\n[报告] 长度 {len(result.report)} 字符")
        print("  报告预览:")
        for line in result.report.split("\n")[:20]:
            print(f"    {line}")


if __name__ == "__main__":
    task_id = int(sys.argv[1])
    asyncio.run(run_single(task_id))
