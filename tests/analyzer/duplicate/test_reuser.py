"""结论复用器测试（feat/duplicate-conclusion-reuse R8）。

apply_reused_conclusion：从单记录整体替换为主单结论 + 复审状态，
标记 reused_from 审计（主单号、相似度证据、复用时间），其余字段零污染。
"""

from typing import Any

from src.analyzer.duplicate.detector import RelatedPair
from src.analyzer.duplicate.reuser import apply_reused_conclusion

MASTER_REC: dict[str, Any] = {
    "urId": 11757372,
    "root_causes": [{"cause_type": "设计缺陷", "description": "查询未做分页"}],
    "conclusion_review": {
        "reviewed_at": "2026-09-03T12:00:00",
        "method": "delphi_multi_expert_consensus",
        "items": [],
    },
    "deep_root_causes": {"deep_root_causes": ["深度结论A"]},
    "violations": [{"rule_id": "security-001"}],
    "image_evidence": "截图OCR",
}

SLAVE_REC: dict[str, Any] = {
    "urId": 11757373,
    "root_causes": [{"cause_type": "数据问题", "description": "旧结论"}],
    "violations": [{"rule_id": "perf-002"}],
    "improvements": [{"action": "旧改进"}],
    "image_evidence": "从单截图OCR",
}

PAIR = RelatedPair(
    master_id=11757372,
    slave_id=11757373,
    title_sim=0.596,
    desc_sim=1.0,
    diff_sim=0.0,
    verdict="strong",
    source="issue_no",
)


class TestApplyReusedConclusion:
    def test_copies_root_causes_and_review(self):
        out = apply_reused_conclusion(SLAVE_REC, MASTER_REC, PAIR)
        assert out["root_causes"] == MASTER_REC["root_causes"]
        assert out["conclusion_review"]["reviewed_at"] == "2026-09-03T12:00:00"
        reused = out["conclusion_review"]["reused_from"]
        assert reused["master_urId"] == 11757372
        assert reused["source"] == "issue_no"
        assert reused["desc_sim"] == 1.0
        assert reused["reused_at"]

    def test_deep_root_causes_copied(self):
        out = apply_reused_conclusion(SLAVE_REC, MASTER_REC, PAIR)
        assert out["deep_root_causes"] == {"deep_root_causes": ["深度结论A"]}

    def test_slave_other_fields_untouched(self):
        out = apply_reused_conclusion(SLAVE_REC, MASTER_REC, PAIR)
        assert out["violations"] == [{"rule_id": "perf-002"}]
        assert out["improvements"] == [{"action": "旧改进"}]
        assert out["image_evidence"] == "从单截图OCR"
        assert out["urId"] == 11757373

    def test_pure_function_inputs_immutable(self):
        import copy

        slave_snapshot = copy.deepcopy(SLAVE_REC)
        master_snapshot = copy.deepcopy(MASTER_REC)
        apply_reused_conclusion(SLAVE_REC, MASTER_REC, PAIR)
        assert slave_snapshot == SLAVE_REC
        assert master_snapshot == MASTER_REC

    def test_master_review_missing_safe(self):
        bare = {"urId": 200, "root_causes": [{"cause_type": "x"}]}
        out = apply_reused_conclusion(SLAVE_REC, bare, PAIR)
        assert out["root_causes"] == [{"cause_type": "x"}]
        assert out["conclusion_review"]["reused_from"]["master_urId"] == 200
        assert "items" not in out["conclusion_review"]

    def test_deep_copy_isolates_master(self):
        out = apply_reused_conclusion(SLAVE_REC, MASTER_REC, PAIR)
        out["root_causes"][0]["description"] = "被篡改"
        assert MASTER_REC["root_causes"][0]["description"] == "查询未做分页"
