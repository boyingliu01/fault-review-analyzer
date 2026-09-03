"""重复单识别与结论复用引擎。

主分支与现网分支各开一单修复的重复故障单（如 11757372/11757373）内容
基本一致，独立复盘会产出不一致结论。本模块在复盘前识别关联单并复用
已复审的结论，保证重复单结论一致性。
"""

from src.analyzer.duplicate.detector import (
    DuplicateDetector,
    RelatedPair,
    TaskCandidate,
    candidate_from_task,
)
from src.analyzer.duplicate.issue_map import load_issue_map
from src.analyzer.duplicate.reuser import apply_reused_conclusion

__all__ = [
    "DuplicateDetector",
    "RelatedPair",
    "TaskCandidate",
    "apply_reused_conclusion",
    "candidate_from_task",
    "load_issue_map",
]
