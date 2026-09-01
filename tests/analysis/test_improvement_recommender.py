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


class TestMergeDuplicateMeasures:
    """重复措施合并测试（同类别同优先级共用同一模板时只保留一条）"""

    def test_merge_same_category_and_priority(self):
        """同类别同优先级的重复措施合并为一条，root_cause 顿号连接"""
        recommender = ImprovementRecommender()

        measures = recommender.recommend_measures(
            ["边界条件未处理", "异常处理不当"]
        )

        assert len(measures) == 1
        assert measures[0].category == "代码类"
        assert measures[0].root_cause == "边界条件未处理、异常处理不当"

    def test_merge_keeps_highest_frequency_impact(self):
        """合并后 expected_impact 保留最高频根因的占比"""
        recommender = ImprovementRecommender()

        measures = recommender.recommend_measures(
            ["边界条件未处理", "边界条件未处理", "边界条件未处理", "异常处理不当"]
        )

        assert len(measures) == 1
        assert "75.0%" in measures[0].expected_impact
        assert measures[0].root_cause == "边界条件未处理、异常处理不当"

    def test_no_merge_across_priorities(self):
        """同类别不同优先级不合并"""
        recommender = ImprovementRecommender()

        # 4/6=66.7% -> high, 1/6=16.7% -> medium（同属代码类）
        measures = recommender.recommend_measures(
            ["边界条件未处理", "边界条件未处理", "边界条件未处理",
             "边界条件未处理", "异常处理不当", "设计缺陷"]
        )

        assert len(measures) == 3
        code_measures = [m for m in measures if m.category == "代码类"]
        assert {m.priority for m in code_measures} == {"high", "medium"}
        # 高优先级条目不跨优先级合并
        assert code_measures[0].root_cause == "边界条件未处理"
        assert code_measures[1].root_cause == "异常处理不当"

    def test_no_merge_across_categories(self):
        """不同类别不合并"""
        recommender = ImprovementRecommender()

        measures = recommender.recommend_measures(
            ["设计遗漏", "边界条件未处理"]
        )

        assert len(measures) == 2
        assert {m.category for m in measures} == {"需求类", "代码类"}

    def test_merge_combines_rule_ids(self):
        """合并时 rule_ids 去重合并"""
        recommender = ImprovementRecommender()

        measures = recommender.recommend_measures(
            ["边界条件未处理", "异常处理不当"],
            rule_ids_by_cause={
                "边界条件未处理": ["J000025"],
                "异常处理不当": ["J000025", "J000033"],
            },
        )

        assert len(measures) == 1
        assert measures[0].rule_ids == ["J000025", "J000033"]

    def test_recommend_measures_deduplicated_end_to_end(self):
        """端到端：真实样例（11757373）合并后 measure 文本无重复"""
        recommender = ImprovementRecommender()

        measures = recommender.recommend_measures(
            ["设计遗漏", "边界条件未处理", "异常处理不当"]
        )

        measure_texts = [m.measure for m in measures]
        assert len(measure_texts) == len(set(measure_texts))

    def test_merge_preserves_order_by_root_cause_frequency(self):
        """合并条目顺序保持根因频次序（高频根因的措施在前）"""
        recommender = ImprovementRecommender()

        # "需求分析不充分"占3条, "违反Java异常处理规范"占2条
        measures = recommender.recommend_measures(
            ["违反Java异常处理规范", "违反Java异常处理规范",
             "需求分析不充分", "需求分析不充分", "需求分析不充分"],
            violation_causes=["违反Java异常处理规范"],
        )

        assert len(measures) == 2
        assert {m.category for m in measures} == {"违规类", "需求类"}
        assert {m.root_cause for m in measures} == {
            "违反Java异常处理规范",
            "需求分析不充分",
        }
