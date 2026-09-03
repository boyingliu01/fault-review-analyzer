# Changelog

本项目的所有重要变更将记录在本文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

### Added

- **feat(analyzer)**: pipeline 接入结论域 Delphi 复审（`AnalysisPipeline._review_conclusions_with_delphi`）——固定插入 `_analyze_with_llm` 之后、`_match_standards` 之前（REQ-5）：被撤销的复盘结论不再传导至规范匹配与改进建议（两者读 `result.root_causes`）。撤销策略（REQ-4）：refuted/insufficient_evidence 移出主列表并记入 `conclusion_review.revoked` 审计（不静默清空）、全单撤销标记 `conclusion_status="pending_rebuild"` 待人工重建（不自动重算，用户裁决）；diverged/复审失败保守保留附 `conclusion_verdict` 待人工标记。可观测（REQ-8）：存在撤销且已有深度结论时附 `deep_impact` 标注、全专家连续失败（opinions 全为 reviewer_error 前缀兜底）时附 `reviewer_error=True` 供人工甄别。`scripts/rerun_violations.py` 行为同步修正：结论空单/pending_rebuild 单据照常重算 violations（结论域与违规域互不影响）。测试 +10（全量 1579 passed）。

- **feat(analyzer)**: 结论域 Delphi 复审器落地（`src/analyzer/review/conclusion_reviewer.py` `ConclusionReviewer` + `ConclusionReviewConfig`）——复盘根因结论经双模型交叉专家复核：fact_evidence_auditor@g-deepseek-v4-flash（事实断言逐条核对证据/diff 原文）与 fix_vs_intro_discriminator@g-qwen3.8-flash（判定问题是否本次变更引入，修复性变更/按设计展示不得定性为缺陷）；verdict 语义 confirmed/refuted/insufficient_evidence/diverged。不变量：INV-1 专家级失败兜底 diverged（严禁静默撤真因）、INV-3 refuted 反证门槛（key_evidence 前 60 字符须在证据/diff 原文子串命中，反证不得锚定故障标题/描述，解析层自动降级 insufficient_evidence）、INV-4 灰度（review.conclusion_review.enabled 默认 false，批量脚本编程传参显式启用）；基类新增 per-persona 指令键回退机制（无键回退共享 base_prompt，违规域行为不变）。测试 +18（全量 1569 passed）。

- **refactor(analyzer)**: Delphi 复审机制泛化为通用基类（`src/analyzer/review/base.py` `DelphiReviewerBase`）——providers 构造/多轮循环/匿名反方意见注入/全票共识判定/两级保守兜底不变量（专家级失败→`opinion_failure_verdict` 域钩子、候选级异常→`candidate_failure_verdict` 保守保留）与 verdict JSON 解析、上下文开窗工具下沉基类；`DelphiViolationReviewer` 改为继承实现（仅保留违规域 verdict 词表/persona/prompt/材料组装/撤销应用），行为零漂移（全量 1551 passed 含既有 19 违规复审测试与 6 项新基类不变量测试），为结论域 Delphi 复审（复盘结论 confirmed/refuted 复核）提供机制复用。顺带修复 `tests/test_sprint_gate.py` 在 git hook 环境下的环境污染：pre-commit 实跑注入的 GIT_DIR/GIT_INDEX_FILE 使 tmp repo 的 git 子进程操作被重定向到外层仓库（12 项门禁行为断言误判），子进程环境剔除 GIT_* 变量修复。

- **feat(analyzer)**: Delphi 多专家违规复审引擎固化——初筛（RulesEngine + ViolationDetector）全部违规候选经多专家匿名多轮共识复审（`src/analyzer/review/delphi_reviewer.py`）：strict_rule_checker（逐字对照条款要件）与 runtime_behavior_analyst（分析真实运行行为）独立会话评审，未达共识时注入匿名反方意见进入下一轮；共识误报/证据不足撤销（宁缺毋滥）、共识违规保留附依据、轮尽分歧 diverged 保留标记待人工 + 人工终裁可叠加。配置 `AppConfig.review`（config.yaml review 段），pipeline 在初筛后自动接入，Streamlit UI 与 Markdown 报告渲染复审记录，`scripts/run_delphi_review.py` 批量复审存档。实战：5 单 6 条候选经真实 LLM 复审全部共识撤销（保留集清零），测试 +22（全量 1554 passed / 覆盖率 85.19%）。

- **feat(analysis)**: 根因链路事实纪律强化与引入单号代码变更接入——根因分析 prompt 增加事实纪律七条款（区分修复变更与引入变更、禁止臆测未读代码、结论必须逐条对应证据原文）；引入单号（introduceTaskNo）代码变更接入根因两条链路（新增 `src/analyzer/introduce_diff.py`、`src/analyzer/requirement_context.py` 与配套测试）；LLM 空响应自动重试（本地模型约 20% 空响应概率）；缓存过期清理与 CLI 缓存路径支撑。

### Fixed

- **chore(reports)**: 基于修复后数据重跑《复盘分析报告.xlsx》《复盘分析汇总.md》《复盘综合分析报告.md》，规范违规统计（18 条/12 起检出）、产品线维度（数渠 89/BSS 83/电商 9）、改进建议去重（381 条/单内零重复）与 progress 数据三方完全同步。
- **fix(analysis)**: 改进措施重复罗列修复——`ImprovementRecommender.recommend_measures()` 按 `(category, priority)` 选模板，不同根因文本（如"边界条件未处理"/"异常处理不当"）命中同一模板时产生完全相同的措施条目（181 单中 93 单单内重复，最多同一条措施重复 3 遍）。新增 `_merge_duplicate_measures()`：同类别同优先级合并为一条，`root_cause` 顿号连接保留全部根因、`rule_ids` 去重合并、`expected_impact` 保留最高频根因占比；新增 `scripts/rerun_improvements.py` 从 progress 的 root_causes/violations 离线重算（备份至 `improvements_dedupe_backup_*`，不重跑 LLM）。重算后措施 488→381 条，单内重复归零，两份报告同步重跑。
- **fix(scripts)**: `generate_client_report.py` 产品线归属改用业务复盘"责任产品线"权威映射（`scripts/extract_product_line_map.py` 从三个产品线复盘xlsx提取，`output/product_line_map.json`，181 UR：数渠 89 / BSS 83 / 电商 9，与业务口径零冲突）；标题推断降级为映射未命中时的回退（历史错误率 34%）；新增电商产品线分类（原映射不存在，被并入数字渠道）。
- **fix(rules)**: 规范违规检测四项隐含缺陷修复（A1/A2/A3/A7）——① 新增 `src/utils/diff_utils.extract_added_lines()`，规则引擎与违规检测器只检测 diff 新增行（删除行/上下文行是历史或被移除代码，混入会被误判为本次引入，见 11964851）；`code_changes` 只检测 `new_content`，不再降级检测 `old_content`。② `security-001` 正则收紧为明确凭证词（password/secret/token/api_key 等），移除裸词 `key|token`（IGNORECASE 下 cacheKey/KEY 等普通变量名大量误报，修正前 41/181 单命中），要求值长度≥6 过滤占位符；evidence 从 `re.findall` 分组元组改为完整代码行（旧证据如 `['KEY','key',...]` 无法复核）。③ `J000025 非线程安全集合` 增加 `context_pattern` 多线程上下文前置检测（无 Thread/Executor/parallelStream 等特征不报）。④ `Rule` 模型支持规则级 `flags`（默认 IGNORECASE 保持兼容），与 `violation_detector` 的 per-pattern flags 机制对齐。修复后重算 181 单：违规 2→18 条（security-001×6、SEC-J00033×6、J000025×4、J000066×1、SEC-J00002×1），新增 `scripts/rerun_violations.py`（备份后仅重算 violations 字段，不重跑 LLM）。后续人工逐条复核 + Delphi 多专家复审双重确认：敏感信息类 12 条（security-001）及残留 6 条命中（J000025×4/J000066×1/SEC-J00002×1）全部为误报，撤销依据存档于各 progress 的 `violation_review`/`delphi_review` 审计记录。
- **fix(utils)**: `AdaptiveRateLimiter.acquire()` 改为 asyncio.Lock 锁内原子预约放行时刻 + 锁外 sleep，消除并发雷群效应；`get_running_loop()` 替代 3.12 已废弃的 `get_event_loop()`；删除 `src/embedding/generator.py` 中的旧副本，统一使用共享实现（重新导出保持测试导入兼容）。
- **fix(analyzer)**: 图片证据链路端到端贯通（`PipelineResult.image_evidence` 字段 → 赋值 → progress 持久化 → 读端生效）；图片下载 `httpx.Client` 改 `AsyncClient` + `follow_redirects`（消除事件循环阻塞与静默重定向失败）；深度根因链路复用 extractor 成员实例；恢复意外异常安全掩蔽（含敏感内容的异常详情不写入对外结果，排查走日志 `exception_type`+`task_id`）；根因推理日志 print→loguru 规范化。
- **fix(feedback)**: `recurrence_detector._parse_timestamp` 解析失败返回 `None`（不再伪造 `now()`），成功解析的 aware 时间戳统一归一化为 UTC naive 后返回，消除与 naive 值混排时 `min()/max()` 抛 `TypeError` 的崩溃风险。
- **fix(analysis)**: `weak_encryption` 弱加密检测误报修复（故障单 11964851）——旧正则缺少词头 `\b` 且全局 IGNORECASE，JS 的 `.includes()` 词尾 "des" 被误判为弱加密；改为双侧词边界 + 算法常量大小写敏感（md5/sha1 允许小写），`VIOLATION_PATTERNS` 支持 per-pattern `flags`，新增回归测试覆盖真实误报样本与真实弱加密用法。
- **fix(scripts)**: `reanalyze_with_images.py` 覆盖生产 progress json 前自动备份至 `output/reanalysis_backup/`（低质量重分析可随时恢复）；`run_all_parallel.py` 的 `_to_record` 补写 `image_evidence` 字段，打通图片证据到 progress 数据的持久化。
- **chore(architecture)**: `architecture.yaml` 清理 ChromaDB 移除后的悬空 `src/storage` 引用（cli/ui），feedback 层依赖修正为 core/utils/config、knowledge 层收窄为 core，消除重复层定义；CLAUDE.md/AGENTS.md 文档同步对齐；Delphi 三轮走查共识记录入库。
