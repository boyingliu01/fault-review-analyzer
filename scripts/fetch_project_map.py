#!/usr/bin/env python
"""从研发云 detail API 补齐每个故障单的项目归属信息。

由于 TaskInfo 模型未保留 projectId 等字段，本脚本对全部 progress 单子
逐个调用 detail 接口，提取 (urId, taskId, projectId, zmpProjectId,
productModuleId, productVersionId) 并写入 output/urid_project_map.json，
供产品线维度统计使用（一次抓取，长期复用；--force 强制重抓）。
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

OUT_DIR = Path(__file__).parent.parent / "output"
MAP_FILE = OUT_DIR / "urid_project_map.json"

BASE_URL = "https://dev.iwhalecloud.com"
DETAIL_API = "/portal/ai-gateway/devspace/rpc/v3/work-item/{tid}/detail"
FIELDS = ["projectId", "zmpProjectId", "productModuleId", "productVersionId"]


async def fetch_one(
    client: Any, headers: dict[str, str], urid: int, sem: asyncio.Semaphore
) -> dict[str, Any] | None:
    async with sem:
        for _ in range(3):
            try:
                r = await client.post(
                    f"{BASE_URL}{DETAIL_API.format(tid=urid)}",
                    json={},
                    headers=headers,
                    timeout=60,
                )
                body = r.json()
                if body.get("code") not in (None, "9999") and not body.get("data"):
                    return None
                task = (body.get("data") or {}).get("apiTask") or {}
                if not task:
                    return None
                entry = {"taskId": task.get("taskNo") or task.get("taskId")}
                for f in FIELDS:
                    entry[f] = task.get(f)
                return entry
            except Exception:
                await asyncio.sleep(1.5)
        return None


async def main(force: bool) -> None:
    from src.api.client import APIClient  # noqa: F401  复用既有鉴权配置读取

    load_dotenv(dotenv_path=".env", override=True)
    token = os.getenv("DEVCLOUD_TOKEN", "")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": token if token.startswith("Bearer ") else f"Bearer {token}",
    }

    urids: list[int] = []
    for fp in sorted(OUT_DIR.glob("progress_*.json")):
        try:
            rec = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if rec.get("urId"):
            urids.append(int(rec["urId"]))

    existing: dict[str, dict] = {}
    if MAP_FILE.exists() and not force:
        existing = json.loads(MAP_FILE.read_text(encoding="utf-8"))

    todo = [u for u in urids if str(u) not in existing]
    print(f"总数 {len(urids)}，已缓存 {len(urids) - len(todo)}，待抓取 {len(todo)}")
    if todo:
        import httpx

        sem = asyncio.Semaphore(5)
        got = 0
        async with httpx.AsyncClient() as client:
            BATCH = 40
            for i in range(0, len(todo), BATCH):
                chunk = todo[i : i + BATCH]
                results = await asyncio.gather(*[fetch_one(client, headers, u, sem) for u in chunk])
                for u, entry in zip(chunk, results, strict=True):
                    if entry:
                        existing[str(u)] = entry
                        got += 1
                print(f"进度 {min(i + BATCH, len(todo))}/{len(todo)}（成功累计 {got}）")

        tmp = MAP_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(MAP_FILE)

    ok = sum(1 for v in existing.values() if v)
    print(f"完成: map 共 {len(existing)} 条（含数据 {ok} 条），输出 {MAP_FILE}")


def main_entry() -> None:
    force = "--force" in sys.argv
    asyncio.run(main(force))


if __name__ == "__main__":
    main_entry()
