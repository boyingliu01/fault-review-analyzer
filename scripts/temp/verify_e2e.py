"""全流程端到端验证脚本 - 用真实故障单号验证全链路打通。

用法: python scripts/temp/verify_e2e.py [task_id]
默认 task_id: 11751534
"""

import asyncio
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig
from src.config.manager import ConfigManager


def print_section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(result) -> None:
    """详细打印 pipeline 各环节结果"""

    # 1. 数据获取
    print_section("1. 数据获取 (API Fetch)")
    if result.task_data:
        td = result.task_data
        print(f"  任务ID:    {td.get('task_id', 'N/A')}")
        print(f"  标题:      {td.get('title', 'N/A')[:80]}")
        print(f"  状态:      {td.get('status', 'N/A')}")
        print(f"  优先级:    {td.get('priority', 'N/A')}")
        dev = td.get("development") or {}
        commits = dev.get("commits") or []
        print(f"  代码提交:  {len(commits)} 条")
        if commits:
            for c in commits[:3]:
                msg = (c.get("message") or "")[:60]
                print(f"    - [{c.get('commit_id', '?')[:8]}] {msg}")
    else:
        print("  ❌ 未获取到任务数据")

    # 2. 数据预处理
    print_section("2. 数据预处理 (Preprocessing)")
    if result.preprocessed:
        segs = result.preprocessed.get("segments", [])
        combined = result.preprocessed.get("combined_text", "")
        print(f"  文本段数:    {len(segs)}")
        print(f"  组合文本长度: {len(combined)} 字符")
        for seg in segs[:5]:
            content_len = len(seg.get("content", ""))
            print(f"    - [{seg.get('type', '?')}] {content_len} 字符")
    else:
        print("  ❌ 未预处理")

    # 3. 代码变更分析
    print_section("3. 代码变更分析 (Code Change Analysis)")
    if result.code_change_analysis:
        cca = result.code_change_analysis
        print(f"  文件变更数:     {cca.get('total_files_changed', 0)}")
        print(f"  代码模式数:     {len(cca.get('code_patterns', []))}")
        # 规范违规检测
        violations = cca.get("violations", [])
        print(f"  规范违规检测:   {len(violations)} 条")
        for v in violations[:5]:
            print(f"    - [{v.get('type', '?')}] {v.get('description', '')[:60]}")
    else:
        print("  ⚠️  无代码变更分析结果（可能无代码提交）")

    # 4. LLM 标签生成
    print_section("4. LLM 标签生成 (Label Generation)")
    if result.labels:
        for label in result.labels[:5]:
            name = label.get("name", "?")
            conf = label.get("confidence", 0)
            print(f"  - {name} (置信度: {conf:.2f})")
    else:
        print("  ⚠️  未生成标签（可能未启用 LLM）")

    # 5. 根因分析
    print_section("5. 根因分析 (Root Cause Analysis)")
    if result.root_causes:
        for rc in result.root_causes[:5]:
            cause = rc.get("root_cause", rc.get("description", "?"))
            print(f"  - {str(cause)[:80]}")
    else:
        print("  ⚠️  未进行根因分析（可能未启用 LLM）")

    # 6. 报告生成
    print_section("6. 报告生成 (Report Generation)")
    if result.report:
        print(f"  报告长度: {len(result.report)} 字符")
        # 打印报告前 500 字符
        preview = result.report[:500]
        print(f"  预览:\n{preview}")
    else:
        print("  ⚠️  未生成报告")

    # 7. 错误检查
    print_section("7. 错误检查")
    if result.error:
        print(f"  ❌ 错误: {result.error}")
    else:
        print("  ✅ 无错误")

    # 总结
    print_section("全流程验证总结")
    steps = {
        "数据获取": result.task_data is not None,
        "数据预处理": result.preprocessed is not None,
        "代码变更分析": result.code_change_analysis is not None or (
            result.task_data and not (result.task_data.get("development") or {}).get("commits")
        ),
        "LLM标签": result.labels is not None,
        "根因分析": result.root_causes is not None,
        "报告生成": bool(result.report),
        "无错误": not result.error,
    }
    for step, passed in steps.items():
        icon = "✅" if passed else "⚠️/❌"
        print(f"  {icon} {step}")

    all_pass = all(steps.values())
    print(f"\n  {'🎉 全流程打通！' if all_pass else '⚠️ 部分环节未通过，请检查上方详情'}")


async def main(task_id: int) -> None:
    print(f"🚀 开始全流程验证，故障单号: {task_id}")

    config_manager = ConfigManager()
    config_manager.load()

    pipeline_config = PipelineConfig(
        use_cache=True,
        use_llm=False,  # LLM key 过期，先关闭验证其他环节
        generate_labels=False,
        analyze_root_cause=False,
        analyze_root_cause_deep=False,
        check_rules=True,
        generate_report=True,
        output_path=Path("./output"),
    )

    pipeline = AnalysisPipeline(config_manager, pipeline_config)

    try:
        result = await pipeline.run_single(task_id)
        print_result(result)
    finally:
        await pipeline.close()


if __name__ == "__main__":
    tid = int(sys.argv[1]) if len(sys.argv) > 1 else 11751534
    asyncio.run(main(tid))
