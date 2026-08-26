"""Excel 故障单号读取工具。

从 Excel 文件中读取故障单号列表，供 CLI 批量分析使用。
支持 pandas 与 openpyxl 两种后端。
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger


def read_task_ids_from_excel(file_path: str | Path) -> list[int]:
    """从 Excel 文件读取故障单号列表。

    自动识别包含"单号/ID/任务"等关键词的列作为故障单号来源，
    兼容多种列名（缺陷单号、任务ID、taskNo 等）。

    Args:
        file_path: Excel 文件路径（.xlsx / .xls）

    Returns:
        故障单号整数列表。

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 未找到有效列或读取失败
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Excel 文件不存在: {path}")

    try:
        import pandas as pd

        df = pd.read_excel(path)
    except Exception as e:
        raise ValueError(f"无法读取 Excel 文件 {path}: {e}") from e

    if df.empty:
        return []

    # 识别故障单号列（优先匹配常见列名）
    id_column = _find_id_column([str(c) for c in df.columns])
    if id_column is None:
        raise ValueError(
            f"未找到故障单号列。请确保 Excel 包含含'单号/ID/任务'等关键词的列，"
            f"当前列: {list(df.columns)}"
        )

    # 提取并清洗单号
    task_ids: list[int] = []
    for value in df[id_column].dropna().tolist():
        try:
            # 支持数字与数字字符串（含可能的前导/尾随空格）
            task_id = int(str(value).strip())
            if task_id > 0:
                task_ids.append(task_id)
        except (ValueError, TypeError):
            logger.warning(f"跳过无效单号: {value}")

    # 去重并保持顺序
    seen: set[int] = set()
    deduped = []
    for task_id in task_ids:
        if task_id not in seen:
            seen.add(task_id)
            deduped.append(task_id)

    return deduped


def _find_id_column(columns: list[str]) -> str | None:
    """在列名中查找故障单号列。

    Returns:
        匹配的列名，未找到返回 None。
    """
    # 精确/高优先级关键词
    high_priority = ["缺陷单号", "故障单号", "任务单号", "taskno", "task_id", "taskid"]
    for col in columns:
        col_lower = str(col).lower()
        if col_lower in {k.lower() for k in high_priority}:
            return str(col)

    # 模糊匹配关键词
    keywords = ["单号", "id", "任务"]
    for col in columns:
        col_lower = str(col).lower()
        if any(keyword in col_lower for keyword in keywords):
            return str(col)

    return None
