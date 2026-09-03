"""结论域 Delphi 复审器（sprint-20260902-77 SLICE-2）。

对复盘根因结论做多专家匿名多轮共识复核（机制在基类 DelphiReviewerBase），
双模型交叉专家各自独立评审视角：

- fact_evidence_auditor（事实核对）：结论中每个事实断言必须能在证据/diff
  原文中找到逐字或直接可推导的依据；断言无依据时判 refuted；依据不足
  以下结论时判 insufficient_evidence
- fix_vs_intro_discriminator（修复/引入判定）：判定结论所指问题是否为
  本次变更引入——变更可能是修复动作（按客户要求调整校验、线程隔离改造）
  或配置/模板占位符按设计展示；修复性变更被定性为缺陷时判 refuted

事实纪律（复盘结论准确性第一）：prompt 采用正向核对指令 + 上游事实注入；
refuted 反证门槛由引擎侧校验（validate_verdict）：key_evidence 前 60 字符
必须在 evidence/diff/截图原文窗口中子串命中，反证只能锚定原文，故障标题/
描述文本不得充当反证（描述本身即脑补高危源）；不满足门槛在解析层降级为
insufficient_evidence——final_verdict 永不出现不满足门槛的 refuted，匿名
反方意见反馈与共识判定口径一致。

裁决纪律（用户裁定口径）：引入单号非必填，修复前代码、变更说明等引入单
信息只是辅助证据，其缺失属于常态而非证据不足；找不到引入单信息时按故障
单自身信息（描述/截图/修复 diff）复盘，不得以辅助信息缺失为由撤销结论。

裁决语义：
- confirmed 共识          -> 结论保留
- refuted 共识            -> 结论撤销（记入审计，附反证行）
- insufficient_evidence 共识 -> 结论撤销（宁缺毋滥）
- 专家级失败 / 轮尽分歧   -> diverged：结论保留并标记待人工（不静默撤真因）
"""

from __future__ import annotations

from typing import Any

from src.analyzer.review.base import (
    DIVERGED,
    DelphiReviewerBase,
    build_context_window,
    normalize_evidence,
)

__all__ = ["ConclusionReviewer", "apply_conclusion_review"]


def apply_conclusion_review(
    conclusions: list[dict[str, Any]], review_record: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """把结论域 Delphi 裁决应用到结论列表。

    返回 (保留列表, 撤销列表)。confirmed/diverged 保留（diverged 附
    conclusion_verdict 待人工标记）；refuted/insufficient_evidence 撤销
    （撤销项附裁决信息供审计与结论重建时针对性注入）。items 与结论按
    index 对齐；缺 item 时兜底 diverged（保守保留）。
    """
    items = review_record.get("items", [])
    kept: list[dict[str, Any]] = []
    revoked: list[dict[str, Any]] = []
    for i, rc in enumerate(conclusions):
        item = items[i] if i < len(items) else None
        verdict = (item or {}).get("final_verdict", DIVERGED)
        tagged = {
            **rc,
            "conclusion_verdict": verdict,
            "conclusion_reason": (item or {}).get("reason", ""),
        }
        if verdict in ("refuted", "insufficient_evidence"):
            revoked.append(tagged)
        else:
            kept.append(tagged)
    return kept, revoked


CONCLUSION_SYSTEM_PROMPT = (
    "你是故障复盘结论评审专家，只做一件事：基于证据原文核对给定的复盘根因结论"
    "是否站得住脚。\n"
    "纪律：\n"
    "1. 只基于提供的证据与代码 diff 原文判断，每个事实断言都要在原文中找到"
    "逐字或直接可推导的依据\n"
    "2. 证据基准：引入单号非必填，修复前代码、变更说明等引入单信息只是辅助"
    "证据，其缺失属于常态而非证据不足；应基于故障单自身信息（故障描述、"
    "图片/截图证据、修复 diff 原文）裁决，不得仅以「未提供修复前代码」"
    "「无代码 diff」「截图未提供」为由判 insufficient_evidence\n"
    "3. 依据不足以下结论时，输出 insufficient_evidence\n"
    "4. 撤销基准：结论能被材料内信息合理支撑时判 confirmed；"
    "insufficient_evidence 仅用于结论的关键断言在材料内找不到依据（推断/脑补）"
    "的情形；refuted 仅用于结论与材料内容矛盾，key_evidence 须锚定原文\n"
    "5. 输出严格为 JSON，不要输出任何其他文本"
)

_FACT_AUDIT_INSTRUCTIONS = """请以事实核对视角独立评审以下复盘根因结论。

## 评审要求（事实核对）
1. 结论中每个事实断言逐条对照证据与代码 diff 原文：能找到逐字或直接可推导
   依据的判定成立
2. 断言在原文中无依据时，verdict 取 refuted，并在 key_evidence 中给出原文中
   的具体反证行
3. 依据不足以下结论时，verdict 取 insufficient_evidence
4. 证据基准：引入单号非必填，修复前代码等引入单信息只是辅助证据，缺失属于
   常态而非证据不足；不得仅以「未提供修复前代码」「无代码 diff」为由判
   insufficient_evidence；结论能被材料内信息合理支撑时判 confirmed
"""

_FIX_VS_INTRO_INSTRUCTIONS = """请以变更性质视角独立评审以下复盘根因结论。

## 评审要求（修复/引入判定）
1. 判定结论所指问题是否为本次变更引入：本次 diff 中的变更可能是修复动作
   （按客户要求调整校验、线程隔离改造等）或配置/模板占位符按设计展示
2. 修复性变更或按设计展示的内容被结论定性为缺陷时，verdict 取 refuted，
   并在 key_evidence 中给出 diff 原文中的具体反证行
3. 无法判定变更性质时，verdict 取 insufficient_evidence
4. 证据基准：引入单号非必填，引入单信息只是辅助证据，缺失属于常态；
   不得仅以「未提供修复前代码」「无代码 diff」「截图未提供」为由判
   insufficient_evidence；结论能被材料内信息合理支撑时判 confirmed
"""

_CONCLUSION_MATERIAL_TEMPLATE = """

## 待评审的根因结论
类型: {cause_type}
结论: {description}
结论引用的证据:
{evidence}

## 证据在代码 diff 中的上下文窗口（行首数字为片段内行号）
```
{context}
```
{image_section}
## 故障背景（仅供参考，证据原文优先）
标题: {title}
描述: {fault_description}

## 输出格式
1. verdict 取值：confirmed（结论成立）/ refuted（结论与事实不符）/ insufficient_evidence（证据不足）
2. reason 引用具体证据行为说明认定理由，不超过 150 字
3. 返回 JSON：
{{"verdict": "...", "reason": "...", "key_evidence": "支持判定的一行证据或 diff 原文"}}"""

# 截图证据段：仅 image_evidence 非空时渲染（缺失属常态，渲染空段会诱导
# 「截图未提供」类裁决，违背裁决纪律）
_IMAGE_SECTION_TEMPLATE = """
## 图片/截图证据（故障单截图 OCR，辅助信息）
{image_evidence}
"""


class ConclusionReviewer(DelphiReviewerBase):
    """多专家匿名多轮共识结论复审器（机制在基类，此处仅结论域实现）。"""

    VALID_VERDICTS = ("confirmed", "refuted", "insufficient_evidence")
    opinion_failure_verdict = DIVERGED  # INV-1：专家失败不撤真因，保留待人工
    candidate_failure_verdict = DIVERGED  # INV-2：候选级异常保守保留
    system_prompt = CONCLUSION_SYSTEM_PROMPT

    def _build_material(
        self, fault_info: dict[str, Any], candidate: dict[str, Any]
    ) -> dict[str, str]:
        evidence_lines = normalize_evidence(candidate.get("evidence"))
        diff_text = fault_info.get("code_snippet", "") or ""
        context = build_context_window(diff_text, evidence_lines, self._config.context_lines)
        image_evidence = (fault_info.get("image_evidence", "") or "").strip()
        # 反证门槛锚定面：结论引用证据 + diff 原文窗口 + 截图 OCR 原文
        # （图片证据客观存在，属故障单自身信息）；标题/描述仍不在锚定面
        evidence_raw = "\n".join(
            part for part in (*evidence_lines, context, image_evidence) if part
        )
        # 截图缺失属常态：不渲染空段，避免诱导「截图未提供」类裁决
        image_section = (
            _IMAGE_SECTION_TEMPLATE.format(image_evidence=image_evidence[:1500])
            if image_evidence
            else ""
        )
        material_common = _CONCLUSION_MATERIAL_TEMPLATE.format(
            cause_type=candidate.get("cause_type", ""),
            description=candidate.get("description") or "",
            evidence="\n".join(f"- {ln}" for ln in evidence_lines) or "-（无）",
            context=context,
            image_section=image_section,
            title=fault_info.get("title", ""),
            fault_description=(fault_info.get("description", "") or "")[:200],
        )
        return {
            "evidence_raw": evidence_raw,
            "base_prompt": material_common,
            "base_prompt_fact_evidence_auditor": (_FACT_AUDIT_INSTRUCTIONS + material_common),
            "base_prompt_fix_vs_intro_discriminator": (
                _FIX_VS_INTRO_INSTRUCTIONS + material_common
            ),
        }

    def validate_verdict(self, verdict: str, key_evidence: str, material: dict[str, str]) -> str:
        """refuted 反证门槛（INV-3）：key_evidence 前 60 字符须在证据/diff 原文命中。

        反证只能锚定 evidence_raw（证据行 + diff 窗口 + 截图 OCR 原文）；
        标题/描述不在锚定面，以其充当反证视为幻觉反证，降级
        insufficient_evidence（宁缺毋滥）。
        """
        if verdict != "refuted":
            return verdict
        needle = key_evidence.strip()[:60]
        # casefold 比较：专家引用反证时的大小写变体不应触发门槛误降级
        if needle and needle.casefold() in material.get("evidence_raw", "").casefold():
            return verdict
        return "insufficient_evidence"

    def _item_identity(self, candidate: dict[str, Any]) -> dict[str, Any]:
        return {
            "cause_type": candidate.get("cause_type", ""),
            "description": candidate.get("description") or "",
        }
