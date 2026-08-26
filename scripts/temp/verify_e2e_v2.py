"""全流程端到端验证 V2 - 使用真实配置"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig
from src.api.client import APIClient
from src.config.manager import ConfigManager


def print_section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


async def main() -> None:
    task_id = 11751534

    print("=" * 60)
    print(f"  全流程端到端验证 - 故障单号: {task_id}")
    print("=" * 60)

    # 1. 配置加载
    print_section("1. 配置加载 (Config Loading)")
    cm = ConfigManager()
    cm.load()
    cfg = cm.get_config()
    print(f"  LLM Provider:   {cfg.llm.provider} / {cfg.llm.model}")
    print(f"  Embedding:      {cfg.embedding.provider} / {cfg.embedding.model}")
    print(f"  API Base URL:   {cfg.api.base_url[:40]}...")

    # 2. API 连通性 + 代码变更数据
    print_section("2. API + 代码变更数据 (API + Code Changes)")
    api = APIClient(
        base_url=cfg.api.base_url,
        api_key=cfg.api.api_key,
        timeout=cfg.api.timeout,
        retry=cfg.api.retry,
    )
    api.ensure_client()
    commits = await api.get_commits(task_id)
    print(f"  代码提交数: {len(commits)}")
    if commits:
        c = commits[0]
        print(f"    commit_id:    {c.commit_id[:12]}")
        print(f"    diff长度:     {len(c.diff)} 字符")
        print(f"    文件路径数:   {len(c.changes)}")
        print(f"    code_changes: {len(c.code_changes)} 个文件")
        if c.code_changes:
            cc = c.code_changes[0]
            print(f"      - {cc.file_path[-50:]}")
            print(f"        old: {len(cc.old_content)} chars, new: {len(cc.new_content)} chars")
    await api.close()

    # 3. 全流程 Pipeline 执行 (启用LLM)
    print_section("3. 全流程 Pipeline 执行 (with LLM)")
    pipeline_cfg = PipelineConfig(
        use_cache=False,
        use_llm=True,
        generate_labels=True,
        analyze_root_cause=True,
        check_rules=True,
        generate_report=True,
        output_path=Path("./output/e2e_v2"),
    )
    pipeline = AnalysisPipeline(config=cm, pipeline_config=pipeline_cfg)
    try:
        result = await pipeline.run_single(task_id)

        print(f"  状态: {'✅ 成功' if not result.error else '❌ 失败: ' + result.error}")

        # 代码变更分析详情
        print_section("4. 代码变更分析结果 (Code Change Analysis)")
        if result.code_change_analysis:
            cca = result.code_change_analysis
            summary = cca.get("summary", {})
            diff_stats = cca.get("diff_stats", {})
            patterns = cca.get("detected_patterns", [])
            analysis_text = cca.get("analysis_text", "")

            print(f"  提交数:         {summary.get('total_commits', 0)}")
            print(f"  文件变更数:     {summary.get('total_files_changed', 0)}")
            print(f"  新增行数:       {diff_stats.get('total_added', 0)}")
            print(f"  删除行数:       {diff_stats.get('total_removed', 0)}")
            print(f"  代码模式数:     {len(patterns)}")
            for p in patterns[:5]:
                print(f"    - {p.get('type', '?')}: {p.get('match', '')[:50]}")
            print(f"  分析文本长度:   {len(analysis_text)} 字符")
            if analysis_text:
                print(f"  分析文本:       {analysis_text[:300]}...")
        else:
            print("  ⚠️  无代码变更分析结果")

        # LLM 标签
        print_section("5. LLM 标签生成 (Label Generation)")
        if result.labels:
            print(f"  生成标签数: {len(result.labels)}")
            for label in result.labels[:5]:
                name = label.get("name", "?")
                conf = label.get("confidence", 0)
                print(f"    - {name} (置信度: {conf:.2f})")
        else:
            print("  ⚠️  未生成标签")

        # 根因分析
        print_section("6. 根因分析 (Root Cause Analysis)")
        if result.root_causes:
            print(f"  识别根因数: {len(result.root_causes)}")
            for rc in result.root_causes[:5]:
                cause = rc.get("root_cause", rc.get("description", "?"))
                print(f"    - {str(cause)[:80]}")
        else:
            print("  ⚠️  未识别根因")

        # 深度根因分析
        if result.deep_root_causes:
            print(f"\n  深度根因分析: {len(str(result.deep_root_causes))} 字符")

        # 规范违规
        print_section("7. 规范违规检测 (Violations)")
        if result.violations:
            print(f"  违规数: {len(result.violations)}")
            for v in result.violations[:5]:
                print(f"    - [{v.get('severity', '?')}] {v.get('rule_name', '')}: {v.get('message', '')[:60]}")
        else:
            print("  ⚠️  无违规")

        # 报告
        print_section("8. 报告生成 (Report)")
        if result.report:
            print(f"  报告长度: {len(result.report)} 字符")
            print(f"  报告预览:\n{result.report[:500]}...")
        else:
            print("  ⚠️  未生成报告")

        # 错误
        if result.error:
            print_section("❌ 错误信息")
            print(f"  {result.error}")

    except Exception as e:
        import traceback
        print(f"  ❌ Pipeline 异常: {e}")
        traceback.print_exc()
    finally:
        await pipeline.close()


asyncio.run(main())
