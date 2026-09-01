"""从业务复盘xlsx提取 urId → 责任产品线 映射，输出 output/product_line_map.json。

权威口径：三个产品线 defect sheet 的"责任产品线"字段直接反映业务归属，
替代 generate_client_report.py 原先按标题关键词的推断（与业务口径不一致
率 34%，62/181——ZSmart_DRM 硬编码归 BSS 但 GOMO 类实际归数渠，电商
产品线在标题推断中不存在）。

数据源（默认，可用参数覆盖目录）:
    E:\\work\\产品研发管理部\\005-专项改进推进\\2026.08 新电故障复盘\\泄漏缺陷复盘\\
    新电泄漏缺陷复盘结论（BSS/电商/数渠）.xlsx —— 名为 defect* 的 sheet

用法:
    python scripts/extract_product_line_map.py [业务xlsx所在目录]
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import openpyxl  # type: ignore[import-untyped]

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "output"
DEFAULT_SRC = Path(
    r"E:\work\产品研发管理部\005-专项改进推进\2026.08 新电故障复盘\泄漏缺陷复盘"
)
DEFECT_SHEET_PREFIX = "defect"


def find_col(header: list[str], *names: str) -> int:
    """按候选名顺序查找列索引（精确匹配优先）。"""
    for name in names:
        for i, h in enumerate(header):
            if h == name:
                return i
    return -1


def extract(src_dir: Path) -> dict[str, list[str]]:
    """扫描 defect sheet，汇总 urId → [责任产品线取值,...]（保留重复以检测冲突）。"""
    mapping: dict[str, list[str]] = defaultdict(list)
    files = sorted(src_dir.glob("新电泄漏缺陷复盘结论（*）.xlsx"))
    if not files:
        raise FileNotFoundError(f"{src_dir} 下未找到复盘结论xlsx")
    for fp in files:
        wb = openpyxl.load_workbook(fp, read_only=True, data_only=True)
        for ws in wb.worksheets:
            if not ws.title.startswith(DEFECT_SHEET_PREFIX):
                continue
            rows = list(ws.iter_rows(values_only=True))
            if len(rows) < 2:
                continue
            header = [str(c).strip() if c is not None else "" for c in rows[0]]
            i_urid = find_col(header, "urId")
            i_line = find_col(header, "责任产品线")
            if i_urid < 0 or i_line < 0:
                print(f"  跳过（缺 urId/责任产品线 列）: {fp.name} [{ws.title}]")
                continue
            for row in rows[1:]:
                urid = row[i_urid] if i_urid < len(row) else None
                line = row[i_line] if i_line < len(row) else None
                if urid is None or str(urid).strip() == "":
                    continue
                line_s = str(line).strip() if line is not None else ""
                if line_s:
                    mapping[str(int(urid))].append(line_s)
        wb.close()
    return mapping


def main() -> None:
    src_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    mapping = extract(src_dir)

    # 冲突检测：同一 urId 在多表取值不一致
    resolved: dict[str, str] = {}
    conflicts: dict[str, list[str]] = {}
    for urid, lines in mapping.items():
        uniq = sorted(set(lines))
        if len(uniq) == 1:
            resolved[urid] = uniq[0]
        else:
            conflicts[urid] = uniq
            resolved[urid] = uniq[0]  # 冲突时取字典序第一个，明细记入 _meta

    dist: dict[str, int] = defaultdict(int)
    for v in resolved.values():
        dist[v] += 1

    out = {
        "_meta": {
            "description": "业务复盘xlsx『责任产品线』字段 → urId 权威映射",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source_dir": str(src_dir),
            "count": len(resolved),
            "distribution": dict(dist),
            "conflicts": conflicts,
            "usage": "generate_client_report.py 优先查此映射，未命中回退标题推断",
        },
        "map": resolved,
    }
    out_file = OUT_DIR / "product_line_map.json"
    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"提取 {len(resolved)} 个 urId → 责任产品线")
    print(f"产品线分布: {dict(dist)}")
    if conflicts:
        print(f"跨表取值冲突 {len(conflicts)} 个（已取字典序第一个，见 _meta.conflicts）:")
        for u, vals in list(conflicts.items())[:20]:
            print(f"  {u}: {vals}")
    print(f"已写入: {out_file}")


if __name__ == "__main__":
    main()
