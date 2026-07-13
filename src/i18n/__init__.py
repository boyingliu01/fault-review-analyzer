"""国际化模块"""

from .manager import I18nManager, _, i18n
from .translations import get_translation, translate_dict

__all__ = ["i18n", "I18nManager", "_", "get_translation", "translate_dict"]
