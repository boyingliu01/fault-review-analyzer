"""规范匹配器 - 将故障分析结论与研发规范库做语义匹配。

匹配流程（embedding召回 + LLM精排）：
1. 召回：对故障分析结论文本与全部规范条款计算 embedding 余弦相似度，取 Top-K 候选
2. 精排：LLM 逐条判定候选条款与故障结论的关系（违反/相关/无关），给出证据与置信度
3. 降级：无 LLM 时按相似度阈值标记；无 embedding 时用关键词重叠打分

典型用途：
- 单故障复盘时识别"该故障违反了哪些规范条款"
- 批量故障分析时聚合"高频违规条款"与"无规范覆盖的新模式"
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from loguru import logger

if TYPE_CHECKING:
    from src.embedding.generator import EmbeddingGenerator
    from src.knowledge.manager import StandardsManager

# 关系类型
RELATION_VIOLATED = "violated"  # 故障结论表明该规范被违反
RELATION_RELATED = "related"  # 与故障相关但非直接违反（如改进方向）
RELATION_UNRELATED = "unrelated"  # 无关

# 默认参数
DEFAULT_TOP_K = 8
SIMILARITY_THRESHOLD = 0.55  # 降级模式下判定"相关"的相似度下限
MAX_RULES_FOR_LLM = 8  # 送LLM精排的候选上限


@dataclass
class StandardMatch:
    """单条规范匹配结果"""

    rule_id: str
    rule_title: str
    category: str = ""
    subcategory: str = ""
    level: str = ""
    relation: str = RELATION_RELATED  # violated / related
    confidence: float = 0.0
    similarity: float = 0.0
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StandardsMatchResult:
    """规范匹配整体结果"""

    matches: list[StandardMatch] = field(default_factory=list)
    match_mode: str = "llm_rerank"  # llm_rerank / similarity_only / keyword_only
    query_text: str = ""

    @property
    def violated(self) -> list[StandardMatch]:
        return [m for m in self.matches if m.relation == RELATION_VIOLATED]

    @property
    def related(self) -> list[StandardMatch]:
        return [m for m in self.matches if m.relation == RELATION_RELATED]

    def to_dict(self) -> dict[str, Any]:
        return {
            "matches": [m.to_dict() for m in self.matches],
            "match_mode": self.match_mode,
            "violated_count": len(self.violated),
            "related_count": len(self.related),
        }


class StandardsMatcher:
    """规范匹配器 - embedding召回 + LLM精排"""

    def __init__(
        self,
        standards_manager: StandardsManager,
        embedding_generator: EmbeddingGenerator | None = None,
        llm_provider: Any | None = None,
        cache_dir: Path | str | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> None:
        self._standards_manager = standards_manager
        self._embedding_generator = embedding_generator
        self._llm_provider = llm_provider
        self._top_k = top_k

        # 规范embedding缓存目录（避免每次启动重算全部条款向量）
        if cache_dir is None:
            cache_dir = (
                Path(__file__).parent.parent.parent / "data" / "cache"
            )
        self._cache_dir = Path(cache_dir)
        self._emb_cache_file = self._cache_dir / "standards_embeddings.json"

        # 运行时缓存: rule_id -> (text_hash, embedding)
        self._rule_embeddings: dict[str, tuple[str, list[float]]] | None = None

    async def match(self, query_text: str) -> StandardsMatchResult:
        """将故障分析结论文本与规范库匹配。

        Args:
            query_text: 故障分析结论文本（标签+根因+代码变更分析等）

        Returns:
            StandardsMatchResult: 匹配结果（仅含 violated/related，已过滤无关项）
        """
        if not query_text or not query_text.strip():
            return StandardsMatchResult(match_mode="empty", query_text="")

        candidates = await self._retrieve_candidates(query_text)
        if not candidates:
            return StandardsMatchResult(match_mode="no_candidates", query_text=query_text)

        if self._llm_provider is not None:
            reranked = await self._llm_rerank(query_text, candidates)
            if reranked is not None:
                return StandardsMatchResult(
                    matches=reranked, match_mode="llm_rerank", query_text=query_text
                )
            logger.warning("LLM精排失败，降级为相似度判定")

        # 降级：按相似度阈值判定
        matches = [
            m for m in candidates if m.similarity >= SIMILARITY_THRESHOLD
        ]
        mode = "similarity_only" if self._embedding_generator else "keyword_only"
        return StandardsMatchResult(matches=matches, match_mode=mode, query_text=query_text)

    # ------------------------------------------------------------------
    # 召回
    # ------------------------------------------------------------------

    async def _retrieve_candidates(self, query_text: str) -> list[StandardMatch]:
        """embedding召回Top-K候选规范；无embedding时用关键词降级。"""
        rules = [
            rule
            for category in self._standards_manager.get_all_categories()
            for rule in category.rules
        ]
        if not rules:
            return []

        if self._embedding_generator is not None:
            try:
                return await self._retrieve_by_embedding(query_text, rules)
            except Exception as e:
                logger.warning(f"embedding召回失败，降级为关键词匹配: {e}")

        return self._retrieve_by_keywords(query_text, rules)

    async def _retrieve_by_embedding(
        self, query_text: str, rules: list[Any]
    ) -> list[StandardMatch]:
        """向量召回：query与全部规范条款计算余弦相似度，取Top-K。"""
        rule_texts = [self._rule_to_document(r) for r in rules]
        embeddings = await self._get_rule_embeddings(rules, rule_texts)

        assert self._embedding_generator is not None
        query_vec = np.array(await self._embedding_generator.embed_text(query_text))

        scored: list[StandardMatch] = []
        for rule, emb in zip(rules, embeddings, strict=True):
            rule_vec = np.array(emb)
            sim = self._cosine_similarity(query_vec, rule_vec)
            scored.append(
                StandardMatch(
                    rule_id=rule.id,
                    rule_title=rule.title,
                    category=rule.category,
                    subcategory=rule.subcategory,
                    level=rule.level,
                    similarity=round(float(sim), 4),
                )
            )

        scored.sort(key=lambda m: m.similarity, reverse=True)
        top = scored[: self._top_k]
        logger.info(
            f"规范召回Top{len(top)}: "
            + ", ".join(f"{m.rule_id}({m.similarity:.3f})" for m in top[:5])
        )
        return top

    def _retrieve_by_keywords(
        self, query_text: str, rules: list[Any]
    ) -> list[StandardMatch]:
        """关键词重叠降级召回。"""
        query_terms = self._extract_terms(query_text)
        scored: list[StandardMatch] = []
        for rule in rules:
            doc = self._rule_to_document(rule)
            doc_terms = self._extract_terms(doc)
            if not doc_terms:
                continue
            overlap = len(query_terms & doc_terms)
            if overlap == 0:
                continue
            score = overlap / max(len(doc_terms), 1)
            scored.append(
                StandardMatch(
                    rule_id=rule.id,
                    rule_title=rule.title,
                    category=rule.category,
                    subcategory=rule.subcategory,
                    level=rule.level,
                    similarity=round(score, 4),
                )
            )
        scored.sort(key=lambda m: m.similarity, reverse=True)
        return scored[: self._top_k]

    @staticmethod
    def _extract_terms(text: str) -> set[str]:
        """从文本中提取关键词（分别处理英文单词和中文词语）。"""
        text_lower = text.lower()
        # 提取英文单词（2个字母以上）
        english_terms = set(re.findall(r"[a-z0-9_]{2,}", text_lower))
        # 提取中文词语（2个汉字以上）
        chinese_terms = set(re.findall(r"[\u4e00-\u9fff]{2,}", text_lower))
        return english_terms | chinese_terms

    # ------------------------------------------------------------------
    # 规范embedding缓存
    # ------------------------------------------------------------------

    async def _get_rule_embeddings(
        self, rules: list[Any], rule_texts: list[str]
    ) -> list[list[float]]:
        """获取全部规范条款的embedding，优先使用磁盘缓存。"""
        if self._rule_embeddings is None:
            self._rule_embeddings = self._load_embedding_cache()

        missing_indices: list[int] = []
        missing_texts: list[str] = []
        result: list[list[float] | None] = [None] * len(rules)

        for i, (rule, text) in enumerate(zip(rules, rule_texts, strict=True)):
            text_hash = self._hash_text(text)
            cached = self._rule_embeddings.get(rule.id)
            if cached and cached[0] == text_hash:
                result[i] = cached[1]
            else:
                missing_indices.append(i)
                missing_texts.append(text)

        if missing_texts:
            assert self._embedding_generator is not None
            logger.info(f"计算 {len(missing_texts)} 条规范embedding（其余命中缓存）")
            new_embeddings = await self._embedding_generator.embed_batch(missing_texts)
            for idx, text, emb in zip(missing_indices, missing_texts, new_embeddings, strict=True):
                rule_id = rules[idx].id
                self._rule_embeddings[rule_id] = (self._hash_text(text), emb)
                result[idx] = emb
            self._save_embedding_cache()

        return [e if e is not None else [] for e in result]

    def _load_embedding_cache(self) -> dict[str, tuple[str, list[float]]]:
        """从磁盘加载规范embedding缓存。"""
        if not self._emb_cache_file.exists():
            return {}
        try:
            data = json.loads(self._emb_cache_file.read_text(encoding="utf-8"))
            return {rid: (item["hash"], item["embedding"]) for rid, item in data.items()}
        except Exception as e:
            logger.warning(f"规范embedding缓存加载失败，将重新计算: {e}")
            return {}

    def _save_embedding_cache(self) -> None:
        """保存规范embedding缓存到磁盘。"""
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            data = {
                rid: {"hash": h, "embedding": emb}
                for rid, (h, emb) in (self._rule_embeddings or {}).items()
            }
            self._emb_cache_file.write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"规范embedding缓存保存失败: {e}")

    # ------------------------------------------------------------------
    # LLM精排
    # ------------------------------------------------------------------

    async def _llm_rerank(
        self, query_text: str, candidates: list[StandardMatch]
    ) -> list[StandardMatch] | None:
        """LLM逐条判定候选规范与故障结论的关系。失败时返回None。"""
        prompt = self._build_rerank_prompt(query_text, candidates[:MAX_RULES_FOR_LLM])

        if self._llm_provider is None:
            return None
        try:
            response = await self._llm_provider.generate(
                system=(
                    "你是研发规范审查专家。你的任务是判断故障分析结论与给定规范条款的关系。"
                    "只基于证据判断，不要臆测。严格按JSON格式输出。"
                ),
                user=prompt,
            )
            return self._parse_rerank_response(str(response), candidates)
        except Exception as e:
            logger.error(f"LLM规范精排失败: {e}")
            return None

    def _build_rerank_prompt(
        self, query_text: str, candidates: list[StandardMatch]
    ) -> str:
        rules_text = ""
        for i, c in enumerate(candidates, 1):
            rule = self._standards_manager.get_rule(c.rule_id)
            content = rule.content[:300] if rule else ""
            rules_text += (
                f"\n### 候选{i}: {c.rule_id}（{c.level}）\n"
                f"标题: {c.rule_title}\n"
                f"内容: {content}\n"
            )

        return f"""请判断以下故障分析结论与候选规范条款的关系。

## 故障分析结论
{query_text[:2000]}

## 候选规范条款
{rules_text}

请逐条判定每个候选规范与故障结论的关系，返回JSON数组：
[
  {{
    "rule_id": "规范ID",
    "relation": "violated|related|unrelated",
    "confidence": 0.0-1.0,
    "evidence": "判定依据（引用故障结论中的具体证据，50字以内）"
  }}
]

判定标准：
- violated: 故障根因/代码变更明确表明违反了该规范（如规范禁止的行为正是故障成因）
- related: 规范与故障主题相关但非直接违反（如改进方向、关联实践）
- unrelated: 与故障无关

只输出JSON数组，不要其他内容。"""

    def _parse_rerank_response(
        self, response: str, candidates: list[StandardMatch]
    ) -> list[StandardMatch]:
        """解析LLM精排响应，合并到候选列表。"""
        json_match = re.search(r"\[[\s\S]*\]", response)
        if not json_match:
            raise ValueError("LLM响应中未找到JSON数组")

        judgements = json.loads(json_match.group())
        candidate_map = {c.rule_id: c for c in candidates}
        matches: list[StandardMatch] = []

        for item in judgements:
            rule_id = str(item.get("rule_id", ""))
            relation = str(item.get("relation", RELATION_UNRELATED))
            if rule_id not in candidate_map or relation == RELATION_UNRELATED:
                continue

            candidate = candidate_map[rule_id]
            candidate.relation = (
                RELATION_VIOLATED if relation == RELATION_VIOLATED else RELATION_RELATED
            )
            candidate.confidence = float(item.get("confidence", 0.5))
            candidate.evidence = str(item.get("evidence", ""))
            matches.append(candidate)

        # violated在前，其后按confidence排序
        matches.sort(
            key=lambda m: (m.relation != RELATION_VIOLATED, -m.confidence)
        )
        return matches

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _rule_to_document(rule: Any) -> str:
        """规范条款转向量化文档文本。"""
        return f"{rule.id} {rule.subcategory} {rule.title} {rule.content}"

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
