"""图片证据提取模块 - 把故障单描述中的 ${tenantCosEndpoint} 占位符图片解析、下载，并用视觉 LLM 读取内容。

背景:
    研发云故障单 API 返回的 comments(描述) 中，图片 URL 是前端占位符形式:
        ${tenantCosEndpoint}/cos-devspace/task/default_add/<uuid>/<file>
    之前因占位符无法解析，LLM 分析时读不到图片，常得出"信息不足/无法定位"的结论。

    已确认 ${tenantCosEndpoint} 的真实值 = https://dev.iwhalecloud.com，图片公开可访问(无需 token)。
    本模块把"图片下载 + 视觉读图 + 证据缓存"集成为可复用能力，
    供 AnalysisPipeline 在单起复盘时自动调用。

用法:
    from src.analyzer.image_evidence import ImageEvidenceExtractor
    extractor = ImageEvidenceExtractor()
    evidence = await extractor.get_image_evidence(task_data)  # -> 证据文本 或 ""
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from loguru import logger

COS_ENDPOINT = "https://dev.iwhalecloud.com"
# 匹配占位符(${tenantCosEndpoint})或已解析(dev.iwhalecloud.com)的 cos-devspace 图片引用
# 捕获 (uuid, filename)，支持 task/default_add/... 或 task/<id>/... 路径
_PLACEHOLDER_RE = re.compile(
    r"(?:\$\{tenantCosEndpoint\}|https://dev\.iwhalecloud\.com)"
    r"/cos-devspace/task/([^/\s]+)/([^/\s]+)/([^)\s]+)"
)
# 默认输出目录: <repo>/output/cos_images
_OUT_DIR = Path(__file__).parent.parent.parent / "output" / "cos_images"

# 视觉读图 prompt（结构化 schema，便于机器消费与跨单去重）
_VISION_PROMPT = """你是多模态图像分析专家。请仔细分析这张研发云故障单截图，严格按以下分节输出提取结果。

【图片类型】接口报错截图 / 界面操作截图 / 数据表格 / IM群聊记录 / 设计文档 / 其他

【错误码与报错】图中出现的所有错误码、resultCode、resultMsg、HTTP状态码、异常堆栈（原样照抄，没有则写"无"）

【接口信息】请求方法+URL、请求参数名/值、响应字段/值（原样照抄，没有则写"无"）

【界面要点】页面名称、关键字段值、表单状态、按钮位置、被红框/箭头标注的区域及其含义

【故障线索】基于以上内容，图中体现的与故障原因直接相关的关键信息（1-3条）

要求：只提取图中实际存在的信息，不要编造；错误码和参数必须逐字准确。"""


def extract_image_refs(description: str) -> list[tuple[str, str, str]]:
    """从描述中提取 (taskpath, uuid, filename) 图片引用列表。

    taskpath 为 cos-devspace/task/ 下的子路径段（如 default_add 或任务号）。
    """
    return [(tp, uuid, fname) for tp, uuid, fname in _PLACEHOLDER_RE.findall(description or "")]


def resolve_url(taskpath: str, uuid: str, filename: str) -> str:
    """把图片引用解析为真实可访问 URL。"""
    return f"{COS_ENDPOINT}/cos-devspace/task/{taskpath}/{uuid}/{filename}"


class ImageEvidenceExtractor:
    """下载故障单占位符图片并用视觉 LLM 提取证据文本。

    设计:
        - 缓存: 图片下载到 <out_dir>/<urId>/，读图结果缓存到 image_evidence.json。
          已有缓存则直接复用，不重复下载/读图。
        - 失败降级: 图片下载或视觉读图失败时返回空字符串，不影响主分析流程。
        - 可注入视觉 provider，便于测试。
    """

    def __init__(
        self,
        out_dir: Path | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        vision_model: str = "local-qwen3.8-27b",
        timeout: int = 60,
    ) -> None:
        """初始化。

        Args:
            out_dir: 图片/证据缓存目录（默认 output/cos_images）。
            api_key: 视觉 LLM API key（默认从配置读取）。
            base_url: 视觉 LLM base_url（默认从配置读取）。
            vision_model: 视觉模型名。
            timeout: 下载/读图超时秒数。
        """
        self._out_dir = out_dir or _OUT_DIR
        self._api_key = api_key
        self._base_url = base_url
        self._vision_model = vision_model
        self._timeout = timeout

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------
    def _load_llm_config(self) -> tuple[str, str]:
        """从 ConfigManager 读取 LLM 配置（视觉模型走同一 whalecloud 代理）。"""
        if self._api_key and self._base_url:
            return self._api_key, self._base_url
        from src.config.manager import ConfigManager

        config = ConfigManager().load().llm
        return config.api_key, config.base_url

    # ------------------------------------------------------------------
    # 图片下载
    # ------------------------------------------------------------------
    async def download_images(self, urid: int, description: str) -> list[Path]:
        """下载单子的占位符图片，返回已存在的图片路径列表（断点续传）。

        图片保存为 <out_dir>/<urid>/image_<i><ext>。
        """
        import httpx

        refs = extract_image_refs(description)
        if not refs:
            return []

        urid_dir = self._out_dir / str(urid)
        urid_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []

        for i, (taskpath, uuid, fname) in enumerate(refs, 1):
            url = resolve_url(taskpath, uuid, fname)
            ext = Path(fname).suffix or ".img"
            dest = urid_dir / f"image_{i}{ext}"
            # 断点续传：已存在且非空则跳过
            if dest.exists() and dest.stat().st_size > 0:
                paths.append(dest)
                continue
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    r = client.get(url)
                if r.status_code == 200 and r.content:
                    dest.write_bytes(r.content)
                    paths.append(dest)
                else:
                    logger.warning("[图片证据] {urid} 图片下载失败 HTTP {status}", urid=urid, status=r.status_code)
            except Exception as e:
                logger.warning("[图片证据] {urid} 图片下载异常: {err}", urid=urid, err=str(e)[:80])
        return paths

    # ------------------------------------------------------------------
    # 视觉读图
    # ------------------------------------------------------------------
    async def _vision_read(self, image_path: Path) -> str:
        """调用视觉 LLM 读取单张图片，返回提取文本。失败返回空串。"""
        try:
            from openai import AsyncOpenAI

            api_key, base_url = self._load_llm_config()
            if not api_key:
                return ""

            b64 = base64.b64encode(image_path.read_bytes()).decode()
            suffix = image_path.suffix.lstrip(".").lower() or "png"
            data_url = f"data:image/{suffix};base64,{b64}"

            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            try:
                response = await client.chat.completions.create(
                    model=self._vision_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": _VISION_PROMPT},
                                {"type": "image_url", "image_url": {"url": data_url}},
                            ],
                        }
                    ],
                    max_tokens=2000,
                )
                return response.choices[0].message.content or ""
            finally:
                await client.close()
        except Exception as e:
            logger.warning("[图片证据] 视觉读图失败 {path}: {err}", path=image_path.name, err=str(e)[:80])
            return ""

    # ------------------------------------------------------------------
    # 证据组装与缓存
    # ------------------------------------------------------------------
    def _evidence_cache_path(self, urid: int) -> Path:
        return self._out_dir / str(urid) / "image_evidence.json"

    @staticmethod
    def _description_hash(description: str) -> str:
        """描述内容的 hash，用于缓存失效判断（任务单后续补图/改描述时重新提取）。"""
        import hashlib

        return hashlib.sha256((description or "").encode("utf-8")).hexdigest()[:16]

    def _load_cached_evidence(self, urid: int, description_hash: str) -> str:
        """读取已缓存的证据文本；存在且描述未变更则返回，否则空串（触发重提取）。"""
        fp = self._evidence_cache_path(urid)
        if not fp.exists():
            return ""
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            return ""
        # 描述 hash 不一致 → 缓存陈旧（任务单后来补传/修改了内容），失效
        cached_hash = data.get("description_hash", "")
        if cached_hash and cached_hash != description_hash:
            logger.info(
                "[图片证据] {urid} 描述已变更({old}→{new})，缓存失效",
                urid=urid,
                old=cached_hash,
                new=description_hash,
            )
            return ""
        # 组装证据文本
        parts: list[str] = []
        for img in data.get("image_evidence", []):
            content = img.get("content", "")
            if content:
                parts.append(f"[图片 {img.get('image', '')}] {content}")
        rc = data.get("real_root_cause", "")
        if rc:
            parts.append(f"[综合判断] {rc}")
        return "\n".join(parts)

    def _save_evidence(self, urid: int, payload: dict[str, Any]) -> None:
        fp = self._evidence_cache_path(urid)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    async def get_image_evidence(
        self, task_data: dict[str, Any]
    ) -> str:
        """获取单起故障的图片证据文本。

        若已有有效缓存（描述未变更）则直接返回；否则下载图片 + 视觉读图 + 缓存。
        无占位符图片或失败时返回空串。

        Args:
            task_data: 任务数据 dict（含 description / title / urId 等）。

        Returns:
            图片证据文本（多行），无则空串。
        """
        urid = task_data.get("urId") or task_data.get("task_id") or task_data.get("taskId")
        description = task_data.get("description", "")
        title = task_data.get("title", "")

        if urid is None:
            return ""

        desc_hash = self._description_hash(description)

        # 1. 已有有效缓存 → 直接返回
        cached = self._load_cached_evidence(int(urid), desc_hash)
        if cached:
            return cached

        # 2. 无占位符图片 → 返回空
        refs = extract_image_refs(description)
        if not refs:
            return ""

        # 3. 下载图片
        image_paths = await self.download_images(int(urid), description)
        if not image_paths:
            return ""

        # 4. 视觉读图
        evidence_list: list[dict[str, str]] = []
        for path in image_paths:
            text = await self._vision_read(path)
            if text:
                evidence_list.append(
                    {"image": path.name, "type": "", "content": text, "clue": ""}
                )

        if not evidence_list:
            return ""

        # 5. 缓存（含描述 hash，供后续失效判断）
        payload = {
            "urId": int(urid),
            "title": title,
            "description_hash": desc_hash,
            "image_evidence": evidence_list,
            "real_root_cause": "",
        }
        self._save_evidence(int(urid), payload)

        # 组装返回
        return "\n".join(f"[图片 {e['image']}] {e['content']}" for e in evidence_list)
