"""复发模式检测器 - 从故障单中发现重复出现的故障模式。

根据故障单的标题/描述/标签相似性，识别重复出现的故障模式，
生成 RecurrencePattern 供告警与改进参考。

GAP G10: 实现规范要求的 recurrence_detector.py 组件。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from src.feedback.models import RecurrencePattern

_DEFAULT_SIMILARITY_THRESHOLD = 0.7


class RecurrenceDetector:
    """复发模式检测器。

    基于关键词重叠与可选 embedding 余弦相似度，将相似故障单聚合成复发模式。
    不依赖外部向量库，核心逻辑为关键词/Jaccard 相似度，可独立运行。
    """

    def __init__(
        self,
        similarity_threshold: float = _DEFAULT_SIMILARITY_THRESHOLD,
        embedding_generator: Any | None = None,
    ) -> None:
        self._similarity_threshold = similarity_threshold
        self._embedding_generator = embedding_generator

    def detect(
        self,
        tasks: list[dict[str, Any]],
        task_ids: list[str] | None = None,
    ) -> list[RecurrencePattern]:
        """检测复发模式。

        Args:
            tasks: 故障单字典列表，每项含 title/description/labels 等字段
            task_ids: 与 tasks 一一对应的故障单ID列表（可选，缺省用 task_id 字段）

        Returns:
            检测到的复发模式列表（出现次数 >= 2 的相似簇）
        """
        if not tasks:
            return []

        ids = task_ids or [str(t.get("task_id", i)) for i, t in enumerate(tasks)]

        # 提取每个任务的特征文本
        features = [self._extract_features(t) for t in tasks]

        # 基于相似度聚合
        clusters = self._cluster_by_similarity(features)

        patterns = []
        for cluster in clusters:
            if len(cluster["indices"]) < 2:
                continue  # 只报告出现 >= 2 次的模式
            pattern = self._build_pattern(cluster, tasks, ids)
            if pattern is not None:
                patterns.append(pattern)

        # 按出现次数降序排序
        patterns.sort(key=lambda p: p.occurrence_count, reverse=True)
        return patterns

    def _extract_features(self, task: dict[str, Any]) -> str:
        """提取任务的特征文本用于相似度比较。"""
        parts = [
            task.get("title", ""),
            task.get("description", ""),
            task.get("problem_category", ""),
        ]
        # 标签
        labels = task.get("labels", [])
        if isinstance(labels, list):
            parts.extend(
                str(label.get("name", label)) if isinstance(label, dict) else str(label)
                for label in labels
            )
        elif isinstance(labels, str):
            parts.append(labels)

        return " ".join(parts).strip()

    def _cluster_by_similarity(
        self,
        features: list[str],
    ) -> list[dict[str, Any]]:
        """基于特征文本相似度聚合任务。"""
        clusters: list[dict[str, Any]] = []
        assigned: set[int] = set()

        for i, feature in enumerate(features):
            if i in assigned:
                continue

            cluster: dict[str, Any] = {"indices": [i], "feature": feature}
            for j in range(i + 1, len(features)):
                if j in assigned:
                    continue
                sim = self._compute_similarity(feature, features[j])
                if sim >= self._similarity_threshold:
                    indices = cluster["indices"]
                    if isinstance(indices, list):
                        indices.append(j)
                    assigned.add(j)

            assigned.add(i)
            clusters.append(cluster)

        return clusters

    def _compute_similarity(self, text_a: str, text_b: str) -> float:
        """计算两个文本的相似度（0~1）。

        优先使用 embedding 余弦相似度（若提供 embedding_generator），
        否则退化为基于关键词集合的 Jaccard 相似度。
        """
        if not text_a or not text_b:
            return 0.0

        if self._embedding_generator is not None:
            try:
                return self._embedding_similarity(text_a, text_b)
            except Exception as e:
                logger.debug(f"Embedding 相似度计算失败，退化为关键词相似度: {e}")

        return self._keyword_similarity(text_a, text_b)

    def _embedding_similarity(self, text_a: str, text_b: str) -> float:
        """基于 embedding 的余弦相似度（同步包装）。"""
        import asyncio

        generator = self._embedding_generator
        if generator is None:
            return self._keyword_similarity(text_a, text_b)

        try:
            asyncio.get_running_loop()
            # 已在事件循环中，无法同步运行异步 embedding
            return self._keyword_similarity(text_a, text_b)
        except RuntimeError:
            pass

        async def _compute() -> float:
            vectors = await generator.embed_batch([text_a, text_b])
            if len(vectors) < 2:
                return 0.0
            va, vb = vectors[0], vectors[1]
            return float(self._cosine_similarity(va, vb))

        return float(asyncio.run(_compute()))

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """计算两个向量的余弦相似度。"""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    @staticmethod
    def _keyword_similarity(text_a: str, text_b: str) -> float:
        """基于关键词集合的 Jaccard 相似度。"""
        import re

        def tokenize(text: str) -> set[str]:
            # 中文按字符切分，英文按词切分
            words = re.findall(r"[a-zA-Z0-9_]+", text.lower())
            chars = re.findall(r"[\u4e00-\u9fff]", text)
            return set(words) | set(chars)

        set_a = tokenize(text_a)
        set_b = tokenize(text_b)
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union)

    def _build_pattern(
        self,
        cluster: dict[str, Any],
        tasks: list[dict[str, Any]],
        ids: list[str],
    ) -> RecurrencePattern | None:
        """根据聚类结果构建 RecurrencePattern。"""
        indices = cluster["indices"]
        member_tasks = [tasks[i] for i in indices]
        member_ids = [ids[i] for i in indices]

        # 汇总关键词
        keywords = self._aggregate_keywords(member_tasks)

        # 时间信息
        timestamps = [
            t.get("create_time", t.get("created_at", t.get("createdDate", "")))
            for t in member_tasks
        ]
        first_seen = self._parse_timestamp(min(timestamps, key=lambda x: str(x)))
        last_seen = self._parse_timestamp(max(timestamps, key=lambda x: str(x)))

        # 严重程度：取最高
        severity = "medium"
        for t in member_tasks:
            sev = str(t.get("severity", "medium")).lower()
            if sev in {"high", "critical"}:
                severity = "high"
                break

        # 置信度：基于相似度
        confidence = min(0.95, 0.6 + 0.05 * (len(member_tasks) - 1))

        return RecurrencePattern(
            name=f"复发模式 #{indices[0] + 1}",
            description=cluster["feature"][:200],
            keywords=keywords,
            task_ids=member_ids,
            occurrence_count=len(member_tasks),
            first_seen=first_seen,
            last_seen=last_seen,
            similarity_threshold=self._similarity_threshold,
            confidence=round(confidence, 2),
            severity=severity,
        )

    @staticmethod
    def _aggregate_keywords(tasks: list[dict[str, Any]]) -> list[str]:
        """从任务中聚合高频关键词。"""
        import re
        from collections import Counter

        counter: Counter[str] = Counter()
        for task in tasks:
            text = " ".join(
                [
                    str(task.get("title", "")),
                    str(task.get("description", "")),
                    str(task.get("problem_category", "")),
                ]
            )
            for word in re.findall(r"[a-zA-Z0-9_]{2,}", text.lower()):
                counter[word] += 1
            for char in re.findall(r"[\u4e00-\u9fff]", text):
                counter[char] += 1

        # 过滤常见停用词
        stopwords = {"the", "and", "for", "with", "that", "this", "are", "was"}
        keywords = [word for word, _ in counter.most_common(10) if word not in stopwords]
        return keywords

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        """将各种时间格式解析为 datetime。"""
        if isinstance(value, datetime):
            return value
        if value is None or value == "":
            return datetime.now()
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return datetime.now()
