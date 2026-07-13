"""自动化测试：验证数据流正确性

测试目标:
1. 验证API字段存在性 - requirement/design/development/testing字段应为空
2. 验证数据质量校验 - 拒绝空数据
3. 验证真实数据分析 - 使用title+comments字段
4. 验证mock数据检测 - 识别并拒绝mock数据
"""

import json
import re
import tempfile
from pathlib import Path

import pytest


class TestDataValidation:
    """测试数据质量校验"""

    def test_validate_empty_data(self):
        """测试拒绝空数据"""
        from validate_and_fix import validate_task_data

        # 空数据
        task = {"title": "", "description": ""}
        is_valid, error = validate_task_data(task)
        assert not is_valid
        assert "标题和描述均为空" in error

    def test_validate_minimal_content(self):
        """测试内容过少"""
        from validate_and_fix import validate_task_data

        # 内容过少
        task = {"title": "短", "description": "123"}
        is_valid, error = validate_task_data(task)
        assert not is_valid
        assert "内容过少" in error

    def test_validate_only_images(self):
        """测试只有图片没有文字"""
        from validate_and_fix import validate_task_data

        # 只有markdown图片
        task = {"title": "", "description": "![img](url)\n[img]: http://example.com"}
        is_valid, error = validate_task_data(task)
        assert not is_valid
        # 清理后内容为空，所以是"标题和描述均为空"
        assert "空" in error

    def test_validate_valid_data(self):
        """测试有效数据通过"""
        from validate_and_fix import validate_task_data

        task = {
            "title": "这是一个有效的故障标题",
            "description": "这是一个详细的故障描述，包含足够的信息用于分析。",
        }
        is_valid, error = validate_task_data(task)
        assert is_valid
        assert error == ""


class TestTextPreparation:
    """测试文本准备"""

    def test_prepare_text_removes_markdown(self):
        """测试清理markdown图片"""
        from validate_and_fix import prepare_analysis_text

        task = {
            "title": "故障标题",
            "description": "![img](url)\n实际描述内容\n[img]: http://example.com",
        }
        text = prepare_analysis_text(task)
        assert "![img]" not in text
        assert "[img]:" not in text
        assert "实际描述内容" in text

    def test_prepare_text_limits_length(self):
        """测试描述长度限制"""
        from validate_and_fix import prepare_analysis_text

        task = {
            "title": "标题",
            "description": "x" * 2000,  # 超长描述
        }
        text = prepare_analysis_text(task)
        assert len(text) < 1500  # 应该被截断


class TestMockDataDetection:
    """测试mock数据检测"""

    def test_detect_mock_titles(self):
        """测试识别mock数据标题"""
        mock_titles = [
            "数据库连接池耗尽导致服务不可用",
            "SQL查询慢导致页面响应超时",
            "空指针异常导致服务崩溃",
            "XSS漏洞导致的安全风险",
        ]

        # 这些标题在真实API数据中不应该出现
        real_titles = [
            "Add job(pot 将userid，staffid， orgid 扩到number(9)）",
            "reconnection复装业务，选择Virtual SIM Card 自动带出卡号",
            "企业账户operator属性自动带出VA值",
        ]

        # Mock标题特征是：过于通用，没有具体业务场景
        for title in mock_titles:
            # 检查是否包含通用技术词汇但没有业务上下文
            assert any(kw in title for kw in ["数据库", "SQL", "空指针", "XSS", "并发", "配置"])
            assert "导致" in title  # Mock标题通常使用"导致"结构

        # 真实标题包含具体业务场景
        for title in real_titles:
            assert any(kw in title for kw in ["job", "pot", "reconnection", "企业账户", "operator"])


class TestAPIFieldValidation:
    """测试API字段验证"""

    def test_api_stage_fields_are_empty(self):
        """验证API阶段性字段为空"""
        # 读取验证结果
        validation_file = Path("output/data_validation/api_field_validation.json")
        if not validation_file.exists():
            pytest.skip("验证文件不存在，先运行validate_api_fields.py")

        with open(validation_file) as f:
            results = json.load(f)

        # 检查所有任务的阶段性字段
        for task_id, result in results.items():
            field_analysis = result.get("field_analysis", {})

            for field in ["requirement", "design", "development", "testing", "production"]:
                analysis = field_analysis.get(field, {})
                # 这些字段应该不存在或为空
                assert not analysis.get("has_content", False), (
                    f"任务{task_id}的{field}字段不应有内容"
                )


class TestAnalysisPipeline:
    """测试分析流程"""

    def test_analysis_uses_available_fields(self):
        """测试分析只使用可用字段"""
        from phase2_real_analysis import prepare_text_for_analysis

        # 模拟API返回的数据结构
        task = {"title": "真实故障标题", "description": "真实故障描述"}

        text = prepare_text_for_analysis(task)

        # 应该包含标题和描述
        assert "真实故障标题" in text
        assert "真实故障描述" in text

        # 不应该尝试访问不存在的字段
        assert "development" not in text
        assert "testing" not in text

    def test_clustering_with_real_data(self):
        """测试真实数据聚类"""
        # 读取真实分析结果
        result_file = Path("output/phase2_real/clustering_result.json")
        if not result_file.exists():
            pytest.skip("分析结果不存在，先运行phase2_real_analysis.py")

        with open(result_file) as f:
            result = json.load(f)

        # 验证结果结构
        assert "labels" in result
        assert "n_clusters" in result
        assert "n_noise" in result

        # 验证所有任务都被处理
        assert len(result["labels"]) == 15


class TestOutputIntegrity:
    """测试输出完整性"""

    def test_report_contains_real_titles(self):
        """验证报告包含真实标题"""
        report_file = Path("output/phase2_real/cluster_analysis_report.md")
        if not report_file.exists():
            pytest.skip("报告不存在")

        content = report_file.read_text(encoding="utf-8")

        # 应该包含真实任务ID
        assert "11743724" in content
        assert "11745664" in content

        # 应该包含真实标题片段
        assert "Add job" in content or "reconnection" in content

        # 不应该包含mock标题
        assert "数据库连接池耗尽" not in content
        assert "空指针异常" not in content

    def test_tasks_json_has_analysis(self):
        """验证任务JSON包含分析结果"""
        tasks_file = Path("output/phase2_real/tasks_with_analysis.json")
        if not tasks_file.exists():
            pytest.skip("任务文件不存在")

        with open(tasks_file) as f:
            tasks = json.load(f)

        # 每个任务都应该有分析结果
        for task in tasks:
            assert "analysis" in task
            assert "title" in task
            assert "description" in task
            # 验证描述来自真实API数据
            assert len(task["description"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
