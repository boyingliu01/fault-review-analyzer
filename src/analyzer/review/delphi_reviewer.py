"""Delphi 式违规复审 —— 多专家匿名多轮共识评审。

初筛（RulesEngine / ViolationDetector 正则）召回高但精确率有限
（2026-09 复核：6/6 命中全部误报——局部集合误判跨线程共享、
InheritableThreadLocal 修复代码被误判违规、多行 SQL 字面量拼接
被误判注入、JS 代码被误套 Java 条款）。语义级判定交给独立评审
专家复核，机制对齐代码走查的 Delphi 评审：

- N 个评审专家（独立 LLM 会话 + 差异化评审视角 persona），互不可
  见、对彼此匿名
- 第 1 轮独立评审；未达共识时进入下一轮，各专家收到"其他专家的
  匿名反方意见"重新独立评审（Delphi 迭代收敛机制）
- 共识 = 全票一致（2 专家场景下 >=90% 统计共识等价于全票一致）
- 最终裁决：
  - violation 共识      -> 保留候选，附专家确认依据
  - false_positive 共识 -> 撤销候选（记入审计，原因可追溯）
  - insufficient_evidence 共识 -> 撤销并标注"证据不足"（宁缺毋滥）
  - 轮次用尽仍分歧      -> diverged：保留候选并标记专家分歧，交人
    工裁决（不静默丢弃真违规，也不把不确定当确定）

事实纪律（复盘结论准确性第一）：评审只基于代码证据；证据不足必须
输出 insufficient_evidence，禁止依据故障描述脑补代码行为。

机制层已泛化至 src.analyzer.review.base（sprint-20260902-77 SLICE-1）：
providers 构造/多轮循环/共识判定/两级保守兜底均由基类提供，本模块仅保留
违规域实现（verdict 词表、persona、prompt、材料组装、撤销应用）。
"""

from __future__ import annotations

from typing import Any

from src.analyzer.review.base import (
    DIVERGED,
    DelphiReviewerBase,
    build_context_window,
    normalize_evidence,
    parse_verdict_json,
)

__all__ = [
    "DIVERGED",
    "DelphiViolationReviewer",
    "apply_review",
    "build_context_window",
    "normalize_evidence",
    "parse_verdict_json",
]

VALID_VERDICTS = ("violation", "false_positive", "insufficient_evidence")

PERSONA_DESCRIPTIONS: dict[str, str] = {
    "strict_rule_checker": (
        "严格规范审查员。逐字对照规范条款的构成要件，"
        "只有条款要件在代码证据中全部成立时才判 violation；"
        "要件不完整一律判 false_positive 并说明缺失的要件"
    ),
    "runtime_behavior_analyst": (
        "运行时行为分析专家。分析代码在真实运行环境中的行为"
        "（线程模型、数据流来源、异常路径、跨文件上下文），"
        "判断初筛模式对应的风险是否实际成立"
    ),
}

SYSTEM_PROMPT = (
    '你是代码规范评审专家，只做一件事：判定给定的"疑似规范违规"是否真实成立。\n'
    "纪律：\n"
    "1. 只基于提供的代码证据判断，禁止推测代码之外的行为，禁止脑补\n"
    "2. 代码证据不足以确认违规时，必须输出 insufficient_evidence（宁缺毋滥）\n"
    "3. 输出严格为 JSON，不要输出任何其他文本"
)

USER_PROMPT_TEMPLATE = """请独立评审以下"疑似规范违规"是否真实成立。

## 规范条款
{rule_id}: {message}

## 代码证据（命中行及其上下文，行首数字为片段内行号）
```
{context}
```

## 初筛说明
该候选由正则模式初筛产生（正则只做字面匹配，无法理解语义），历史复核发现
的典型误报形态包括：方法内局部集合被误判为跨线程共享；InheritableThreadLocal
等线程隔离的正确实现被误判为违规；多行 SQL 字符串字面量拼接被误判为拼接用
户输入；脚本语言（JS/Kotlin）代码被误套 Java 条款。请独立判断，不要默认初
筛正确。

## 故障背景（仅供参考，代码证据优先）
标题: {title}
描述: {description}

## 评审要求
1. verdict 取值：violation（违规成立）/ false_positive（误报）/ insufficient_evidence（证据不足）
2. reason 引用具体代码行为说明认定理由，不超过 150 字
3. 返回 JSON：
{{"verdict": "...", "reason": "...", "key_evidence": "最关键的一行代码或事实"}}"""


def apply_review(
    violations: list[dict[str, Any]], review_record: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """把 Delphi 裁决应用到候选列表。

    返回 (保留列表, 撤销列表)。violation/diverged 保留（diverged 标注分歧待
    人工裁决）；false_positive / insufficient_evidence 撤销（撤销项附带裁决
    信息，供审计记录）。items 与候选按 index 对齐。
    """
    items = review_record.get("items", [])
    kept: list[dict[str, Any]] = []
    revoked: list[dict[str, Any]] = []
    for i, v in enumerate(violations):
        item = items[i] if i < len(items) else None
        verdict = (item or {}).get("final_verdict", DIVERGED)
        if verdict in ("false_positive", "insufficient_evidence"):
            revoked.append(
                {**v, "delphi_verdict": verdict, "delphi_reason": (item or {}).get("reason", "")}
            )
        else:
            kept.append(
                {**v, "delphi_verdict": verdict, "delphi_reason": (item or {}).get("reason", "")}
            )
    return kept, revoked


class DelphiViolationReviewer(DelphiReviewerBase):
    """多专家匿名多轮共识违规复审器（机制在基类，此处仅域实现）。"""

    VALID_VERDICTS = VALID_VERDICTS
    opinion_failure_verdict = "insufficient_evidence"  # INV-1：失败不放大违规
    candidate_failure_verdict = DIVERGED  # INV-2：候选级异常保守保留
    system_prompt = SYSTEM_PROMPT

    def _build_material(
        self, fault_info: dict[str, Any], violation: dict[str, Any]
    ) -> dict[str, str]:
        context = build_context_window(
            fault_info.get("code_snippet", ""),
            normalize_evidence(violation.get("evidence")),
            self._config.context_lines,
        )
        base_prompt = USER_PROMPT_TEMPLATE.format(
            rule_id=violation.get("rule_id", ""),
            message=violation.get("message", ""),
            context=context,
            title=fault_info.get("title", ""),
            description=(fault_info.get("description", "") or "")[:200],
        )
        return {"base_prompt": base_prompt}

    def _item_identity(self, violation: dict[str, Any]) -> dict[str, Any]:
        return {"rule_id": violation.get("rule_id", ""), "message": violation.get("message", "")}
