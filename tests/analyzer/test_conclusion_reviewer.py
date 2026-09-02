"""结论域 Delphi 复审器不变量锁定（sprint-20260902-77 SLICE-2，设计文档 §3.2/§3.1）。

- INV-1 结论域：专家级失败（调用异常/解析失败/非法 verdict）→ opinion_failure_verdict
  必须为 diverged（保留交人工），严禁 insufficient_evidence 静默撤真因
- INV-3 refuted 反证门槛：key_evidence 前 60 字符须在 evidence/diff 原文子串命中，
  不得以故障标题/描述文本充当反证；不满足在解析层降级 insufficient_evidence
- REQ-2/8：双模型交叉专家（fact_evidence_auditor@g-deepseek-v4-flash +
  fix_vs_intro_discriminator@g-qwen3.8-flash），enabled 默认 false 灰度（INV-4）
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.analyzer.review.base import DIVERGED
from src.analyzer.review.conclusion_reviewer import ConclusionReviewer
from src.config.models import ConclusionReviewConfig, LLMConfig

FAULT: dict[str, str] = {
    "title": "订单导出失败",
    "description": "导出任务超时，客户侧无法获取报表",
    "code_snippet": (
        "10: public List<Order> query() {\n11:     return orderMapper.queryAll();\n12: }"
    ),
}
CANDIDATE: dict[str, Any] = {
    "cause_type": "设计缺陷",
    "description": "查询未做分页导致全量加载超时",
    "evidence": ["return orderMapper.queryAll();"],
}
EVIDENCE_LINE = "return orderMapper.queryAll();"


def _make_reviewer(
    responses: dict[str, str], config: ConclusionReviewConfig | None = None
) -> ConclusionReviewer:
    """按 persona->响应文本构造复审器（providers 直接替换为 mock）。"""
    llm_cfg = LLMConfig(api_key="k", model="m", base_url="https://gw.example")
    cfg = config or ConclusionReviewConfig(enabled=True)
    reviewer = ConclusionReviewer(llm_cfg, cfg)
    for persona in cfg.reviewers:
        provider = MagicMock()
        provider.generate = AsyncMock(return_value=responses.get(persona.persona, ""))
        reviewer._providers[persona.persona] = provider
    return reviewer


CONFIRMED = '{"verdict": "confirmed", "reason": "结论有证据支撑", "key_evidence": "return orderMapper.queryAll();"}'
REFUTED_VALID = '{"verdict": "refuted", "reason": "代码存在分页调用", "key_evidence": "return orderMapper.queryAll();"}'
REFUTED_HALLUCINATED = (
    '{"verdict": "refuted", "reason": "描述与实现不符", '
    '"key_evidence": "存在分页拦截器 PageHelper.startPage 自动注入的幻觉行"}'
)
REFUTED_ON_TITLE = '{"verdict": "refuted", "reason": "标题即证据", "key_evidence": "订单导出失败"}'
INSUFFICIENT = '{"verdict": "insufficient_evidence", "reason": "证据不足以下结论"}'


class TestConfigDefaults:
    """REQ-8/INV-4：配置默认值与灰度。"""

    def test_enabled_default_false(self):
        assert ConclusionReviewConfig().enabled is False

    def test_default_reviewers_dual_model(self):
        cfg = ConclusionReviewConfig()
        personas = [r.persona for r in cfg.reviewers]
        models = [r.model for r in cfg.reviewers]
        assert personas == ["fact_evidence_auditor", "fix_vs_intro_discriminator"]
        assert models == ["g-deepseek-v4-flash", "g-qwen3.8-flash"]

    def test_reviewer_temperature_cold(self):
        # REQ-9：复盘分析类 LLM 调用温度 < 0.2
        assert all(r.temperature < 0.2 for r in ConclusionReviewConfig().reviewers)

    def test_satisfies_base_protocol(self):
        cfg = ConclusionReviewConfig()
        assert isinstance(cfg.max_rounds, int) and cfg.max_rounds >= 1
        assert isinstance(cfg.context_lines, int) and cfg.context_lines >= 2
        assert isinstance(cfg.reviewers, list)


class TestProviderConstruction:
    """REQ-2：双模型 provider 构造与主配置继承。"""

    def test_dual_model_providers(self):
        reviewer = _make_reviewer({})
        assert len(reviewer.providers) == 2

    def test_inherit_llm_config(self):
        llm_cfg = LLMConfig(api_key="main-key", model="main-model", base_url="https://gw")
        reviewer = ConclusionReviewer(llm_cfg, ConclusionReviewConfig(enabled=True))
        for provider in reviewer.providers:
            assert provider.api_key == "main-key"
            assert provider.base_url == "https://gw"


class TestExpertFailureInvariant:
    """INV-1 结论域：专家级失败兜底 diverged（不撤真因）。"""

    @pytest.mark.asyncio
    async def test_expert_exception_diverged(self):
        broken = MagicMock()
        broken.generate = AsyncMock(side_effect=RuntimeError("network down"))
        reviewer = _make_reviewer({})
        reviewer._providers = dict.fromkeys(reviewer._providers, broken)
        record = await reviewer.review(FAULT, [dict(CANDIDATE)])
        item = record["items"][0]
        assert item["final_verdict"] == DIVERGED
        assert item["consensus"] is True  # 全部兜底为同一 verdict → 形式共识
        assert "reviewer_error" in item["opinions"][0]["reason"]

    @pytest.mark.asyncio
    async def test_unparseable_output_diverged(self):
        reviewer = _make_reviewer({"fact_evidence_auditor": "抱歉无法回答"})
        record = await reviewer.review(FAULT, [dict(CANDIDATE)])
        item = record["items"][0]
        assert item["final_verdict"] == DIVERGED


class TestRefutedGate:
    """INV-3：refuted 反证门槛（引擎侧校验，解析层降级）。"""

    @pytest.mark.asyncio
    async def test_refuted_with_valid_key_evidence_kept(self):
        reviewer = _make_reviewer(
            {
                "fact_evidence_auditor": REFUTED_VALID,
                "fix_vs_intro_discriminator": REFUTED_VALID,
            }
        )
        record = await reviewer.review(FAULT, [dict(CANDIDATE)])
        item = record["items"][0]
        assert item["final_verdict"] == "refuted" and item["consensus"] is True

    @pytest.mark.asyncio
    async def test_refuted_hallucinated_evidence_downgraded(self):
        # key_evidence 在 evidence/diff 原文中不存在 → 降级 insufficient_evidence
        reviewer = _make_reviewer(
            {
                "fact_evidence_auditor": REFUTED_HALLUCINATED,
                "fix_vs_intro_discriminator": REFUTED_HALLUCINATED,
            }
        )
        record = await reviewer.review(FAULT, [dict(CANDIDATE)])
        item = record["items"][0]
        assert item["final_verdict"] == "insufficient_evidence"

    @pytest.mark.asyncio
    async def test_refuted_anchored_on_title_only_downgraded(self):
        # 反证只命中故障标题（脑补高危源），不在 evidence/diff 原文 → 降级
        reviewer = _make_reviewer(
            {
                "fact_evidence_auditor": REFUTED_ON_TITLE,
                "fix_vs_intro_discriminator": REFUTED_ON_TITLE,
            }
        )
        record = await reviewer.review(FAULT, [dict(CANDIDATE)])
        item = record["items"][0]
        assert item["final_verdict"] == "insufficient_evidence"

    @pytest.mark.asyncio
    async def test_confirmed_unaffected_by_gate(self):
        reviewer = _make_reviewer(
            {
                "fact_evidence_auditor": CONFIRMED,
                "fix_vs_intro_discriminator": CONFIRMED,
            }
        )
        record = await reviewer.review(FAULT, [dict(CANDIDATE)])
        item = record["items"][0]
        assert item["final_verdict"] == "confirmed"


class TestMaterial:
    """§3.2：材料组装（结论+证据窗口+背景）与 per-persona 指令。"""

    def test_material_contains_conclusion_and_evidence(self):
        reviewer = _make_reviewer({})
        material = reviewer._build_material(FAULT, dict(CANDIDATE))
        base_prompt = material["base_prompt"]
        assert CANDIDATE["cause_type"] in base_prompt
        assert CANDIDATE["description"] in base_prompt
        assert EVIDENCE_LINE in base_prompt
        assert FAULT["title"] in base_prompt

    def test_per_persona_prompts_differ(self):
        reviewer = _make_reviewer({})
        material = reviewer._build_material(FAULT, dict(CANDIDATE))
        key_a = "base_prompt_fact_evidence_auditor"
        key_b = "base_prompt_fix_vs_intro_discriminator"
        assert key_a in material and key_b in material
        assert material[key_a] != material[key_b]
        # 共享材料在两个 persona prompt 中均在场
        assert EVIDENCE_LINE in material[key_a]
        assert EVIDENCE_LINE in material[key_b]

    def test_evidence_raw_excludes_title_and_description(self):
        # INV-3 反证锚定面：只含 evidence/diff 原文，不含标题/描述
        reviewer = _make_reviewer({})
        material = reviewer._build_material(FAULT, dict(CANDIDATE))
        raw = material["evidence_raw"]
        assert EVIDENCE_LINE in raw
        assert FAULT["title"] not in raw
        assert FAULT["description"] not in raw


class TestConsensus:
    """共识收敛与轮尽分歧（机制层在基类，结论域联通验证）。"""

    @pytest.mark.asyncio
    async def test_unanimous_confirmed(self):
        reviewer = _make_reviewer(
            {"fact_evidence_auditor": CONFIRMED, "fix_vs_intro_discriminator": CONFIRMED}
        )
        record = await reviewer.review(FAULT, [dict(CANDIDATE)])
        item = record["items"][0]
        assert item["final_verdict"] == "confirmed"
        assert item["consensus"] is True
        assert item["rounds"] == 1

    @pytest.mark.asyncio
    async def test_diverged_on_disagreement(self):
        reviewer = _make_reviewer(
            {"fact_evidence_auditor": CONFIRMED, "fix_vs_intro_discriminator": INSUFFICIENT}
        )
        record = await reviewer.review(FAULT, [dict(CANDIDATE)])
        item = record["items"][0]
        assert item["final_verdict"] == DIVERGED
        assert item["consensus"] is False


class TestBasePersonaFallback:
    """基类 per-persona 回退键：违规域（仅 base_prompt）行为不变。"""

    @pytest.mark.asyncio
    async def test_base_prompt_used_when_no_persona_key(self):
        from src.analyzer.review.base import DelphiReviewerBase

        seen_prompts: list[str] = []

        class _Probe(DelphiReviewerBase):
            VALID_VERDICTS = ("a", "b")

            def _build_material(
                self, fault_info: dict[str, Any], candidate: dict[str, Any]
            ) -> dict[str, str]:
                return {"base_prompt": "共享材料"}  # 无 per-persona 键（违规域形态）

            def _item_identity(self, candidate: dict[str, Any]) -> dict[str, Any]:
                return {}

        llm_cfg = LLMConfig(api_key="k", model="m")
        cfg = ConclusionReviewConfig(enabled=True)
        reviewer = _Probe(llm_cfg, cfg)
        for persona in list(reviewer._providers):
            provider = MagicMock()

            async def _capture(_system: str, user: str) -> str:
                seen_prompts.append(user)
                return '{"verdict": "a"}'

            provider.generate = AsyncMock(side_effect=_capture)
            reviewer._providers[persona] = provider
        await reviewer.review({}, [{}])
        assert seen_prompts and all(p == "共享材料" for p in seen_prompts)
