#!/usr/bin/env python
"""解析故障单描述中的 ${tenantCosEndpoint} 占位符图片 URL 并下载。

背景:
    研发云任务单 API 返回的 comments(描述) 中，图片 URL 是前端占位符形式:
        ${tenantCosEndpoint}/cos-devspace/task/default_add/<uuid>/<file>
    之前因占位符无法解析，导致图片读取不到、无法做详细复盘。

关键发现:
    ${tenantCosEndpoint} 的真实值 = https://dev.iwhalecloud.com
    (依据: progress_11899403.json 中发现的已解析 URL)

    图片公开可访问，无需 token。

用法:
    python scripts/resolve_cos_images.py [--urid 11757373 11757372 ...] [--out-dir output/cos_images]
        --urid     可选，指定要处理的单子 urId；缺省处理所有含占位符图片的单子
        --out-dir  图片下载目录 (默认 output/cos_images)
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import requests

COS_ENDPOINT = "https://dev.iwhalecloud.com"
_PLACEHOLDER_RE = re.compile(
    r"(?:\$\{tenantCosEndpoint\}|https://dev\.iwhalecloud\.com)"
    r"/cos-devspace/task/([^/\s]+)/([^/\s]+)/([^)\s]+)"
)
_OUT_DIR = Path(__file__).parent.parent / "output"


def extract_image_refs(description: str) -> list[tuple[str, str, str]]:
    """从描述中提取 (taskpath, uuid, filename) 图片引用列表。"""
    return [(tp, uuid, fname) for tp, uuid, fname in _PLACEHOLDER_RE.findall(description)]


def resolve_url(taskpath: str, uuid: str, filename: str) -> str:
    """把图片引用解析为真实可访问 URL。"""
    return f"{COS_ENDPOINT}/cos-devspace/task/{taskpath}/{uuid}/{filename}"


def download_images(
    urids: list[int], out_dir: Path, timeout: int = 30, workers: int = 8
) -> dict[int, list[dict]]:
    """批量下载指定单子的占位符图片（并发 + 断点续传）。

    返回: {urId: [{"url", "path", "status", "content_type", "size"}]}
    """
    from concurrent.futures import ThreadPoolExecutor

    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[int, list[dict]] = {}

    # 收集所有待下载任务
    tasks: list[tuple[int, str, str, Path]] = []  # (urid, url, dest_name, dest)
    for urid in urids:
        fp = _OUT_DIR / f"progress_{urid}.json"
        if not fp.exists():
            print(f"[{urid}] progress 文件不存在，跳过")
            continue
        try:
            rec = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[{urid}] 读取失败: {e}")
            continue

        refs = extract_image_refs(rec.get("description", ""))
        if not refs:
            print(f"[{urid}] 无占位符图片")
            continue

        urid_dir = out_dir / str(urid)
        urid_dir.mkdir(parents=True, exist_ok=True)
        results[urid] = []

        for i, (taskpath, uuid, fname) in enumerate(refs, 1):
            url = resolve_url(taskpath, uuid, fname)
            ext = Path(fname).suffix or ".img"
            dest = urid_dir / f"image_{i}{ext}"
            # 断点续传：已存在且非空则跳过
            if dest.exists() and dest.stat().st_size > 0:
                print(f"[{urid}] = 已存在 {dest.name}，跳过")
                results[urid].append(
                    {"url": url, "path": str(dest), "status": 200, "size": dest.stat().st_size, "cached": True}
                )
                continue
            tasks.append((urid, url, dest.name, dest))

    def _download(task: tuple[int, str, str, Path]) -> tuple[int, dict]:
        urid, url, name, dest = task
        entry: dict[str, Any] = {"url": url, "path": str(dest)}
        try:
            r = requests.get(url, timeout=timeout)
            entry["status"] = r.status_code
            entry["content_type"] = r.headers.get("Content-Type", "")
            if r.status_code == 200:
                dest.write_bytes(r.content)
                entry["size"] = len(r.content)
                print(f"[{urid}] ✓ {name} ({len(r.content)}B)")
            else:
                entry["size"] = 0
                print(f"[{urid}] ✗ HTTP {r.status_code} {url[:90]}")
        except Exception as e:
            entry["status"] = "error"
            entry["size"] = 0
            print(f"[{urid}] ✗ 错误 {str(e)[:60]} {url[:90]}")
        return urid, entry

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for urid, entry in pool.map(_download, tasks):
            results.setdefault(urid, []).append(entry)

    # 写清单
    for urid, entries in results.items():
        (out_dir / str(urid) / "manifest.json").write_text(
            json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="解析并下载 ${tenantCosEndpoint} 占位符图片")
    parser.add_argument("--urid", nargs="*", type=int, help="指定 urId；缺省处理所有含占位符图片的单子")
    parser.add_argument("--out-dir", default=str(_OUT_DIR / "cos_images"), help="图片下载目录")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)

    if args.urid:
        urids = args.urid
    else:
        urids = []
        for fp in sorted(_OUT_DIR.glob("progress_*.json")):
            try:
                rec = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            if rec.get("urId") and extract_image_refs(rec.get("description", "")):
                urids.append(rec["urId"])

    print(f"处理 {len(urids)} 个含占位符图片的单子，输出目录: {out_dir}")
    results = download_images(urids, out_dir)

    total = sum(len(v) for v in results.values())
    ok = sum(1 for v in results.values() for e in v if e.get("status") == 200)
    print(f"\n完成: 下载 {ok}/{total} 张图片")


if __name__ == "__main__":
    main()
