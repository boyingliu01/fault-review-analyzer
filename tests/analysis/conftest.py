"""Analysis模块测试 fixtures"""

from datetime import datetime

from unittest.mock import MagicMock

import pytest

from src.analysis.code_change_analyzer import CodeChangeAnalyzer
from src.analysis.enhanced_llm_analyzer import EnhancedLLMAnalyzer
from src.analysis.root_cause_validator import RootCauseValidator
from src.analysis.violation_detector import ViolationDetector
from src.knowledge.manager import StandardsManager


@pytest.fixture
def standards_manager():
    return StandardsManager()


@pytest.fixture
def violation_detector(standards_manager):
    return ViolationDetector(standards_manager=standards_manager)


@pytest.fixture
def root_cause_validator():
    return RootCauseValidator()


@pytest.fixture
def code_change_analyzer():
    return CodeChangeAnalyzer()


@pytest.fixture
def enhanced_llm_analyzer(standards_manager):
    return EnhancedLLMAnalyzer(standards_manager=standards_manager)


@pytest.fixture
def sample_fault_info():
    return {
        "task_id": "TASK-001",
        "title": "空指针异常导致服务崩溃",
        "description": "代码中存在空指针未做校验",
        "code_snippet": "user.getName(); // user可能为null",
        "development": {"commits": []},
    }


@pytest.fixture
def sample_fault_info_with_code():
    return {
        "task_id": "TASK-002",
        "title": "数据库连接泄漏",
        "description": "获取连接后未关闭",
        "code_snippet": "Connection conn = ds.getConnection();",
        "development": {
            "commits": [
                {
                    "commit_id": "abc123",
                    "message": "添加数据库操作",
                    "author": "dev1",
                    "timestamp": datetime(2024, 1, 15, 10, 0, 0),
                    "diff": "+Connection conn = ds.getConnection();",
                    "files_changed": ["src/DbUtil.java"],
                }
            ]
        },
    }


@pytest.fixture
def mock_llm_provider():
    mock_provider = MagicMock()
    mock_provider.generate.return_value = '{"is_actionable": true, "actionability_score": 0.8}'
    return mock_provider
