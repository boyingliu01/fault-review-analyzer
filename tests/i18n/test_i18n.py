"""国际化模块测试"""

import pytest
from src.i18n import i18n, _, get_translation, translate_dict


class TestI18n:
    """国际化管理器测试"""

    def test_initialization(self):
        """测试初始化"""
        assert i18n.language == "zh"
        assert i18n.get("report.title") == "故障分析报告"

    def test_translation_zh(self):
        """测试中文翻译"""
        i18n.language = "zh"
        assert i18n.get("report.title") == "故障分析报告"
        assert i18n.get("cluster.size") == "聚类大小"
        assert i18n.get("severity.critical") == "严重"

    def test_translation_en(self):
        """测试英文翻译"""
        i18n.language = "en"
        assert i18n.get("report.title") == "Fault Analysis Report"
        assert i18n.get("cluster.size") == "Cluster Size"
        assert i18n.get("severity.critical") == "Critical"

    def test_fallback_to_key(self):
        """测试未定义翻译时返回键名"""
        assert i18n.get("unknown.key") == "unknown.key"

    def test_translate_dict(self):
        """测试字典翻译"""
        data = {"report.title": "report.title", "cluster.size": "cluster.size"}
        result = translate_dict(data, "en")
        assert result["report.title"] == "Fault Analysis Report"
        assert result["cluster.size"] == "Cluster Size"

    def test_translate_recursive_dict(self):
        """测试递归翻译嵌套字典"""
        data = {
            "report": {
                "title": "report.title",
                "sections": {"cluster": {"id": "cluster.id", "size": "cluster.size"}},
            }
        }
        result = translate_dict(data, "en")
        assert result["report"]["title"] == "Fault Analysis Report"
        assert result["report"]["sections"]["cluster"]["id"] == "Cluster ID"
        assert result["report"]["sections"]["cluster"]["size"] == "Cluster Size"

    def test_context_manager(self):
        """测试上下文管理器"""
        i18n.language = "zh"
        assert i18n.get("report.title") == "故障分析报告"

        with i18n.set_context_language("en"):
            assert i18n.get("report.title") == "Fault Analysis Report"

        assert i18n.get("report.title") == "故障分析报告"

    def test_format_translation(self):
        """测试翻译文本格式化"""
        i18n.language = "zh"
        assert i18n.get("cluster.id", id=1) == "聚类ID"
        # 测试带参数的翻译
        i18n.load_translations({"zh": {"test.param": "参数值: {value}"}})
        assert i18n.get("test.param", value="123") == "参数值: 123"

    def test_load_translations(self):
        """测试加载翻译"""
        initial_count = len(i18n.get_available_languages())
        i18n.load_translations({"fr": {"report.title": "Rapport d'Analyse"}})
        assert "fr" in i18n.get_available_languages()
        assert len(i18n.get_available_languages()) == initial_count + 1

    def test_get_available_languages(self):
        """测试获取可用语言"""
        assert {"zh", "en"}.issubset(set(i18n.get_available_languages()))

    def test_singleton_behavior(self):
        """测试单例行为"""
        from src.i18n import I18nManager

        manager1 = I18nManager()
        manager2 = I18nManager()
        assert manager1 is manager2

    def test_convenience_function(self):
        """测试便捷函数"""
        i18n.language = "zh"
        assert _("report.title") == "故障分析报告"
        i18n.language = "en"
        assert _("report.title") == "Fault Analysis Report"


class TestDirectTranslation:
    """测试直接调用翻译函数"""

    def test_get_translation_zh(self):
        """测试直接获取中文翻译"""
        assert get_translation("report.title", "zh") == "故障分析报告"

    def test_get_translation_en(self):
        """测试直接获取英文翻译"""
        assert get_translation("report.title", "en") == "Fault Analysis Report"

    def test_unsupported_language(self):
        """测试不支持的语言"""
        assert get_translation("report.title", "fr") == "故障分析报告"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
