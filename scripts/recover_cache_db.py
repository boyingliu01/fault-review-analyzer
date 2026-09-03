"""从被清空的 cache.db 中恢复被删除的 task 数据（SQLite 页级解析恢复）.

背景：
    CacheManager.__init__ 会在构造时执行 cleanup_expired()
    （src/cache/manager.py）。全量 pytest 期间，某测试实例化了指向真实库
    data/cache/cache.db 的 CacheManager，此时 194 条 task 数据均已过 TTL
    （CACHE_TTL=86400，数据 8/27 fetch），构造即被全部删除。
    删除后 page_count=14762、freelist_count=14759：被删页几乎未被覆盖，
    可通过解析表 btree 叶页与 overflow 链恢复原始 record。

方法：
    1. 扫描文件全部 4096 字节页，识别表 btree 叶页（btree header 首字节 0x0D）；
    2. 解析 cell 指针数组与 cell（payload_len varint + rowid varint + payload），
       payload 溢出时沿 overflow 页链（页首 4 字节 next 指针）拼接；
    3. 按 SQLite record 格式反序列化（header varint + serial types + body），
       取第 2 列 data TEXT（task JSON）；
    4. json.loads 校验：顶层须含 task_id 与 title 才收；
    5. 按 task_id 去重。dry-run 只统计校验；--write 时先备份原文件再写回
       cache 表（expires_at 续期 30 天，避免再次被 cleanup_expired 清除）。

用法：
    python scripts/recover_cache_db.py            # dry-run：只统计与校验
    python scripts/recover_cache_db.py --write    # 备份原库后写回
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import struct
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "cache" / "cache.db"
PAGE_SIZE = 4096


def read_varint(buf: bytes, offset: int) -> tuple[int, int]:
    """读取 SQLite varint，返回 (值, 新偏移)。"""
    result = 0
    for i in range(8):
        byte = buf[offset + i]
        result = (result << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return result, offset + i + 1
    result = (result << 8) | buf[offset + 8]
    return result, offset + 9


def serial_size(st: int) -> int:
    """SQLite record serial type 对应的内容字节数。"""
    if st >= 12:
        return (st - 12) // 2 if st % 2 == 0 else (st - 13) // 2
    return (0, 1, 2, 3, 4, 6, 8, 8, 0, 0, 0, 0)[st]


def parse_record(payload: bytes) -> list[Any]:
    """反序列化 SQLite record：header + serial types + body。"""
    header_len, offset = read_varint(payload, 0)
    if header_len <= 0 or header_len > len(payload):
        raise IndexError("invalid header length")
    types: list[int] = []
    while offset < header_len:
        st, offset = read_varint(payload, offset)
        types.append(st)
    values: list[Any] = []
    body = header_len
    for st in types:
        size = serial_size(st)
        raw = payload[body : body + size]
        if st == 0:
            values.append(None)
        elif 1 <= st <= 6:
            values.append(int.from_bytes(raw, "big", signed=True))
        elif st == 7:
            values.append(struct.unpack(">d", raw)[0])
        elif st == 8:
            values.append(0)
        elif st == 9:
            values.append(1)
        elif st >= 13 and st % 2 == 1:
            values.append(raw.decode("utf-8", errors="replace"))
        else:
            values.append(raw)
        body += size
    return values


def extract_records(data: bytes) -> list[tuple[int, list[Any]]]:
    """扫描全部页，提取表 btree 叶页中的 (rowid, record values)。"""
    page_count = len(data) // PAGE_SIZE
    reserved = data[20]  # 文件头 offset 20：每页保留字节数
    usable = PAGE_SIZE - reserved
    max_local = usable - 35
    min_local = ((usable - 12) * 32) // 255 - 23

    results: list[tuple[int, list[Any]]] = []
    for page_no in range(1, page_count + 1):
        start = (page_no - 1) * PAGE_SIZE
        page = data[start : start + PAGE_SIZE]
        hdr = 100 if page_no == 1 else 0
        if page[hdr] != 0x0D:  # 非表叶页（索引页/溢出页/freelist trunk 等）
            continue
        ncells = int.from_bytes(page[hdr + 3 : hdr + 5], "big")
        ptr_start = hdr + 8
        for i in range(ncells):
            cell_off = int.from_bytes(page[ptr_start + 2 * i : ptr_start + 2 * i + 2], "big")
            if cell_off < ptr_start + 2 * ncells or cell_off >= PAGE_SIZE:
                continue
            try:
                payload_len, off = read_varint(page, cell_off)
                rowid, off = read_varint(page, off)
                if payload_len <= 0 or payload_len > 10_000_000:
                    continue
                if payload_len <= max_local:
                    payload = page[off : off + payload_len]
                else:
                    local = min_local + ((payload_len - min_local) % (usable - 4))
                    if local > max_local:
                        local = min_local
                    buf = bytearray(page[off : off + local])
                    next_pg = int.from_bytes(page[off + local : off + local + 4], "big")
                    remaining = payload_len - local
                    seen: set[int] = set()
                    while next_pg and remaining > 0 and next_pg not in seen:
                        seen.add(next_pg)
                        op_start = (next_pg - 1) * PAGE_SIZE
                        op = data[op_start : op_start + PAGE_SIZE]
                        chunk = op[4 : 4 + min(remaining, usable - 4)]
                        buf.extend(chunk)
                        remaining -= len(chunk)
                        next_pg = int.from_bytes(op[:4], "big")
                    payload = bytes(buf)
                values = parse_record(payload)
                results.append((rowid, values))
            except (IndexError, struct.error):
                continue
    return results


def collect_tasks(data: bytes) -> dict[int, str]:
    """从页记录中提取并去重 task JSON，返回 task_id -> data json 文本。"""
    tasks: dict[int, str] = {}
    malformed = 0
    for _rowid, values in extract_records(data):
        if len(values) < 2 or not isinstance(values[1], str):
            continue
        text = values[1]
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(obj, dict) and "task_id" in obj and "title" in obj:
            tasks[int(obj["task_id"])] = text
        else:
            malformed += 1
    if malformed:
        print(f"[提示] 跳过无法解析/非 task 数据的 record: {malformed} 条")
    return tasks


def write_back(tasks: dict[int, str]) -> None:
    """备份原库后把恢复的 task 数据写回 cache 表（expires_at 续期 30 天）。"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DB_PATH.parent / f"{DB_PATH.name}.corrupt_{ts}"
    shutil.copyfile(DB_PATH, backup)
    print(f"已备份原库: {backup}")

    now = datetime.now()
    expires = now + timedelta(days=30)
    conn = sqlite3.connect(DB_PATH)
    try:
        for task_id, text in tasks.items():
            conn.execute(
                "INSERT OR REPLACE INTO cache (task_id, data, created_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    task_id,
                    text,
                    now.strftime("%Y-%m-%d %H:%M:%S"),
                    expires.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
    finally:
        conn.close()
    print(f"写回完成: cache 表现有 {count} 条")


def main() -> None:
    """Entry point."""
    if not DB_PATH.exists():
        raise SystemExit(f"数据库不存在: {DB_PATH}")
    data = DB_PATH.read_bytes()
    print(f"文件大小: {len(data)} 字节（{len(data) // PAGE_SIZE} 页）")

    tasks = collect_tasks(data)
    print(f"恢复到 {len(tasks)} 条 task 数据")
    for task_id in sorted(tasks)[:5]:
        title = json.loads(tasks[task_id]).get("title", "")
        print(f"  样例 task_id={task_id}: {title[:60]}")
    if not tasks:
        raise SystemExit("未恢复到任何数据，中止")

    if "--write" in sys.argv:
        write_back(tasks)
    else:
        print("dry-run 模式，未写回。确认无误后追加 --write 执行写回。")


if __name__ == "__main__":
    main()
