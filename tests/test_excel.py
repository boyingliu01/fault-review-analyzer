"""Excel处理测试"""

import tempfile
import time
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def sample_excel_file():
    """创建临时Excel文件用于测试"""
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        file_path = f.name

    # 创建测试数据
    df = pd.DataFrame(
        {
            "缺陷单号": [12345, 12346, 12347],
            "标题": ["Test 1", "Test 2", "Test 3"],
            "描述": ["Desc 1", "Desc 2", "Desc 3"],
            "状态": ["Open", "Closed", "Open"],
        }
    )
    df.to_excel(file_path, index=False)

    yield file_path

    # 清理 - Windows上可能需要重试
    for _ in range(3):
        try:
            Path(file_path).unlink(missing_ok=True)
            break
        except PermissionError:
            time.sleep(0.1)


def test_read_excel_columns(sample_excel_file):
    """测试读取Excel列名"""
    df = pd.read_excel(sample_excel_file)

    assert "缺陷单号" in df.columns
    assert "标题" in df.columns
    assert "描述" in df.columns
    assert "状态" in df.columns


def test_read_excel_data(sample_excel_file):
    """测试读取Excel数据"""
    df = pd.read_excel(sample_excel_file)

    # 验证数据
    assert len(df) == 3
    assert df["缺陷单号"].iloc[0] == 12345
    assert df["标题"].iloc[0] == "Test 1"


def test_find_id_column(sample_excel_file):
    """测试查找ID列"""
    df = pd.read_excel(sample_excel_file)

    # 查找包含特定关键词的列
    id_columns = []
    for col in df.columns:
        if any(keyword in col for keyword in ["单号", "ID", "id", "任务"]):
            id_columns.append(col)

    assert len(id_columns) >= 1
    assert "缺陷单号" in id_columns
