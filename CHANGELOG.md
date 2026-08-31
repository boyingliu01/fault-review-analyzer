# Changelog

本项目的所有重要变更将记录在本文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

### Fixed

- **fix(utils)**: `AdaptiveRateLimiter.acquire()` 改为 asyncio.Lock 锁内原子预约放行时刻 + 锁外 sleep，消除并发雷群效应；`get_running_loop()` 替代 3.12 已废弃的 `get_event_loop()`；删除 `src/embedding/generator.py` 中的旧副本，统一使用共享实现（重新导出保持测试导入兼容）。
