import pytest
from pathlib import Path
from src.report.generator import ReportGenerator


class TestReportGenerator:
    def test_generate_single_report(self):
        generator = ReportGenerator()

        task_data = {
            "task_id": 123,
            "title": "测试任务",
            "summary": "测试总结",
        }

        report = generator.generate_single(task_data)

        assert "测试任务" in report
        assert "测试总结" in report
        assert "故障复盘分析报告" in report

    def test_generate_single_with_segments(self):
        generator = ReportGenerator()

        task_data = {
            "task_id": 1,
            "title": "测试",
            "summary": "总结",
        }

        segments = [
            {"type": "开发阶段", "content": "开发内容"},
            {"type": "测试阶段", "content": "测试内容"},
        ]

        report = generator.generate_single(task_data, segments=segments)

        assert "开发阶段" in report
        assert "测试阶段" in report

    def test_generate_single_with_labels(self):
        generator = ReportGenerator()

        task_data = {"task_id": 1, "title": "测试", "summary": "总结"}

        labels = [
            {"name": "性能问题", "category": "performance", "confidence": 0.8, "description": "性能瓶颈"},
        ]

        report = generator.generate_single(task_data, labels=labels)

        assert "性能问题" in report
        assert "performance" in report

    def test_generate_single_with_root_causes(self):
        generator = ReportGenerator()

        task_data = {"task_id": 1, "title": "测试", "summary": "总结"}

        root_causes = [
            {
                "cause_type": "编码错误",
                "description": "代码逻辑错误",
                "evidence": ["证据1"],
                "confidence": 0.9,
            }
        ]

        report = generator.generate_single(task_data, root_causes=root_causes)

        assert "编码错误" in report
        assert "代码逻辑错误" in report

    def test_generate_single_with_suggestions(self):
        generator = ReportGenerator()

        task_data = {"task_id": 1, "title": "测试", "summary": "总结"}

        suggestions = [
            "建议1: 优化代码",
            "建议2: 增加测试",
        ]

        report = generator.generate_single(task_data, suggestions=suggestions)

        assert "建议1" in report

    def test_generate_cluster_report(self):
        from src.report.models import ClusterReport

        generator = ReportGenerator()

        cluster_report = ClusterReport(
            cluster_id=1,
            task_count=10,
            labels=[{"name": "性能问题", "category": "perf"}],
            common_root_causes=[],
            summary="这是一个聚类",
            suggestions=["建议1"],
        )

        report = generator.generate_cluster(cluster_report)

        assert "聚类分析报告" in report
        assert "10" in report

    def test_generate_batch_report(self):
        from src.report.models import BatchReport, ClusterReport

        generator = ReportGenerator()

        batch_report = BatchReport(
            total_tasks=100,
            cluster_count=5,
            cluster_reports=[
                ClusterReport(
                    cluster_id=1,
                    task_count=20,
                    labels=[],
                    common_root_causes=[],
                    summary="聚类1",
                    suggestions=[],
                )
            ],
            overall_summary="批量分析总结",
            recommendations=["建议1"],
        )

        report = generator.generate_batch(batch_report)

        assert "批量故障分析报告" in report
        assert "100" in report

    def test_save_report(self, tmp_path):
        generator = ReportGenerator()

        content = "# 测试报告"
        output_path = tmp_path / "test_report.md"

        generator.save_report(content, output_path)

        assert output_path.exists()
        assert output_path.read_text(encoding="utf-8") == content

    def test_render_single_markdown(self):
        generator = ReportGenerator()

        task_data = {"task_id": 1, "title": "测试", "summary": "总结"}
        report = generator._render_single_markdown(task_data, None, None, None, None)

        assert "故障复盘分析报告" in report
        assert "测试" in report
