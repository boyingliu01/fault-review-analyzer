"""Issue No 映射表加载器测试（feat/duplicate-conclusion-reuse R8）。

load_issue_map：从泄漏缺陷复盘映射 Excel（Incident sheet）读取
urId -> Issue No 映射；空白行跳过，缺失必需列报错。
"""

import pandas as pd
import pytest

from src.analyzer.duplicate.issue_map import ISSUE_MAP_SHEET, load_issue_map


def _write_xlsx(path, rows):
    """构造最小 Incident sheet：Issue No / urId 两列。"""
    df = pd.DataFrame(rows, columns=["Issue No", "urId"])
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=ISSUE_MAP_SHEET, index=False)


class TestLoadIssueMap:
    def test_reads_mapping(self, tmp_path):
        fp = tmp_path / "map.xlsx"
        _write_xlsx(
            fp,
            [("IS22976", 11757372), ("IS22976", 11757373), ("IS29704", 11875712)],
        )
        mapping = load_issue_map(fp)
        assert mapping == {11757372: "IS22976", 11757373: "IS22976", 11875712: "IS29704"}

    def test_skips_blank_cells(self, tmp_path):
        fp = tmp_path / "map.xlsx"
        _write_xlsx(fp, [("IS1", 100), (None, 200), ("IS2", None)])
        mapping = load_issue_map(fp)
        assert mapping == {100: "IS1"}

    def test_first_issue_wins_on_duplicate_urid(self, tmp_path):
        fp = tmp_path / "map.xlsx"
        _write_xlsx(fp, [("IS1", 100), ("IS2", 100)])
        assert load_issue_map(fp) == {100: "IS1"}

    def test_missing_required_column_raises(self, tmp_path):
        fp = tmp_path / "bad.xlsx"
        pd.DataFrame({"foo": [1]}).to_excel(fp, sheet_name=ISSUE_MAP_SHEET, index=False)
        with pytest.raises(ValueError, match="Issue No"):
            load_issue_map(fp)

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_issue_map(tmp_path / "nope.xlsx")
