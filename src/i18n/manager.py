"""国际化管理器"""

from pathlib import Path
from typing import Dict, Any, Optional
import threading
import json
import yaml
from loguru import logger

from .translations import TRANSLATIONS, get_translation, translate_dict


class I18nManager:
    """国际化管理器"""

    _instance: Optional["I18nManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "I18nManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._translations: Dict[str, Dict[str, str]] = dict(TRANSLATIONS)
        self._default_language = "zh"
        self._local = threading.local()
        self._local.language = self._default_language

    @property
    def language(self) -> str:
        """获取当前线程的语言"""
        return getattr(self._local, "language", self._default_language)

    @language.setter
    def language(self, lang: str) -> None:
        """设置当前线程的语言"""
        self._local.language = lang.lower()

    def set_default_language(self, lang: str) -> None:
        """设置默认语言"""
        self._default_language = lang.lower()

    def get(
        self, key: str, language: Optional[str] = None, **kwargs: Any
    ) -> str:
        """
        获取翻译文本

        Args:
            key: 翻译键
            language: 语言（可选，默认使用当前线程语言）
            **kwargs: 格式化参数

        Returns:
            翻译后的文本
        """
        lang = language.lower() if language else self.language
        text = get_translation(key, lang)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError):
                return text
        return text

    def t(
        self, key: str, language: Optional[str] = None, **kwargs: Any
    ) -> str:
        """获取翻译文本的简写方法"""
        return self.get(key, language, **kwargs)

    def translate_dict(
        self, data: Dict[str, Any], language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        递归翻译字典

        Args:
            data: 要翻译的数据字典
            language: 目标语言（可选，默认使用当前线程语言）

        Returns:
            翻译后的字典
        """
        lang = language.lower() if language else self.language
        return translate_dict(data, lang)

    def load_translations(
        self, translations: Dict[str, Dict[str, str]]
    ) -> None:
        """
        加载额外的翻译词典

        Args:
            translations: 翻译词典，格式为 {lang: {key: text}}
        """
        for lang, lang_translations in translations.items():
            lang = lang.lower()
            if lang not in self._translations:
                self._translations[lang] = {}
            self._translations[lang].update(lang_translations)
        logger.info(f"Loaded translations: {list(translations.keys())}")

    def load_translations_from_file(self, file_path: Path) -> int:
        """
        从文件加载翻译

        Args:
            file_path: 文件路径（支持 JSON 和 YAML）

        Returns:
            加载的翻译数量
        """
        if not file_path.exists():
            logger.warning(f"Translation file not found: {file_path}")
            return 0

        try:
            if file_path.suffix.lower() == ".json":
                with file_path.open(encoding="utf-8") as f:
                    translations = json.load(f)
            elif file_path.suffix.lower() in [".yaml", ".yml"]:
                with file_path.open(encoding="utf-8") as f:
                    translations = yaml.safe_load(f)
            else:
                logger.warning(f"Unsupported file format: {file_path}")
                return 0

            self.load_translations(translations)

            count = sum(len(ts) for ts in translations.values())
            logger.info(f"Loaded {count} translations from {file_path}")
            return count

        except Exception as e:
            logger.error(f"Failed to load translations from {file_path}: {e}")
            return 0

    def get_available_languages(self) -> list[str]:
        """获取可用语言列表"""
        return list(self._translations.keys())

    def set_context_language(self, language: str) -> "I18nManager":
        """
        上下文管理器：临时设置语言

        Args:
            language: 目标语言

        Returns:
            self (用于上下文管理器)

        Example:
            with i18n.set_context_language("en"):
                print(i18n.t("report.title"))
        """
        self._previous_language = self.language
        self.language = language
        return self

    def __enter__(self) -> "I18nManager":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if hasattr(self, "_previous_language"):
            self.language = self._previous_language
            delattr(self, "_previous_language")


# 全局实例
i18n = I18nManager()


def _(key: str, **kwargs: Any) -> str:
    """便捷的翻译函数"""
    return i18n.t(key, **kwargs)
