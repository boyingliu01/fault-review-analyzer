"""重复单识别引擎测试（feat/duplicate-conclusion-reuse R8）。

三层识别优先级：
- 第〇层 issue no 相同（Excel 映射表）：组内主单已复盘 -> 直接复用，不比对内容
- 第一层显式 relationship：预留（当前 API 全空），内容过门槛即复用
- 第二层内容相似度：desc>=0.90 或 diff>=0.80 -> strong 自动复用；
  过候选门槛但未达强一致 -> borderline 出清单

主从规则：已有复审结论优先 -> createdDate 更早 -> task_id 更小。
文本用可精确预测 SequenceMatcher.ratio 的短串（相似度指两单"交叉"
比较，同一字符串自身 sim 恒为 1.0）：
"abcdef" vs "abcdef"=1.0、vs "abcxyz"/"abcdxy"=0.667、vs "xyzuvw"=0.0。
"""

import pytest

from src.analyzer.duplicate.detector import (
    PAIR_SIM_THRESHOLD,
    STRONG_DESC_SIM,
    STRONG_DIFF_SIM,
    TITLE_SIM_THRESHOLD,
    DuplicateDetector,
    RelatedPair,
    TaskCandidate,
    candidate_from_task,
)

SIM_A = "abcdef"
SIM_B = "abcxyz"  # sim(SIM_A, SIM_B) = 0.667
SIM_C = "abcdxy"  # sim(SIM_A, SIM_C) = 0.667，∈ [0.60, 0.75) 候选门槛临界样本
DISSIM = "xyzuvw"  # sim(SIM_A, DISSIM) = 0.0


def cand(
    tid: int,
    title: str = "",
    desc: str = "",
    diffs: tuple[str, ...] = (),
    related: tuple[str, ...] = (),
    reviewed: bool = False,
    created: str = "",
    issue_no: str = "",
) -> TaskCandidate:
    return TaskCandidate(
        task_id=tid,
        title=title,
        description=desc,
        diffs=diffs,
        related_task_nos=related,
        has_reviewed_conclusion=reviewed,
        created_date=created,
        issue_no=issue_no,
    )


class TestThresholdConstants:
    def test_threshold_values(self):
        assert TITLE_SIM_THRESHOLD == 0.60
        assert PAIR_SIM_THRESHOLD == 0.75
        assert STRONG_DESC_SIM == 0.90
        assert STRONG_DIFF_SIM == 0.80


class TestIssueNoLayer:
    """第〇层：issue no 相同 -> 主单已复盘直接复用，不比对内容。"""

    def test_issue_no_match_reuses_even_if_content_diverges(self):
        det = DuplicateDetector()
        pair = det.find_related(
            cand(100, title=DISSIM, desc=DISSIM, issue_no="IS22976"),
            [cand(200, title=DISSIM, desc=SIM_A, reviewed=True, issue_no="IS22976")],
        )
        assert pair is not None
        assert pair.source == "issue_no"
        assert pair.verdict == "strong"
        assert (pair.master_id, pair.slave_id) == (200, 100)

    def test_issue_no_match_requires_reviewed_master(self):
        det = DuplicateDetector()
        pair = det.find_related(
            cand(100, issue_no="IS22976"),
            [cand(200, issue_no="IS22976", reviewed=False)],
        )
        assert pair is None

    def test_issue_no_target_is_master_returns_none(self):
        # target 已有复审结论（组内主单）-> 无需复用
        det = DuplicateDetector()
        pair = det.find_related(
            cand(100, issue_no="IS22976", reviewed=True),
            [cand(200, issue_no="IS22976", reviewed=False)],
        )
        assert pair is None

    def test_issue_no_group_all_pairs_share_master(self):
        det = DuplicateDetector()
        group = [
            cand(100, issue_no="IS29704", reviewed=True, created="2026-01-01"),
            cand(200, issue_no="IS29704", reviewed=True, created="2026-01-02"),
            cand(300, issue_no="IS29704", reviewed=False),
        ]
        pairs = det.find_all_pairs(group)
        assert len(pairs) == 2
        assert {p.slave_id for p in pairs} == {200, 300}
        assert all(p.master_id == 100 for p in pairs)  # 复审过且最早者为主

    def test_issue_group_skips_content_scan(self):
        # issue 层覆盖的单不再参与内容层扫描（避免同一对重复配对）
        det = DuplicateDetector()
        group = [
            cand(100, issue_no="IS1", reviewed=True, title=SIM_A, desc=SIM_A),
            cand(200, issue_no="IS1", reviewed=True, title=SIM_A, desc=SIM_A),
        ]
        pairs = det.find_all_pairs(group)
        assert len(pairs) == 1
        assert pairs[0].source == "issue_no"

    def test_issue_group_without_reviewed_master_skipped(self):
        # 组内全部未复盘 -> 无可复用结论，不生成配对
        det = DuplicateDetector()
        group = [
            cand(100, issue_no="IS1", reviewed=False),
            cand(200, issue_no="IS1", reviewed=False),
        ]
        assert det.find_all_pairs(group) == []


class TestContentMatching:
    """第二层：内容相似度分层判定。"""

    def test_strong_by_desc(self):
        det = DuplicateDetector()
        pair = det.find_related(
            cand(100, title=SIM_A, desc=SIM_A),
            [cand(200, title=SIM_A, desc=SIM_A, reviewed=True)],
        )
        assert pair is not None
        assert pair.verdict == "strong"
        assert pair.source == "content"
        assert pair.desc_sim == pytest.approx(1.0)

    def test_strong_by_diff(self):
        det = DuplicateDetector()
        pair = det.find_related(
            cand(100, title=SIM_A, desc=SIM_B, diffs=("abcdefgh",)),
            [cand(200, title=SIM_A, desc=SIM_A, diffs=("abcdefgh",), reviewed=True)],
        )
        assert pair is not None
        assert pair.verdict == "strong"  # desc 0.667 < 0.90 但 diff 1.0 >= 0.80
        assert pair.diff_sim == pytest.approx(1.0)

    def test_borderline_when_below_strong(self):
        det = DuplicateDetector()
        pair = det.find_related(
            cand(100, title=SIM_A, desc=SIM_B, diffs=("aaaaaa",)),
            [cand(200, title=SIM_A, desc=SIM_A, diffs=("bbbbbb",), reviewed=True)],
        )
        assert pair is not None
        assert pair.verdict == "borderline"  # 过候选门槛但 desc/diff 均未达强一致

    def test_below_pair_threshold_returns_none(self):
        det = DuplicateDetector()
        pair = det.find_related(
            cand(100, title=SIM_A, desc=SIM_C),  # max(t 0.667, d 0.667) < 0.75
            [cand(200, title=SIM_C, desc=SIM_A, reviewed=True)],
        )
        assert pair is None

    def test_title_gate_blocks_low_title(self):
        # title 0.0 < 0.60 粗筛拦截（desc 在 gate 之后才参与）
        det = DuplicateDetector()
        pair = det.find_related(
            cand(100, title=DISSIM, desc=SIM_A),
            [cand(200, title=SIM_A, desc=DISSIM, reviewed=True)],
        )
        assert pair is None

    def test_single_side_diff_not_strong(self):
        # 一方无 diff（如样例对 B 单）不能靠单边 diff 判强一致
        det = DuplicateDetector()
        pair = det.find_related(
            cand(100, title=SIM_A, desc=SIM_B, diffs=("abcdefgh",)),
            [cand(200, title=SIM_A, desc=SIM_A, diffs=(), reviewed=True)],
        )
        assert pair is not None
        assert pair.verdict == "borderline"

    def test_pick_best_candidate(self):
        det = DuplicateDetector()
        pair = det.find_related(
            cand(100, title=SIM_A, desc=SIM_A),
            [
                cand(200, title=SIM_A, desc=SIM_B, reviewed=True),  # desc 0.667
                cand(300, title=SIM_A, desc=SIM_A, reviewed=True),  # desc 1.0
            ],
        )
        assert pair is not None
        assert pair.master_id == 300  # 相似度最高者优先

    def test_content_find_all_pairs(self):
        det = DuplicateDetector()
        group = [
            cand(100, title=SIM_A, desc=SIM_A, reviewed=True),
            cand(200, title=SIM_A, desc=SIM_A, reviewed=True),
            cand(300, title=DISSIM, desc=DISSIM, reviewed=True),
        ]
        pairs = det.find_all_pairs(group)
        assert len(pairs) == 1
        assert (pairs[0].master_id, pairs[0].slave_id) == (100, 200)


class TestExplicitRelationLayer:
    """第一层：显式 relationship 关联跳过 title 粗筛。"""

    def test_explicit_bypasses_title_gate(self):
        # title 0.0 本会被粗筛拦截，显式关系跳过 gate（desc 1.0 过候选门槛）
        det = DuplicateDetector()
        pair = det.find_related(
            cand(100, title=DISSIM, desc=SIM_B, related=("200",)),
            [cand(200, title=SIM_A, desc=SIM_B, related=("100",), reviewed=True)],
        )
        assert pair is not None
        assert pair.source == "explicit"
        assert pair.verdict == "strong"

    def test_explicit_but_content_diverges_rejected(self):
        # 显式关系仍需内容过候选门槛（基本一致才复用）：t 0.0 / d 0.0
        det = DuplicateDetector()
        pair = det.find_related(
            cand(100, title=DISSIM, desc=SIM_A, related=("200",)),
            [cand(200, title=SIM_A, desc=DISSIM, related=("100",), reviewed=True)],
        )
        assert pair is None


class TestMasterResolution:
    """主从规则：复审结论优先 -> createdDate 更早 -> task_id 更小。"""

    def test_reviewed_first(self):
        det = DuplicateDetector()
        assert det.resolve_master(cand(100, reviewed=False), cand(200, reviewed=True)) == 200

    def test_created_earlier_wins(self):
        det = DuplicateDetector()
        assert (
            det.resolve_master(
                cand(100, created="2026-01-04 15:30:00"),
                cand(200, created="2026-01-04 15:29:00"),
            )
            == 200
        )

    def test_task_id_tiebreak(self):
        det = DuplicateDetector()
        assert (
            det.resolve_master(cand(300, created="2026-01-01"), cand(200, created="2026-01-01"))
            == 200
        )

    def test_self_excluded_in_find_related(self):
        det = DuplicateDetector()
        pair = det.find_related(
            cand(100, title=SIM_A, desc=SIM_A),
            [cand(100, title=SIM_A, desc=SIM_A, reviewed=True)],
        )
        assert pair is None


class TestCandidateFactory:
    """candidate_from_task：从 cache 任务 dict 构造候选。"""

    def test_extracts_fields(self):
        task = {
            "task_id": 11757372,
            "title": "GOMO-BXportin 号码接口报错",
            "description": "接口报错",
            "create_time": "2026-01-04 15:30:00",
            "development": {"commits": [{"diff": "diff --git a/x"}, {"diff": ""}]},
        }
        rec = {
            "conclusion_review": {"reviewed_at": "2026-09-03T00:00:00"},
            "root_causes": [{"cause_type": "x"}],
        }
        c = candidate_from_task(task, rec, issue_no="IS22976")
        assert c.task_id == 11757372
        assert c.diffs == ("diff --git a/x",)  # 空 diff 剔除
        assert c.has_reviewed_conclusion is True
        assert c.issue_no == "IS22976"
        assert c.created_date == "2026-01-04 15:30:00"

    def test_missing_development_safe(self):
        c = candidate_from_task({"task_id": 1, "development": None})
        assert c.diffs == ()

    def test_reviewed_flag_requires_both(self):
        task = {"task_id": 1}
        assert candidate_from_task(task, None).has_reviewed_conclusion is False
        assert (
            candidate_from_task(
                task, {"conclusion_review": {"reviewed_at": "t"}}
            ).has_reviewed_conclusion
            is False
        )
        assert (
            candidate_from_task(task, {"root_causes": [{"x": 1}]}).has_reviewed_conclusion is False
        )
        assert (
            candidate_from_task(
                task,
                {"conclusion_review": {"reviewed_at": "t"}, "root_causes": [{"x": 1}]},
            ).has_reviewed_conclusion
            is True
        )

    def test_related_task_nos_passthrough(self):
        c = candidate_from_task({"task_id": 1, "related_task_nos": ["200", "300"]})
        assert c.related_task_nos == ("200", "300")


class TestRelatedPairShape:
    def test_pair_fields(self):
        pair = RelatedPair(
            master_id=200,
            slave_id=100,
            title_sim=1.0,
            desc_sim=1.0,
            diff_sim=0.0,
            verdict="strong",
            source="issue_no",
        )
        assert pair.master_id == 200
        assert pair.slave_id == 100
        assert pair.source == "issue_no"
