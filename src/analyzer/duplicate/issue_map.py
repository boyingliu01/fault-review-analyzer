"""Issue No 映射表加载器。

泄漏缺陷复盘映射 Excel（Incident sheet）以行记录 Issue No 与关联的
研发云任务单（urId）：同一原始 issue 的主分支/现网分支重复单共享同一
Issue No。本加载器把该表读成 urId -> Issue No 映射，供重复单识别的
第〇层（确定性关联）使用。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ISSUE_MAP_SHEET = "Incident"
_ISSUE_COL = "Issue No"
_URID_COL = "urId"


def load_issue_map(xlsx_path: Path | str, sheet: str = ISSUE_MAP_SHEET) -> dict[int, str]:
    """读取映射表，返回 ``{urId: issue_no}``。

    - 空白单元格行跳过；同一 urId 多个 Issue No 时取首个（映射表每单
      原则上只挂一个原始 issue）
    - 缺失必需列（Issue No / urId）时抛 ValueError，提示映射表格式
    """
    path = Path(xlsx_path)
    if not path.is_file():
        raise FileNotFoundError(f"映射表不存在: {path}")
    df = pd.read_excel(path, sheet_name=sheet)
    missing = [col for col in (_ISSUE_COL, _URID_COL) if col not in df.columns]
    if missing:
        raise ValueError(f"映射表缺少必需列: {missing}（sheet={sheet}）")
    mapping: dict[int, str] = {}
    for _, row in df.iterrows():
        urid, issue = row.get(_URID_COL), row.get(_ISSUE_COL)
        if pd.isna(urid) or pd.isna(issue):
            continue
        key = int(urid)
        if key not in mapping:
            mapping[key] = str(issue).strip()
    return mapping
