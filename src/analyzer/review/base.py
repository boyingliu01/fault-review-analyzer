"""Delphi 多专家匿名多轮共识复审 —— 通用基类。

sprint-20260902-77 从违规复审（DelphiViolationReviewer）泛化的纯机制层，
与领域无关：

- providers 构造：per-reviewer model/base_url/api_key 覆盖，空则继承主配置
- 多轮循环：未达共识时向各专家注入其他专家的匿名反方意见（Delphi 迭代收敛）
- 全票共识判定（consensus_rule 参数位预留，本期恒为 unanimous）
- 两级保守兜底不变量（R1/R2 评审高危条件，设计文档 §3.1）：
  * 专家级失败（round 内解析失败/非法 verdict/调用异常）
    -> opinion_failure_verdict（域决定：违规域 insufficient_evidence 不放大
       违规；结论域 diverged 不静默撤结论）
  * 候选级异常（单条候选复审整体失败）
    -> candidate_failure_verdict（两域一致 diverged，保守保留交人工）

子类只需提供：VALID_VERDICTS（verdict 词表）、system_prompt、_build_material()
（材料组装）、_item_identity()（候选标识字段）、validate_verdict()（域级
verdict 校验钩子，默认恒等；结论域覆写执行 refuted 反证门槛）。
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Protocol

from loguru import logger

from src.analyzer.llm_provider import OpenAILLMProvider

if TYPE_CHECKING:
    from src.config.models import LLMConfig, ReviewerConfig


class DelphiReviewSettings(Protocol):
    """复审配置结构协议（违规/结论域配置类共同满足的结构子类型）。"""

    max_rounds: int
    context_lines: int
    reviewers: list[ReviewerConfig]


DIVERGED = "diverged"

# 专家意见兜底 reason 前缀（全部代表"该意见非真实复核产物"）：
# reviewer_error=LLM 调用异常、unparseable_response=输出解析失败、
# invalid_verdict=非法 verdict、review_error=候选级异常。
# 消费端（pipeline/批量脚本）据此识别"全专家失败"单据做可观测标注
FAILURE_REASON_PREFIXES = (
    "reviewer_error",
    "unparseable_response",
    "invalid_verdict",
    "review_error",
)

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


class DelphiReviewerBase:
    """多专家匿名多轮共识复审基类（机制层）。"""

    VALID_VERDICTS: ClassVar[tuple[str, ...]] = ()
    opinion_failure_verdict: ClassVar[str] = "insufficient_evidence"
    candidate_failure_verdict: ClassVar[str] = DIVERGED
    system_prompt: ClassVar[str] = ""
    review_method: ClassVar[str] = "delphi_multi_expert_consensus"

    def __init__(
        self,
        llm_config: LLMConfig,
        config: DelphiReviewSettings,
        consensus_rule: str = "unanimous",
    ) -> None:
        self._config = config
        self._consensus_rule = consensus_rule  # 预留：unanimous 全票（本期唯一实现）
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
        self, fault_info: dict[str, Any], candidates: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """对全部候选执行 Delphi 复审。

        Returns:
            复审记录（含 items，与候选按 index 对齐），可直接序列化存档。
        """
        items: list[dict[str, Any]] = []
        for v in candidates:
            try:
                items.append(await self._review_candidate(fault_info, v))
            except Exception as e:  # noqa: BLE001 复审失败保守保留候选（INV-2）
                logger.warning(f"Delphi 复审异常（保守保留候选）: {type(e).__name__} {e}")
                items.append(
                    self._final_item(
                        v,
                        self.candidate_failure_verdict,
                        False,
                        0,
                        [],
                        f"review_error: {e}",
                    )
                )
        return {
            "reviewed_at": datetime.now().isoformat(timespec="seconds"),
            "method": self.review_method,
            "reviewers": list(self._providers.keys()),
            "max_rounds": self._config.max_rounds,
            "items": items,
        }

    async def _review_candidate(
        self, fault_info: dict[str, Any], candidate: dict[str, Any]
    ) -> dict[str, Any]:
        material = self._build_material(fault_info, candidate)
        previous: dict[str, ExpertOpinion] = {}
        rounds: list[dict[str, ExpertOpinion]] = []
        for round_no in range(1, self._config.max_rounds + 1):
            round_ops = await self._collect_round(material, round_no, previous)
            rounds.append(round_ops)
            verdicts = {op.verdict for op in round_ops.values()}
            previous = round_ops
            if len(verdicts) == 1:  # unanimous（consensus_rule 参数位预留）
                verdict = verdicts.pop()
                flat = [op for r in rounds for op in r.values()]
                reason = next(op.reason for op in round_ops.values() if op.verdict == verdict)
                return self._final_item(candidate, verdict, True, round_no, flat, reason)
        flat = [op for r in rounds for op in r.values()]
        verdict_strs = ", ".join(sorted({op.verdict for op in flat}))
        return self._final_item(
            candidate,
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
            # per-persona 指令键（结论域差异化评审视角）；无该键回退共享 base_prompt（违规域形态）
            user_prompt = material.get(f"base_prompt_{persona}") or material["base_prompt"]
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
            response = await provider.generate(self.system_prompt, user_prompt)
            return self._parse_opinion(persona, round_no, response, material)

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
                    verdict=self.opinion_failure_verdict,  # INV-1：域决定兜底
                    reason=f"reviewer_error: {res}",
                )
            else:
                ops[persona] = res
        return ops

    def _parse_opinion(
        self, persona: str, round_no: int, response: str, material: dict[str, str]
    ) -> ExpertOpinion:
        data = parse_verdict_json(response)
        if data is None:
            logger.warning(
                f"评审专家 {persona} 输出无法解析，按 {self.opinion_failure_verdict} 处理"
            )
            return ExpertOpinion(
                reviewer=persona,
                round_no=round_no,
                verdict=self.opinion_failure_verdict,
                reason=f"unparseable_response: {response[:120]}",
            )
        verdict = str(data.get("verdict", "")).strip()
        if verdict not in self.VALID_VERDICTS:
            logger.warning(
                f"评审专家 {persona} 输出非法 verdict: {verdict!r}，"
                f"按 {self.opinion_failure_verdict} 处理"
            )
            return ExpertOpinion(
                reviewer=persona,
                round_no=round_no,
                verdict=self.opinion_failure_verdict,
                reason=f"invalid_verdict: {response[:120]}",
            )
        key_evidence = str(data.get("key_evidence", ""))
        final_verdict = self.validate_verdict(verdict, key_evidence, material)
        return ExpertOpinion(
            reviewer=persona,
            round_no=round_no,
            verdict=final_verdict,
            reason=str(data.get("reason", "")),
            key_evidence=key_evidence,
        )

    # ---- 子类契约 ----

    # 基类恒等实现不消费参数；签名（key_evidence/material）是结论域覆写 refuted 反证门槛的契约
    def validate_verdict(self, verdict: str, key_evidence: str, material: dict[str, str]) -> str:  # noqa: ARG002
        """域级 verdict 校验钩子（解析层调用，匿名反馈与共识判定口径一致）。

        默认恒等返回；结论域覆写执行 refuted 反证门槛降级。
        """
        return verdict

    def _build_material(
        self, fault_info: dict[str, Any], candidate: dict[str, Any]
    ) -> dict[str, str]:
        raise NotImplementedError

    def _item_identity(self, candidate: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def _final_item(
        self,
        candidate: dict[str, Any],
        verdict: str,
        consensus: bool,
        rounds: int,
        opinions: list[ExpertOpinion],
        reason: str,
    ) -> dict[str, Any]:
        return {
            **self._item_identity(candidate),
            "final_verdict": verdict,
            "consensus": consensus,
            "rounds": rounds,
            "reason": reason,
            "opinions": [op.to_dict() for op in opinions],
        }
