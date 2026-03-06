import json

import pytest

from src.knowledge.manager import StandardsManager


@pytest.fixture
def standards_data_dir(tmp_path):
    standards_dir = tmp_path / "standards" / "mock"
    standards_dir.mkdir(parents=True)

    java_standards = {
        "version": "1.0",
        "category": "java_coding",
        "name": "Java编码规范",
        "description": "Java代码开发规范",
        "rules": [
            {
                "id": "JAVA-001",
                "category": "代码规范",
                "subcategory": "异常处理",
                "title": "禁止捕获异常后不做任何处理",
                "content": "捕获异常后必须进行处理",
                "level": "强制",
                "code": "J000001",
                "examples": ["try { ... } catch (Exception e) { }"],
            },
            {
                "id": "JAVA-002",
                "category": "代码规范",
                "subcategory": "资源管理",
                "title": "数据库连接必须正确关闭",
                "content": "使用完数据库连接后必须关闭",
                "level": "强制",
                "code": "J000002",
                "examples": [],
            },
        ],
    }

    database_standards = {
        "version": "1.0",
        "category": "database_design",
        "name": "数据库设计规范",
        "description": "数据库设计和开发规范",
        "rules": [
            {
                "id": "DB-001",
                "category": "设计规范",
                "subcategory": "索引设计",
                "title": "禁止使用函数索引",
                "content": "不建议在索引列上使用函数",
                "level": "强制",
                "code": "D000001",
                "examples": [],
            }
        ],
    }

    (standards_dir / "java_coding_standards.json").write_text(
        json.dumps(java_standards, ensure_ascii=False)
    )
    (standards_dir / "database_standards.json").write_text(
        json.dumps(database_standards, ensure_ascii=False)
    )

    return standards_dir


@pytest.fixture
def standards_manager(standards_data_dir):
    return StandardsManager(data_dir=standards_data_dir)


@pytest.fixture
def sample_java_standards():
    return {
        "version": "1.0",
        "category": "java_coding",
        "name": "Java编码规范",
        "rules": [
            {
                "id": "JAVA-001",
                "category": "代码规范",
                "subcategory": "异常处理",
                "title": "禁止捕获异常后不做任何处理",
                "content": "捕获异常后必须进行处理",
                "level": "强制",
                "code": "J000001",
                "examples": [],
            }
        ],
    }


@pytest.fixture
def sample_database_standards():
    return {
        "version": "1.0",
        "category": "database_design",
        "name": "数据库设计规范",
        "rules": [
            {
                "id": "DB-001",
                "category": "设计规范",
                "subcategory": "索引设计",
                "title": "禁止使用函数索引",
                "content": "不建议在索引列上使用函数",
                "level": "强制",
                "code": "D000001",
                "examples": [],
            }
        ],
    }
