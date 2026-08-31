"""ImageEvidenceExtractor 单元测试。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.analyzer.image_evidence import (
    ImageEvidenceExtractor,
    extract_image_refs,
    resolve_url,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

DESC_WITH_IMAGES = """### 重现步骤：
![image.png](${tenantCosEndpoint}/cos-devspace/task/default_add/1330f133-b86f-485c-91db-0b67dcdc1197/image.png)
![image.png](${tenantCosEndpoint}/cos-devspace/task/default_add/07ff0b5d-fd01-4be1-abee-f8ea5304a148/image.png)
"""

DESC_NO_IMAGES = "### 重现步骤：\n输入参数后报错，无图片。"


def test_extract_image_refs_placeholder() -> None:
    refs = extract_image_refs(DESC_WITH_IMAGES)
    assert len(refs) == 2
    assert refs[0] == (
        "default_add",
        "1330f133-b86f-485c-91db-0b67dcdc1197",
        "image.png",
    )


def test_extract_image_refs_none() -> None:
    assert extract_image_refs(DESC_NO_IMAGES) == []
    assert extract_image_refs("") == []


def test_extract_image_refs_resolved_url() -> None:
    """已解析的 https://dev.iwhalecloud.com URL 也应被识别。"""
    desc = "![image.png](https://dev.iwhalecloud.com/cos-devspace/task/default_add/abc-1/photo.jpg)"
    refs = extract_image_refs(desc)
    assert refs == [("default_add", "abc-1", "photo.jpg")]


def test_resolve_url() -> None:
    url = resolve_url("default_add", "abc-123", "image.png")
    assert url == ("https://dev.iwhalecloud.com/cos-devspace/task/default_add/abc-123/image.png")


def test_no_images_returns_empty(tmp_path: Path) -> None:
    ext = ImageEvidenceExtractor(out_dir=tmp_path)
    result = asyncio_run(ext.get_image_evidence({"urId": 1, "description": DESC_NO_IMAGES}))
    assert result == ""


def test_cached_evidence_reused(tmp_path: Path) -> None:
    """有缓存时直接返回，不触发下载/读图。"""
    ext = ImageEvidenceExtractor(out_dir=tmp_path)
    # 预置缓存
    urid_dir = tmp_path / "123"
    urid_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "urId": 123,
        "title": "t",
        "image_evidence": [{"image": "image_1.png", "content": "缓存证据内容"}],
        "real_root_cause": "",
    }
    (urid_dir / "image_evidence.json").write_text(
        __import__("json").dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    result = asyncio_run(ext.get_image_evidence({"urId": 123, "description": DESC_WITH_IMAGES}))
    assert "缓存证据内容" in result


def test_failed_download_returns_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """图片下载全部失败时返回空，不崩溃。"""
    ext = ImageEvidenceExtractor(out_dir=tmp_path)

    async def _fake_download(_urid: int, _desc: str) -> list[Path]:
        return []

    monkeypatch.setattr(ext, "download_images", _fake_download)
    result = asyncio_run(ext.get_image_evidence({"urId": 999, "description": DESC_WITH_IMAGES}))
    assert result == ""


def test_extractor_importable() -> None:
    assert callable(ImageEvidenceExtractor)


def asyncio_run(coro):
    """运行协程的辅助函数。"""
    import asyncio

    return asyncio.run(coro)
