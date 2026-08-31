# Changelog

本项目的所有重要变更将记录在本文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

### Fixed

- **fix(utils)**: `AdaptiveRateLimiter.acquire()` 改为 asyncio.Lock 锁内原子预约放行时刻 + 锁外 sleep，消除并发雷群效应；`get_running_loop()` 替代 3.12 已废弃的 `get_event_loop()`；删除 `src/embedding/generator.py` 中的旧副本，统一使用共享实现（重新导出保持测试导入兼容）。
- **fix(analyzer)**: 图片证据链路端到端贯通（`PipelineResult.image_evidence` 字段 → 赋值 → progress 持久化 → 读端生效）；图片下载 `httpx.Client` 改 `AsyncClient` + `follow_redirects`（消除事件循环阻塞与静默重定向失败）；深度根因链路复用 extractor 成员实例；恢复意外异常安全掩蔽（含敏感内容的异常详情不写入对外结果，排查走日志 `exception_type`+`task_id`）；根因推理日志 print→loguru 规范化。
- **fix(feedback)**: `recurrence_detector._parse_timestamp` 解析失败返回 `None`（不再伪造 `now()`），成功解析的 aware 时间戳统一归一化为 UTC naive 后返回，消除与 naive 值混排时 `min()/max()` 抛 `TypeError` 的崩溃风险。
- **fix(analysis)**: `weak_encryption` 弱加密检测误报修复（故障单 11964851）——旧正则缺少词头 `\b` 且全局 IGNORECASE，JS 的 `.includes()` 词尾 "des" 被误判为弱加密；改为双侧词边界 + 算法常量大小写敏感（md5/sha1 允许小写），`VIOLATION_PATTERNS` 支持 per-pattern `flags`，新增回归测试覆盖真实误报样本与真实弱加密用法。
