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
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from loguru import logger

from src.analyzer.llm_provider import OpenAILLMProvider

if TYPE_CHECKING:
    from src.config.models import DelphiReviewConfig, LLMConfig

VALID_VERDICTS = ("violation", "false_positive", "insufficient_evidence")
DIVERGED = "diverged"

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

ROUND_FEEDBACK_TEMPLATE = """

## 第 {round_no} 轮评审说明
上一轮各评审专家意见存在分歧。以下是其他专家的匿名反方意见（不代表正确答案，
仅供参考后独立重判）：
{other_opinions}

请基于代码证据独立重新评审，可以坚持或修正你的判断。仍按第 1 轮要求返回 JSON。"""


@dataclass
class ExpertOpinion:
    """单个专家的单轮评审意见。"""

    reviewer: str
    round_no: int
    verdict: str
    reason: str = ""
    key_evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "reviewer": self.reviewer,
            "round": self.round_no,
            "verdict": self.verdict,
            "reason": self.reason,
            "key_evidence": self.key_evidence,
        }


def normalize_evidence(evidence: Any) -> list[str]:
    """evidence 归一化为行列表（兼容 list/str/None）。"""
    if evidence is None:
        return []
    if isinstance(evidence, list):
        return [str(x) for x in evidence if str(x).strip()]
    text = str(evidence).strip()
    return [line for line in text.splitlines() if line.strip()] if text else []


def build_context_window(
    code_snippet: str, evidence_lines: list[str], context_lines: int, fallback_lines: int = 60
) -> str:
    """在代码片段中定位 evidence 命中行，取前后 context_lines 行作为评审上下文。

    多条命中行分别开窗（去重合并）；全部未命中时兜底取片段前 fallback_lines 行。
    """
    lines = code_snippet.splitlines()
    targets: list[int] = []
    for ev in evidence_lines:
        needle = ev.strip()[:60]
        if not needle:
            continue
        for i, ln in enumerate(lines):
            if needle in ln and i not in targets:
                targets.append(i)
                break
    if not targets:
        return "\n".join(f"{i + 1:>4}: {ln}" for i, ln in enumerate(lines[:fallback_lines]))
    windows: list[str] = []
    for idx in sorted(targets):
        lo = max(0, idx - context_lines)
        hi = min(len(lines), idx + context_lines + 1)
        window = "\n".join(f"{j + 1:>4}: {lines[j]}" for j in range(lo, hi))
        windows.append(window)
    return "\n    ...（多条命中行分别开窗）...\n".join(windows)


def parse_verdict_json(response: str) -> dict[str, Any] | None:
    """解析专家评审响应（支持 markdown code block 与花括号提取）。"""
    if not response:
        return None
    text = response.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"```\s*$", "", text).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    # 兜底：提取首个平衡 JSON 对象
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            return None
    return None


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


class DelphiViolationReviewer:
    """多专家匿名多轮共识违规复审器。"""

    def __init__(self, llm_config: LLMConfig, config: DelphiReviewConfig) -> None:
        self._config = config
        self._providers: dict[str, OpenAILLMProvider] = {}
        for rc in config.reviewers:
            self._providers[rc.persona] = OpenAILLMProvider(
                api_key=rc.api_key or llm_config.api_key,
                model=rc.model or llm_config.model,
                base_url=rc.base_url or llm_config.base_url,
                temperature=rc.temperature,
                max_tokens=llm_config.max_tokens,
            )

    @property
    def providers(self) -> list[OpenAILLMProvider]:
        """评审用 LLM provider（调用方统一管理生命周期）。"""
        return list(self._providers.values())

    async def review(
        self, fault_info: dict[str, Any], violations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """对全部初筛候选执行 Delphi 复审。

        Returns:
            复审记录（含 items，与候选按 index 对齐），可直接序列化存档。
        """
        items: list[dict[str, Any]] = []
        for v in violations:
            try:
                items.append(await self._review_candidate(fault_info, v))
            except Exception as e:  # noqa: BLE001 复审失败保守保留候选
                logger.warning(f"Delphi 复审异常（保守保留候选）: {type(e).__name__} {e}")
                items.append(self._final_item(v, DIVERGED, False, 0, [], f"review_error: {e}"))
        return {
            "reviewed_at": datetime.now().isoformat(timespec="seconds"),
            "method": "delphi_multi_expert_consensus",
            "reviewers": list(self._providers.keys()),
            "max_rounds": self._config.max_rounds,
            "items": items,
        }

    async def _review_candidate(
        self, fault_info: dict[str, Any], violation: dict[str, Any]
    ) -> dict[str, Any]:
        material = self._build_material(fault_info, violation)
        previous: dict[str, ExpertOpinion] = {}
        rounds: list[dict[str, ExpertOpinion]] = []
        for round_no in range(1, self._config.max_rounds + 1):
            round_ops = await self._collect_round(material, round_no, previous)
            rounds.append(round_ops)
            verdicts = {op.verdict for op in round_ops.values()}
            previous = round_ops
            if len(verdicts) == 1:
                verdict = verdicts.pop()
                flat = [op for r in rounds for op in r.values()]
                reason = next(op.reason for op in round_ops.values() if op.verdict == verdict)
                return self._final_item(violation, verdict, True, round_no, flat, reason)
        flat = [op for r in rounds for op in r.values()]
        verdict_strs = ", ".join(sorted({op.verdict for op in flat}))
        return self._final_item(
            violation,
            DIVERGED,
            False,
            len(rounds),
            flat,
            f"专家分歧（{verdict_strs}），需人工裁决",
        )

    async def _collect_round(
        self,
        material: dict[str, str],
        round_no: int,
        previous: dict[str, ExpertOpinion],
    ) -> dict[str, ExpertOpinion]:
        async def ask(persona: str, provider: OpenAILLMProvider) -> ExpertOpinion:
            user_prompt = material["base_prompt"]
            if round_no > 1 and previous:
                others = [op for p, op in previous.items() if p != persona]
                if others:
                    feedback = "\n".join(
                        f"- 专家{chr(65 + i)}（匿名）: {op.verdict} — {op.reason[:150]}"
                        for i, op in enumerate(others)
                    )
                    user_prompt += ROUND_FEEDBACK_TEMPLATE.format(
                        round_no=round_no, other_opinions=feedback
                    )
            response = await provider.generate(SYSTEM_PROMPT, user_prompt)
            return self._parse_opinion(persona, round_no, response)

        pairs = list(self._providers.items())
        results = await asyncio.gather(
            *[ask(persona, provider) for persona, provider in pairs],
            return_exceptions=True,
        )
        ops: dict[str, ExpertOpinion] = {}
        for (persona, _), res in zip(pairs, results, strict=True):
            if isinstance(res, BaseException):
                logger.warning(f"评审专家 {persona} 调用失败: {res}")
                ops[persona] = ExpertOpinion(
                    reviewer=persona,
                    round_no=round_no,
                    verdict="insufficient_evidence",
                    reason=f"reviewer_error: {res}",
                )
            else:
                ops[persona] = res
        return ops

    def _parse_opinion(self, persona: str, round_no: int, response: str) -> ExpertOpinion:
        data = parse_verdict_json(response)
        if data is None:
            # 无法解析 -> 证据不足（保守，不放大违规）
            logger.warning(f"评审专家 {persona} 输出无法解析，按证据不足处理")
            return ExpertOpinion(
                reviewer=persona,
                round_no=round_no,
                verdict="insufficient_evidence",
                reason=f"unparseable_response: {response[:120]}",
            )
        verdict = str(data.get("verdict", "")).strip()
        if verdict not in VALID_VERDICTS:
            # 非法 verdict -> 证据不足（保守，不放大违规）
            logger.warning(f"评审专家 {persona} 输出非法 verdict: {verdict!r}，按证据不足处理")
            return ExpertOpinion(
                reviewer=persona,
                round_no=round_no,
                verdict="insufficient_evidence",
                reason=f"invalid_verdict: {response[:120]}",
            )
        return ExpertOpinion(
            reviewer=persona,
            round_no=round_no,
            verdict=verdict,
            reason=str(data.get("reason", "")),
            key_evidence=str(data.get("key_evidence", "")),
        )

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

    def _final_item(
        self,
        violation: dict[str, Any],
        verdict: str,
        consensus: bool,
        rounds: int,
        opinions: list[ExpertOpinion],
        reason: str,
    ) -> dict[str, Any]:
        return {
            "rule_id": violation.get("rule_id", ""),
            "message": violation.get("message", ""),
            "final_verdict": verdict,
            "consensus": consensus,
            "rounds": rounds,
            "reason": reason,
            "opinions": [op.to_dict() for op in opinions],
        }
