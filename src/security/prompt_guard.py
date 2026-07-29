"""
Prompt 注入防护模块

提供对 LLM 输入文本的清洗、注入模式检测和防护功能。
"""

import re

from loguru import logger


class PromptGuard:
    """
    Prompt 注入防护器

    检测并阻止常见的 Prompt 注入模式，提供输入清洗和验证功能。
    """

    # 注入模式正则表达式
    INJECTION_PATTERNS = [
        # 直接忽略指令模式
        re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
        re.compile(r"disregard\s+previous\s+instructions", re.IGNORECASE),
        re.compile(r"pay\s+no\s+attention\s+to\s+previous\s+instructions", re.IGNORECASE),
        # 系统提示词覆盖模式
        re.compile(r"system\s+prompt", re.IGNORECASE),
        re.compile(r"override\s+system\s+prompt", re.IGNORECASE),
        re.compile(r"reset\s+system\s+prompt", re.IGNORECASE),
        # 模式切换模式
        re.compile(r"you\s+are\s+now", re.IGNORECASE),
        re.compile(r"you\s+are\s+to\s+act\s+as", re.IGNORECASE),
        re.compile(r"pretend\s+to\s+be", re.IGNORECASE),
        # 特殊模式
        re.compile(r"\bDAN\b", re.IGNORECASE),
        re.compile(r"do\s+anything\s+now", re.IGNORECASE),
        re.compile(r"developer\s+mode", re.IGNORECASE),
        re.compile(r"debug\s+mode", re.IGNORECASE),
        # XML 标签注入
        re.compile(r"<system>", re.IGNORECASE),
        re.compile(r"</system>", re.IGNORECASE),
        re.compile(r"<prompt>", re.IGNORECASE),
        re.compile(r"</prompt>", re.IGNORECASE),
        re.compile(r"<user>", re.IGNORECASE),
        re.compile(r"</user>", re.IGNORECASE),
    ]

    DEFAULT_MAX_LENGTH = 8192

    def __init__(self, max_length: int = DEFAULT_MAX_LENGTH):
        """
        初始化 PromptGuard

        Args:
            max_length: 允许的最大输入长度（默认 8192）
        """
        self.max_length = max_length
        logger.debug(f"PromptGuard 初始化完成，最大长度限制: {self.max_length}")

    def detect_injection(self, text: str) -> list[tuple[str, str]]:
        """
        检测文本中的注入模式

        Args:
            text: 待检测的文本

        Returns:
            检测到的注入模式列表，包含 (模式类型, 匹配文本) 元组
        """
        detected = []

        for pattern in self.INJECTION_PATTERNS:
            matches = pattern.findall(text)
            for match in matches:
                detected.append((pattern.pattern, match))

        return detected

    def clean_text(self, text: str) -> str:
        """
        清洗文本，移除或转义潜在的恶意内容

        Args:
            text: 待清洗的文本

        Returns:
            清洗后的文本
        """
        # 移除或转义潜在的注入模式
        cleaned = text

        # 转义 XML 标签
        cleaned = cleaned.replace("<", "&lt;").replace(">", "&gt;")

        return cleaned

    def validate(self, text: str) -> tuple[bool, str, list[tuple[str, str]]]:
        """
        验证文本是否安全

        Args:
            text: 待验证的文本

        Returns:
            (是否安全, 清洗后的文本, 检测到的注入模式)
        """
        # 检查长度限制
        if len(text) > self.max_length:
            logger.warning(f"文本长度超出限制: {len(text)} > {self.max_length}")
            return False, text[: self.max_length], []

        # 检测注入模式
        injections = self.detect_injection(text)
        if injections:
            logger.warning(f"检测到注入模式: {injections}")
            return False, text, injections

        # 文本安全
        return True, self.clean_text(text), []

    def guard(self, text: str) -> str:
        """
        防护函数，自动检测并清洗文本

        Args:
            text: 待处理的文本

        Returns:
            安全的文本（如果检测到注入，返回空字符串）
        """
        is_safe, cleaned, injections = self.validate(text)

        if not is_safe:
            logger.error(f"Prompt 验证失败，检测到注入模式: {injections}")
            return ""

        logger.debug("Prompt 验证通过")
        return cleaned


# 全局实例
_default_guard = PromptGuard()


def detect_injection(text: str) -> list[tuple[str, str]]:
    """
    检测文本中的注入模式（便捷函数）

    Args:
        text: 待检测的文本

    Returns:
        检测到的注入模式列表
    """
    return _default_guard.detect_injection(text)


def clean_text(text: str) -> str:
    """
    清洗文本（便捷函数）

    Args:
        text: 待清洗的文本

    Returns:
        清洗后的文本
    """
    return _default_guard.clean_text(text)


def validate(text: str) -> tuple[bool, str, list[tuple[str, str]]]:
    """
    验证文本是否安全（便捷函数）

    Args:
        text: 待验证的文本

    Returns:
        (是否安全, 清洗后的文本, 检测到的注入模式)
    """
    return _default_guard.validate(text)


def guard(text: str) -> str:
    """
    防护函数（便捷函数）

    Args:
        text: 待处理的文本

    Returns:
        安全的文本
    """
    return _default_guard.guard(text)
