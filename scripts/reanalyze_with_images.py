#!/usr/bin/env python
"""基于图片证据重新生成故障复盘分析。

背景:
    之前部分故障单的 description 中图片 URL 是 ${tenantCosEndpoint} 占位符，
    导致 LLM 读不到图片、只能基于残缺文本做分析，常得出"信息不足/无法定位"的结论。

    现已确认 ${tenantCosEndpoint} = https://dev.iwhalecloud.com，图片可公开下载，
    并用视觉 LLM 提取了图片内容（output/cos_images/<urId>/image_evidence.json）。

本脚本读取 image_evidence.json，把"原始描述 + 图片证据文本"一起交给 LLM，
重新生成 root_causes / improvements / labels，并更新 output/progress_<urId>.json。

用法:
    python scripts/reanalyze_with_images.py <urId> [urId ...]
    python scripts/reanalyze_with_images.py all        # 处理所有含图片证据的单子

输出:
    更新 output/progress_<urId>.json（保留原始字段，仅替换分析字段）
    追加 output/reanalysis_<timestamp>.json（本次重分析的批量汇总）
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer.llm_provider import OpenAILLMProvider, create_llm_provider
from src.config.manager import ConfigManager

OUT_DIR = Path(__file__).parent.parent / "output"
COS_DIR = OUT_DIR / "cos_images"

REANALYSIS_PROMPT = """你是研发泄漏缺陷复盘分析专家。请基于【故障单原始描述】和【故障单图片证据】（截图提取的文字内容），重新进行根因分析。

之前因图片无法访问，分析结论常是"信息不足/无法定位"。现在图片证据已补充，请给出准确、可落地的根因分析。

【故障单标题】
{title}

【故障单原始描述】
{description}

【故障单图片证据】
{image_evidence}

【是否有代码变更】{has_code_change}

请严格按以下 JSON 格式输出（不要输出任何其他内容、不要用markdown代码块包裹）：

{{
  "root_causes": [
    {{
      "cause_type": "根因类型，如 编码错误/设计缺陷/需求理解偏差/测试遗漏/配置错误/状态机异常 等",
      "description": "基于图片证据的详细根因描述，明确指出故障的技术原因",
      "evidence": ["证据1", "证据2", "证据3"],
      "confidence": 0.0-1.0
    }}
  ],
  "improvements": [
    {{
      "root_cause": "对应根因类型",
      "measure": "具体改进措施",
      "acceptance_criteria": "验收标准",
      "expected_impact": "预期影响",
      "priority": "high/medium/low",
      "category": "需求类/代码类/设计类/测试类/运维类 等",
      "rule_ids": []
    }}
  ],
  "labels": [
    {{
      "name": "标签名",
      "confidence": 0.0-1.0,
      "category": "故障来源/根因类型 等",
      "description": "标签说明"
    }}
  ]
}}

要求：
- root_causes 给 2-4 条，基于图片证据给出准确技术根因，不要再说"信息不足/无法定位"
- evidence 必须是图片证据中实际出现的内容
- improvements 给 2-5 条，与根因对应
- 严格输出合法 JSON
"""


def _load_image_evidence(urid: int) -> str:
    """读取单子的图片证据文本，合并为一段。"""
    ev_file = COS_DIR / str(urid) / "image_evidence.json"
    if not ev_file.exists():
        return ""
    try:
        data = json.loads(ev_file.read_text(encoding="utf-8"))
    except Exception:
        return ""
    parts: list[str] = []
    for img in data.get("image_evidence", []):
        parts.append(f"[图片 {img.get('image','')}] {img.get('content','')}")
    rc = data.get("real_root_cause", "")
    if rc:
        parts.append(f"[综合判断] {rc}")
    return "\n".join(parts)


def _parse_llm_json(text: str) -> dict[str, Any]:
    """解析 LLM 返回的 JSON（容忍 markdown 代码块包裹）。"""
    t = text.strip()
    if t.startswith("```"):
        # 去掉代码块围栏
        lines = t.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines)
    data = json.loads(t)
    if not isinstance(data, dict):
        raise ValueError(f"LLM 返回的 JSON 不是对象: {type(data).__name__}")
    return data


def _merge_record(original: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """保留原始字段，仅替换分析字段（root_causes/improvements/labels）。"""
    merged = dict(original)
    for key in ("root_causes", "improvements", "labels"):
        if key in new:
            merged[key] = new[key]
    # 记录重分析来源
    merged["reanalyzed_with_images"] = True
    merged["reanalysis_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return merged


async def reanalyze_one(urid: int, provider: OpenAILLMProvider) -> dict[str, Any] | None:
    """重分析单个单子，返回更新后的记录。"""
    progress_file = OUT_DIR / f"progress_{urid}.json"
    if not progress_file.exists():
        print(f"[{urid}] progress 文件不存在，跳过")
        return None

    evidence = _load_image_evidence(urid)
    if not evidence:
        print(f"[{urid}] 无图片证据，跳过")
        return None

    try:
        rec = json.loads(progress_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[{urid}] 读取失败: {e}")
        return None

    prompt = REANALYSIS_PROMPT.format(
        title=rec.get("title", ""),
        description=rec.get("description", ""),
        image_evidence=evidence,
        has_code_change=rec.get("has_code_change", False),
    )

    try:
        response = await provider.generate(
            system="你只输出合法 JSON，不输出其他内容。",
            user=prompt,
        )
    except Exception as e:
        print(f"[{urid}] LLM 调用失败: {e}")
        return None

    if not response.strip():
        print(f"[{urid}] LLM 返回空")
        return None

    try:
        new = _parse_llm_json(response)
    except Exception as e:
        print(f"[{urid}] JSON 解析失败: {e}\n响应片段: {response[:200]}")
        return None

    merged = _merge_record(rec, new)
    # 覆盖前备份当前记录到 output/reanalysis_backup/，
    # 保留重分析前的原始分析结果，低质量重分析可随时恢复
    backup_dir = OUT_DIR / "reanalysis_backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / (
        f"progress_{urid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    shutil.copyfile(progress_file, backup)
    progress_file.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"[{urid}] ✓ 已更新: 根因{len(merged.get('root_causes', []))} "
        f"改进{len(merged.get('improvements', []))} 标签{len(merged.get('labels', []))}"
    )
    return merged


async def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("用法: python scripts/reanalyze_with_images.py <urId> [urId ...] | all")
        return

    config_manager = ConfigManager()
    config = config_manager.load()
    provider = create_llm_provider(config.llm)
    if provider is None:
        print("LLM 未配置，退出")
        return

    if args == ["all"]:
        urids = []
        for fp in sorted(OUT_DIR.glob("progress_*.json")):
            try:
                rec = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            if rec.get("urId") and _load_image_evidence(rec["urId"]):
                urids.append(rec["urId"])
    else:
        urids = [int(x) for x in args]

    print(f"开始重分析 {len(urids)} 个单子...")
    start = time.time()
    updated: list[dict[str, Any]] = []
    try:
        for urid in urids:
            rec = await reanalyze_one(urid, provider)
            if rec:
                updated.append(rec)
    finally:
        await provider.close()

    # 批量汇总
    if updated:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = OUT_DIR / f"reanalysis_{ts}.json"
        out_file.write_text(
            json.dumps({"results": updated, "elapsed_sec": time.time() - start}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n完成 {len(updated)} 起，耗时 {time.time()-start:.0f}s，汇总: {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
