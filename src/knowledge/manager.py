"""规范知识库管理器 - 加载和管理研发规范"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from src.core.models import StandardCategory, StandardRule


class StandardsManager:
    """规范知识库管理器 - 负责加载和管理研发规范"""

    def __init__(self, data_dir: Path | str | None = None) -> None:
        self._data_dir = Path(data_dir) if data_dir else self._get_default_data_dir()
        self._categories: dict[str, StandardCategory] = {}
        self._rules_index: dict[str, StandardRule] = {}
        self._load_all()

    def _get_default_data_dir(self) -> Path:
        # 优先加载 production 目录（真实规范库），若不存在则回退到 mock 目录
        base = Path(__file__).parent.parent.parent / "data" / "standards"
        production_dir = base / "production"
        if production_dir.exists() and any(production_dir.glob("*_standards.json")):
            return production_dir
        return base / "mock"

    def _load_all(self) -> None:
        if not self._data_dir.exists():
            logger.warning(f"规范数据目录不存在: {self._data_dir}")
            return

        for json_file in self._data_dir.glob("*_standards.json"):
            self._load_category_file(json_file)

    def _load_category_file(self, file_path: Path) -> int:
        try:
            with file_path.open(encoding="utf-8") as f:
                data = json.load(f)

            category_id = data.get("category", file_path.stem.replace("_standards", ""))
            category_name = data.get("name", category_id)
            category_desc = data.get("description", "")

            rules = []
            for rule_data in data.get("rules", []):
                rule = StandardRule(
                    id=rule_data.get("id", ""),
                    category=category_id,
                    subcategory=rule_data.get("subcategory", ""),
                    title=rule_data.get("title", ""),
                    content=rule_data.get("content", ""),
                    level=rule_data.get("level", "推荐"),
                    code=rule_data.get("code", ""),
                    examples=rule_data.get("examples", []),
                )
                rules.append(rule)
                self._rules_index[rule.id] = rule

            category = StandardCategory(
                id=category_id,
                name=category_name,
                description=category_desc,
                rules=rules,
            )
            self._categories[category_id] = category

            logger.info(f"加载规范类别: {category_id}, 规则数: {len(rules)}")
            return len(rules)

        except Exception as e:
            logger.error(f"加载规范文件失败 {file_path}: {e}")
            return 0

    def load_category(self, category_id: str) -> StandardCategory | None:
        """加载指定类别"""
        return self._categories.get(category_id)

    def get_all_categories(self) -> list[StandardCategory]:
        """获取所有规范类别"""
        return list(self._categories.values())

    def get_rule(self, rule_id: str) -> StandardRule | None:
        """根据ID获取规则"""
        return self._rules_index.get(rule_id)

    def search_rules(self, keyword: str) -> list[StandardRule]:
        """按关键字搜索规则"""
        keyword_lower = keyword.lower()
        results = []
        for rule in self._rules_index.values():
            if (
                keyword_lower in rule.title.lower()
                or keyword_lower in rule.content.lower()
                or keyword_lower in rule.subcategory.lower()
            ):
                results.append(rule)
        return results

    def get_rules_by_level(self, level: str) -> list[StandardRule]:
        """按级别获取规则"""
        return [rule for rule in self._rules_index.values() if rule.level == level]

    def get_rules_by_subcategory(self, category: str, subcategory: str) -> list[StandardRule]:
        """按类别和子类别获取规则"""
        return [
            rule
            for rule in self._rules_index.values()
            if rule.category == category and rule.subcategory == subcategory
        ]

    def get_total_rules_count(self) -> int:
        """获取规则总数"""
        return len(self._rules_index)

    def reload(self) -> None:
        """重新加载所有规范"""
        self._categories.clear()
        self._rules_index.clear()
        self._load_all()
