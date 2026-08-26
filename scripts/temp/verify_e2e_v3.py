"""全流程端到端验证 V3 - 详细日志"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# 启用详细日志
import os

os.environ["LOGURU_LEVEL"] = "DEBUG"

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="DEBUG", format="{time:HH:mm:ss} | {level} | {message}")

from src.analyzer.labeling.generator import LabelGenerator
from src.analyzer.llm_provider import create_llm_provider
from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig
from src.config.manager import ConfigManager


def print_section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


async def main() -> None:
    task_id = 11751534

    print("=" * 60)
    print(f"  全流程端到端验证 V3 - 故障单号: {task_id}")
    print("=" * 60)

    # 1. 配置加载
    print_section("1. 配置加载")
    cm = ConfigManager()
    cm.load()
    cfg = cm.get_config()
    print(f"  LLM Provider:   {cfg.llm.provider} / {cfg.llm.model}")
    print(f"  LLM API Key:    {'已配置' if cfg.llm.api_key else '未配置'}")
    print(f"  LLM Base URL:   {cfg.llm.base_url}")

    # 2. 直接测试 LabelGenerator
    print_section("2. 直接测试 LabelGenerator")
    provider = create_llm_provider(cfg.llm)
    print(f"  Provider 创建: {provider is not None}")

    if provider:
        label_gen = LabelGenerator(llm_provider=provider)
        print(f"  LabelGenerator.is_available: {label_gen.is_available}")

        # 模拟任务数据
        mock_task = {
            "task_id": task_id,
            "title": "[P3] 催缴邮件重复发送",
            "description": "流程实例判断26号为节假日，暂停催缴流程失败后重复处理导致邮件暴增",
            "status": "closed",
            "priority": "P3",
        }
        mock_segments = [
            {"type": "title", "content": "[P3] 催缴邮件重复发送"},
            {"type": "description", "content": "流程实例判断26号为节假日，暂停催缴流程失败后重复处理导致邮件暴增"},
        ]

        try:
            print("  调用 LabelGenerator.generate()...")
            result = await label_gen.generate(mock_task, mock_segments)
            print(f"  标签生成成功: {len(result.labels)} 个标签")
            for label in result.labels[:3]:
                print(f"    - {label.name} ({label.confidence:.2f})")
        except Exception as e:
            import traceback
            print(f"  标签生成失败: {e}")
            traceback.print_exc()

    # 3. 全流程 Pipeline 执行
    print_section("3. 全流程 Pipeline 执行")
    pipeline_cfg = PipelineConfig(
        use_cache=False,
        use_llm=True,
        generate_labels=True,
        analyze_root_cause=True,
        check_rules=True,
        generate_report=True,
        output_path=Path("./output/e2e_v3"),
    )
    pipeline = AnalysisPipeline(config=cm, pipeline_config=pipeline_cfg)

    try:
        result = await pipeline.run_single(task_id)
        print(f"  状态: {'✅ 成功' if not result.error else '❌ 失败: ' + result.error}")

        # 代码变更分析
        print_section("4. 代码变更分析")
        if result.code_change_analysis:
            cca = result.code_change_analysis
            summary = cca.get("summary", {})
            diff_stats = cca.get("diff_stats", {})
            patterns = cca.get("detected_patterns", [])
            analysis_text = cca.get("analysis_text", "")

            print(f"  提交数:       {summary.get('total_commits', 0)}")
            print(f"  文件变更数:   {summary.get('total_files_changed', 0)}")
            print(f"  新增行数:     {diff_stats.get('total_added', 0)}")
            print(f"  删除行数:     {diff_stats.get('total_removed', 0)}")
            print(f"  代码模式数:   {len(patterns)}")
            print(f"  分析文本:     {analysis_text[:200]}...")
        else:
            print("  ⚠️  无代码变更分析")

        # LLM 标签
        print_section("5. LLM 标签生成")
        if result.labels:
            print(f"  生成标签数: {len(result.labels)}")
            for label in result.labels[:5]:
                print(f"    - {label.get('name', '?')} ({label.get('confidence', 0):.2f})")
        else:
            print("  ⚠️  未生成标签")

        # 根因分析
        print_section("6. 根因分析")
        if result.root_causes:
            print(f"  识别根因数: {len(result.root_causes)}")
            for rc in result.root_causes[:3]:
                print(f"    - {str(rc.get('root_cause', rc.get('description', '?')))[:80]}")
        else:
            print("  ⚠️  未识别根因")

        # 规范违规
        print_section("7. 规范违规检测")
        if result.violations:
            print(f"  违规数: {len(result.violations)}")
            for v in result.violations[:5]:
                print(f"    - [{v.get('severity', '?')}] {v.get('rule_name', '')}")
        else:
            print("  ⚠️  无违规")

        # 报告
        print_section("8. 报告生成")
        if result.report:
            print(f"  报告长度: {len(result.report)} 字符")
            # 保存完整报告到文件
            report_dir = Path("./output/e2e_v3")
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / f"report_{task_id}.md"
            report_path.write_text(result.report, encoding="utf-8")
            print(f"  报告已保存: {report_path}")
            print(f"  报告预览:\n{result.report[:600]}...")
        else:
            print("  ⚠️  未生成报告")

        if result.error:
            print_section("❌ 错误")
            print(f"  {result.error}")

    except Exception as e:
        import traceback
        print(f"  ❌ Pipeline 异常: {e}")
        traceback.print_exc()
    finally:
        await pipeline.close()


asyncio.run(main())
