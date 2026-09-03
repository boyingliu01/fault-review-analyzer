"""重复单识别引擎（三层优先级）。

背景：主分支与现网分支各开一单修复（如 11757372/11757373），处理内容
与代码修改基本一致，独立复盘产出不一致结论。识别三层优先级：

- 第〇层 issue no 相同（泄漏缺陷复盘映射表 urId->Issue No）：确定性关联，
  组内主单已有复盘结论即直接复用，不比对内容（原始 issue 相同即同一问题）
- 第一层显式 relationship（研发云 relatedTaskList，当前 API 未填充、预留）：
  内容过候选门槛即复用
- 第二层内容相似度：desc>=STRONG_DESC_SIM 或 diff>=STRONG_DIFF_SIM -> strong
  自动复用；过候选门槛但未达强一致 -> borderline 出清单人工确认

主从规则（组内/对内复用来源）：已有复审结论优先 -> createdDate 更早 ->
task_id 更小（结论确定性优先，其余保证可复现）。
"""

from __future__ import annotations

import difflib
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

TITLE_SIM_THRESHOLD = 0.60  # 内容层粗筛：title 相似度
PAIR_SIM_THRESHOLD = 0.75  # 内容层候选判定：max(title, desc)
STRONG_DESC_SIM = 0.90  # 强一致：desc
STRONG_DIFF_SIM = 0.80  # 强一致：diff 佐证（须双方均有 diff）

# description 参与相似度计算的截断长度（清洗后再切片）
_DESC_SLICE = 800

# 单据模板噪音：图片 markdown（截图无业务文字）、描述固定段落标题、
# 标题尾部产品版本号全角括号段（如 （ZSmart_DRM_Product_R9.0_Singtel-0313））。
# 同项目所有单据共享这些片段，会把字符相似度撑过候选门槛（回归
# 11832053~11796991 误报），剥离后相似度反映业务内容。
_IMG_MARKDOWN_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_SECTION_HEADING_RE = re.compile(r"###\s*(?:重现步骤|测试结果|期望结果)[：:]?")
_TITLE_VERSION_RE = re.compile(r"（ZSmart[^）]*）")


def _normalize(text: str) -> str:
    """剥离单据模板噪音，使相似度计算只看业务内容。"""
    text = _IMG_MARKDOWN_RE.sub("", text)
    text = _SECTION_HEADING_RE.sub("", text)
    return _TITLE_VERSION_RE.sub("", text)


@dataclass(frozen=True)
class TaskCandidate:
    """重复单识别所需的单据元数据（任务数据 + 结论记录 + issue no）。"""

    task_id: int
    title: str = ""
    description: str = ""
    diffs: tuple[str, ...] = ()
    related_task_nos: tuple[str, ...] = ()
    has_reviewed_conclusion: bool = False
    created_date: str = ""
    issue_no: str = ""


@dataclass(frozen=True)
class RelatedPair:
    """一组复用关系：slave 的复盘结论替换为 master 的结论。"""

    master_id: int
    slave_id: int
    title_sim: float
    desc_sim: float
    diff_sim: float
    verdict: str  # "strong" | "borderline"
    source: str  # "issue_no" | "explicit" | "content"


@dataclass(frozen=True)
class _Match:
    """候选匹配明细（不含主从方向）。"""

    other: TaskCandidate
    title_sim: float
    desc_sim: float
    diff_sim: float
    verdict: str
    source: str

    def rank(self) -> tuple[float, float, float]:
        return (self.desc_sim, self.diff_sim, self.title_sim)


def _similarity(a: str, b: str) -> float:
    """文本相似度（difflib SequenceMatcher，autojunk 关闭）。"""
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def candidate_from_task(
    task_data: dict[str, Any],
    progress_record: dict[str, Any] | None = None,
    issue_no: str = "",
) -> TaskCandidate:
    """从 cache 任务 dict（+ progress 结论记录 + issue no）构造识别候选。

    已复盘判定沿用 progress 记录真实结构：conclusion_review.reviewed_at
    存在且顶层 root_causes 非空。
    """
    commits = (task_data.get("development") or {}).get("commits") or []
    diffs = tuple(str(c.get("diff") or "") for c in commits if c.get("diff"))
    review = (progress_record or {}).get("conclusion_review") or {}
    reviewed = bool(review.get("reviewed_at")) and bool((progress_record or {}).get("root_causes"))
    return TaskCandidate(
        task_id=int(task_data.get("task_id", 0) or 0),
        title=str(task_data.get("title") or ""),
        description=str(task_data.get("description") or ""),
        diffs=diffs,
        related_task_nos=tuple(str(x) for x in (task_data.get("related_task_nos") or ())),
        has_reviewed_conclusion=reviewed,
        created_date=str(task_data.get("create_time") or ""),
        issue_no=issue_no,
    )


class DuplicateDetector:
    """重复单识别：issue no 层 + 显式关系层 + 内容相似度层。"""

    def resolve_master(self, a: TaskCandidate, b: TaskCandidate) -> int:
        """主从规则：复审结论优先 -> createdDate 更早 -> task_id 更小。"""
        if a.has_reviewed_conclusion != b.has_reviewed_conclusion:
            return a.task_id if a.has_reviewed_conclusion else b.task_id
        if a.created_date != b.created_date:
            return a.task_id if a.created_date < b.created_date else b.task_id
        return min(a.task_id, b.task_id)

    def find_related(
        self, target: TaskCandidate, candidates: Sequence[TaskCandidate]
    ) -> RelatedPair | None:
        """为 target 找可复用结论的关联单（最佳候选），无则 None。

        target 自身为主单（对方均无可复用结论）时返回 None——此时应正常
        走复盘流程，其结论将作为后续关联单的复用来源。
        """
        best: _Match | None = None
        for c in candidates:
            if c.task_id == target.task_id:
                continue
            m = self._match(target, c)
            if m is None:
                continue
            if m.source == "issue_no":
                # 第〇层确定性关联：主单须已有复审结论且不是 target 自己
                if c.has_reviewed_conclusion and self.resolve_master(target, c) == c.task_id:
                    return self._pair(target, m, c.task_id)
                continue
            if best is None or m.rank() > best.rank():
                best = m
        if best is None:
            return None
        master_id = self.resolve_master(target, best.other)
        if master_id == target.task_id:
            return None
        return self._pair(target, best, master_id)

    def find_all_pairs(self, candidates: Sequence[TaskCandidate]) -> list[RelatedPair]:
        """全量扫描：issue no 组配对（主从判定）+ 剩余单内容层两两扫描。

        issue 层覆盖的单（含主单）不再参与内容层，避免同一对重复配对。
        内容层可能返回 borderline 对，由调用方决定自动复用（strong）或
        出清单人工确认（borderline）。
        """
        pairs: list[RelatedPair] = []
        covered: set[int] = set()

        by_issue: dict[str, list[TaskCandidate]] = defaultdict(list)
        for c in candidates:
            if c.issue_no:
                by_issue[c.issue_no].append(c)
        for members in by_issue.values():
            if len(members) < 2:
                continue
            ordered = sorted(
                members,
                key=lambda x: (not x.has_reviewed_conclusion, x.created_date, x.task_id),
            )
            master = ordered[0]
            if not master.has_reviewed_conclusion:
                continue  # 组内无已复盘单，无可复用
            covered.update(m.task_id for m in members)
            deterministic = _Match(
                other=master,
                title_sim=1.0,
                desc_sim=1.0,
                diff_sim=1.0,
                verdict="strong",
                source="issue_no",
            )
            pairs.extend(self._pair(m, deterministic, master.task_id) for m in ordered[1:])

        rest = [c for c in candidates if c.task_id not in covered]
        for i, a in enumerate(rest):
            for b in rest[i + 1 :]:
                m = self._match(a, b)
                if m is None or m.source == "issue_no":
                    # issue 层配对已在前段完整处理（含组内无已复盘主单
                    # 时不生成配对的语义），此处不再二次命中
                    continue
                master_id = self.resolve_master(a, b)
                master = a if master_id == a.task_id else b
                slave = b if master_id == a.task_id else a
                pairs.append(self._pair(slave, m, master.task_id))
        return pairs

    def _match(self, a: TaskCandidate, b: TaskCandidate) -> _Match | None:
        """两单关联判定（不含主从方向）。"""
        if a.issue_no and a.issue_no == b.issue_no:
            # 第〇层：issue no 相同即确定性关联，直接复用不比对内容
            return _Match(
                other=b,
                title_sim=1.0,
                desc_sim=1.0,
                diff_sim=1.0,
                verdict="strong",
                source="issue_no",
            )
        explicit = str(b.task_id) in a.related_task_nos or str(a.task_id) in b.related_task_nos
        t_sim = _similarity(_normalize(a.title), _normalize(b.title))
        if not explicit and t_sim < TITLE_SIM_THRESHOLD:
            return None
        d_sim = _similarity(
            _normalize(a.description)[:_DESC_SLICE], _normalize(b.description)[:_DESC_SLICE]
        )
        if max(t_sim, d_sim) < PAIR_SIM_THRESHOLD:
            return None
        # diff 强佐证须双方均有 diff：单边无 diff（如样例对 B 单）不构成佐证
        f_sim = _similarity("\n".join(a.diffs), "\n".join(b.diffs)) if a.diffs and b.diffs else 0.0
        if explicit:
            verdict, source = "strong", "explicit"
        elif d_sim >= STRONG_DESC_SIM or f_sim >= STRONG_DIFF_SIM:
            verdict, source = "strong", "content"
        else:
            verdict, source = "borderline", "content"
        return _Match(
            other=b,
            title_sim=t_sim,
            desc_sim=d_sim,
            diff_sim=f_sim,
            verdict=verdict,
            source=source,
        )

    def _pair(self, target: TaskCandidate, m: _Match, master_id: int) -> RelatedPair:
        return RelatedPair(
            master_id=master_id,
            slave_id=target.task_id,
            title_sim=m.title_sim,
            desc_sim=m.desc_sim,
            diff_sim=m.diff_sim,
            verdict=m.verdict,
            source=m.source,
        )
