import tempfile
from pathlib import Path

from src.report.generator import ReportGenerator
from src.report.models import BatchReport, ClusterReport


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
            {
                "name": "性能问题",
                "category": "performance",
                "confidence": 0.8,
                "description": "性能瓶颈",
            },
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

    def test_generate_single_with_custom_template(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            template_dir = Path(tmpdir)
            template_file = template_dir / "single.md.j2"
            template_file.write_text("# Custom Template\nTask: {{ title }}", encoding="utf-8")

            generator = ReportGenerator(template_dir=template_dir)
            task_data = {"task_id": 1, "title": "测试任务", "summary": "总结"}
            report = generator.generate_single(task_data)

            assert "Custom Template" in report
            assert "测试任务" in report

    def test_generate_cluster_with_custom_template(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            template_dir = Path(tmpdir)
            template_file = template_dir / "cluster.md.j2"
            template_file.write_text(
                "# Cluster {{ cluster_id }}\nCount: {{ task_count }}", encoding="utf-8"
            )

            generator = ReportGenerator(template_dir=template_dir)
            cluster_report = ClusterReport(
                cluster_id=1,
                task_count=10,
                labels=[],
                common_root_causes=[],
                summary="聚类",
                suggestions=[],
            )
            report = generator.generate_cluster(cluster_report)

            assert "Cluster 1" in report
            assert "Count: 10" in report

    def test_generate_batch_with_custom_template(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            template_dir = Path(tmpdir)
            template_file = template_dir / "batch.md.j2"
            template_file.write_text("# Batch Report\nTotal: {{ total_tasks }}", encoding="utf-8")

            generator = ReportGenerator(template_dir=template_dir)
            batch_report = BatchReport(
                total_tasks=50,
                cluster_count=3,
                cluster_reports=[],
                overall_summary="总结",
                recommendations=[],
            )
            report = generator.generate_batch(batch_report)

            assert "Batch Report" in report
            assert "Total: 50" in report

    def test_save_report_creates_parent_dirs(self, tmp_path):
        generator = ReportGenerator()

        content = "# 测试报告"
        output_path = tmp_path / "subdir" / "test_report.md"

        generator.save_report(content, output_path)

        assert output_path.exists()
        assert output_path.read_text(encoding="utf-8") == content

    def test_render_cluster_markdown(self):
        generator = ReportGenerator()

        cluster_report = ClusterReport(
            cluster_id=1,
            task_count=5,
            labels=[{"name": "标签1", "category": "cat1"}],
            common_root_causes=[{"cause_type": "类型1", "description": "描述1"}],
            summary="聚类总结",
            suggestions=["建议1"],
        )
        report = generator._render_cluster_markdown(cluster_report)

        assert "聚类分析报告" in report
        assert "标签1" in report

    def test_render_batch_markdown(self):
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
            overall_summary="总体总结",
            recommendations=["建议1", "建议2"],
        )
        report = generator._render_batch_markdown(batch_report)

        assert "批量故障分析报告" in report
        assert "100" in report
        assert "建议1" in report


class TestConclusionReviewRender:
    """结论域 Delphi 复审报告渲染（sprint-20260902-77 SLICE-4）。

    撤销项不在 root_causes 中（已被移出主列表），必须在复审块中可见，
    与 confirmed/diverged 根因条目标记形成完整审计视图。
    """

    _RC = {
        "cause_type": "设计缺陷",
        "description": "查询未做分页导致全量加载超时",
        "evidence": ["return orderMapper.queryAll();"],
    }

    def _generate(self, root_causes=None, conclusion_review=None):
        generator = ReportGenerator()
        task_data = {"task_id": 1, "title": "订单导出失败", "summary": "总结"}
        return generator.generate_single(
            task_data, root_causes=root_causes, conclusion_review=conclusion_review
        )

    def test_no_review_renders_no_block(self):
        """未复审（conclusion_review=None）不渲染结论域复审块。"""
        report = self._generate(root_causes=[dict(self._RC)])
        assert "结论域复审" not in report

    def test_confirmed_verdict_annotated(self):
        """confirmed 根因条目附复审确认标记。"""
        rc = {**self._RC, "conclusion_verdict": "confirmed"}
        report = self._generate(root_causes=[rc])
        assert "复审确认" in report

    def test_diverged_verdict_distinct_from_confirmed(self):
        """diverged 根因条目标注专家分歧待人工（与 confirmed 视觉区分）。"""
        rc = {**self._RC, "conclusion_verdict": "diverged"}
        report = self._generate(root_causes=[rc])
        assert "专家分歧" in report
        assert "待人工" in report
        assert "复审确认" not in report

    def test_revoked_items_listed_in_review_block(self):
        """撤销项在结论域复审块中列出（撤销审计不静默消失）。"""
        review = {
            "reviewed_at": "2026-09-02T00:00:00",
            "method": "delphi_multi_expert_consensus",
            "revoked": [
                {**self._RC, "conclusion_verdict": "refuted", "conclusion_reason": "反证不足"}
            ],
        }
        report = self._generate(root_causes=[], conclusion_review=review)
        assert "结论域复审" in report
        assert "设计缺陷" in report
        assert "反证不足" in report

    def test_pending_rebuild_status_highlighted(self):
        """全单撤销 → pending_rebuild 待人工重建提示。"""
        review = {
            "reviewed_at": "t",
            "method": "m",
            "revoked": [{**self._RC, "conclusion_verdict": "refuted"}],
            "conclusion_status": "pending_rebuild",
        }
        report = self._generate(root_causes=[], conclusion_review=review)
        assert "待人工重建" in report

    def test_reviewer_error_annotated(self):
        """全专家失败 → 复审失败待人工标注。"""
        review = {"reviewed_at": "t", "method": "m", "revoked": [], "reviewer_error": True}
        report = self._generate(root_causes=[dict(self._RC)], conclusion_review=review)
        assert "复审失败" in report
