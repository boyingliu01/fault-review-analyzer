"""CLI 缓存路径解析的防回归测试。

回归背景：_get_cache_db_path 曾在显式 --config 加载失败时静默回退到
./data/cache/cache.db（项目真实库相对路径）；叠加测试未隔离缓存路径与
CacheManager 构造期清理副作用，全量 pytest 运行期间真实缓存库
data/cache/cache.db 中的数据被物理删除。
"""

from pathlib import Path

import pytest
import typer

from src.cli.commands.cache import _get_cache_db_path


class TestGetCacheDbPath:
    """_get_cache_db_path 的路径解析与失败语义。"""

    def test_valid_config_returns_configured_path(self, tmp_path: Path) -> None:
        """配置合法时返回配置中的缓存路径。"""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            'cache:\n  db_path: "X:/isolated/cache.db"\n',
            encoding="utf-8",
        )
        assert _get_cache_db_path(config_path) == Path("X:/isolated/cache.db")

    def test_missing_config_fails_loudly(self, tmp_path: Path) -> None:
        """显式指定的配置文件不存在时报错退出，不得静默回退真实库。"""
        missing = tmp_path / "nonexistent.yaml"
        with pytest.raises(typer.Exit):
            _get_cache_db_path(missing)

    def test_invalid_config_fails_loudly(self, tmp_path: Path) -> None:
        """配置文件解析失败时报错退出，不得静默回退真实库。"""
        bad_config = tmp_path / "broken.yaml"
        bad_config.write_text("cache: [unclosed\n", encoding="utf-8")
        with pytest.raises(typer.Exit):
            _get_cache_db_path(bad_config)

    def test_none_returns_default_path(self) -> None:
        """未指定 --config 时按 CLI 惯例返回默认路径。"""
        assert _get_cache_db_path(None) == Path("./data/cache/cache.db")
