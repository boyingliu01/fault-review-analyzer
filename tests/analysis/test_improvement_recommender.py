"""改进措施推荐器测试套件"""

from src.analysis.improvement_recommender import (
    ImprovementMeasure,
    ImprovementRecommender,
    RootCauseFrequency,
)


class TestImprovementMeasure:
    """改进措施数据模型测试"""

    def test_create_measure(self):
        """测试创建改进措施"""
        measure = ImprovementMeasure(
            root_cause="需求遗漏",
            measure="建立需求评审checklist",
            acceptance_criteria="所有需求必须经过评审",
            expected_impact="减少30%需求遗漏故障",
            priority="high",
        )

        assert measure.root_cause == "需求遗漏"
        assert measure.priority == "high"


class TestImprovementRecommender:
    """改进措施推荐器测试套件"""

    def test_create_recommender(self):
        """测试创建推荐器"""
        recommender = ImprovementRecommender()
        assert recommender is not None

    def test_calculate_frequencies(self):
        """测试计算根因频率"""
        recommender = ImprovementRecommender()

        root_causes = [
            "需求遗漏",
            "需求遗漏",
            "设计缺陷",
            "代码bug",
            "代码bug",
            "代码bug",
        ]

        frequencies = recommender.calculate_frequencies(root_causes)

        assert len(frequencies) == 3
        assert frequencies[0].root_cause == "代码bug"
        assert frequencies[0].count == 3
        assert frequencies[0].percentage == 50.0

    def test_generate_measure_for_violation(self):
        """测试为违规根因生成改进措施"""
        recommender = ImprovementRecommender()

        freq = RootCauseFrequency(
            root_cause="违反Java异常处理规范",
            count=10,
            percentage=25.0,
        )

        measure = recommender._generate_measure_for_root_cause(freq, is_violation=True)

        assert measure is not None
        assert "Java" in measure.measure or "规范" in measure.measure
        assert measure.priority == "high"

    def test_generate_measure_for_non_violation(self):
        """测试为非违规根因生成改进措施"""
        recommender = ImprovementRecommender()

        freq = RootCauseFrequency(
            root_cause="需求分析不充分",
            count=8,
            percentage=15.0,  # 低于20%，应该是medium
        )

        measure = recommender._generate_measure_for_root_cause(freq, is_violation=False)

        assert measure is not None
        assert measure.priority == "medium"

    def test_recommend_measures(self):
        """测试推荐改进措施"""
        recommender = ImprovementRecommender()

        root_causes = [
            "违反Java异常处理规范",
            "违反Java异常处理规范",
            "需求分析不充分",
            "需求分析不充分",
            "需求分析不充分",
            "数据库连接泄漏",
        ]

        measures = recommender.recommend_measures(
            root_causes,
            violation_causes=["违反Java异常处理规范", "数据库连接泄漏"],
        )

        assert len(measures) > 0
        # 违规根因应该排在前面
        assert measures[0].priority == "high"

    def test_recommend_measures_empty(self):
        """测试空根因列表"""
        recommender = ImprovementRecommender()

        measures = recommender.recommend_measures([])

        assert len(measures) == 0

    def test_sort_by_priority(self):
        """测试按优先级排序"""
        recommender = ImprovementRecommender()

        measures = [
            ImprovementMeasure(
                root_cause="根因1",
                measure="措施1",
                acceptance_criteria="标准1",
                expected_impact="影响1",
                priority="medium",
            ),
            ImprovementMeasure(
                root_cause="根因2",
                measure="措施2",
                acceptance_criteria="标准2",
                expected_impact="影响2",
                priority="high",
            ),
            ImprovementMeasure(
                root_cause="根因3",
                measure="措施3",
                acceptance_criteria="标准3",
                expected_impact="影响3",
                priority="low",
            ),
        ]

        sorted_measures = recommender._sort_by_priority(measures)

        assert sorted_measures[0].priority == "high"
        assert sorted_measures[1].priority == "medium"
        assert sorted_measures[2].priority == "low"

    def test_generate_report(self):
        """测试生成改进措施报告"""
        recommender = ImprovementRecommender()

        measures = [
            ImprovementMeasure(
                root_cause="需求遗漏",
                measure="建立需求评审机制",
                acceptance_criteria="所有需求必须经过评审",
                expected_impact="减少30%需求遗漏故障",
                priority="high",
            ),
            ImprovementMeasure(
                root_cause="代码bug",
                measure="加强代码审查",
                acceptance_criteria="所有代码必须经过CR",
                expected_impact="减少20%代码bug",
                priority="medium",
            ),
        ]

        report = recommender.generate_report(measures)

        assert "需求遗漏" in report
        assert "建立需求评审机制" in report
        assert "高优先级" in report  # 报告输出中文优先级

    def test_filter_by_priority(self):
        """测试按优先级筛选"""
        recommender = ImprovementRecommender()

        measures = [
            ImprovementMeasure(
                root_cause="根因1",
                measure="措施1",
                acceptance_criteria="标准1",
                expected_impact="影响1",
                priority="high",
            ),
            ImprovementMeasure(
                root_cause="根因2",
                measure="措施2",
                acceptance_criteria="标准2",
                expected_impact="影响2",
                priority="medium",
            ),
            ImprovementMeasure(
                root_cause="根因3",
                measure="措施3",
                acceptance_criteria="标准3",
                expected_impact="影响3",
                priority="high",
            ),
        ]

        filtered = recommender.filter_by_priority(measures, "high")

        assert len(filtered) == 2
        assert all(m.priority == "high" for m in filtered)
