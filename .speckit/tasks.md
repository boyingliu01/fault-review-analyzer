# Task List

## Feature
故障复盘分析系统 - 核心流水线 + Scope Expansions

## Overview
按照 SDD 流程分解实现任务，遵循 TDD 开发模式，确保测试覆盖率 ≥ 79.9%。
本任务列表整合了 GSTACK CEO 审查批准的 26 项改进。

## Task Breakdown

### Phase 0: Architecture & Security Fixes (P0 - Critical)
**Estimated Time**: 8 hours
**Source**: GSTACK CEO Review - Architecture + Security

#### Task 0.1: 统一 ClusteringResult 模型
- [x] 删除 `src/analysis/clustering.py` 中的 `ClusteringAnalysisResult`
- [x] 更新所有引用使用 `src/clustering/models.py` 中的 `ClusterResult`
- [x] 更新相关测试
- **Dependencies**: 无
- **Deliverables**: 单一 ClusteringResult 模型，无重复定义
- **Estimated**: 1 hour
- **Priority**: P0
- **Status**: ✅ Completed (2026-03-30)

#### Task 0.2: 添加 Circuit Breaker 模式
- [x] 创建 `src/utils/circuit_breaker.py` 断路器实现
- [x] 为 APIClient 添加断路器保护
- [x] 为 EmbeddingGenerator 添加断路器保护
- [x] 编写单元测试
- **Dependencies**: 无
- **Deliverables**: 外部 API 调用具备断路器保护
- **Estimated**: 2 hours
- **Priority**: P0
- **Status**: ✅ Completed (2026-03-30)

#### Task 0.3: ChromaDB 容错机制
- [ ] 添加 ChromaDB 连接重试逻辑
- [ ] 实现本地文件备份机制
- [ ] 添加优雅降级（写入失败时缓存到本地）
- **Dependencies**: 无
- **Deliverables**: ChromaDB 具备容错能力
- **Estimated**: 2 hours
- **Priority**: P0

#### Task 0.4: 安全改进 - Token 管理
- [ ] 添加 Token 过期检测
- [ ] 实现 Token 轮换告警机制
- [ ] 添加 taskNo 输入格式验证（数字 + 长度范围）
- [ ] 创建 `src/security/input_validator.py`
- **Dependencies**: 无
- **Deliverables**: Token 轮换机制，输入验证
- **Estimated**: 2 hours
- **Priority**: P0

#### Task 0.5: Prompt 注入防护
- [ ] 创建 `src/security/prompt_guard.py`
- [ ] 对 LLM 输入文本进行清洗
- [ ] 检测并阻止注入模式
- [ ] 添加单元测试
- **Dependencies**: 无
- **Deliverables**: Prompt 注入防护机制
- **Estimated**: 1 hour
- **Priority**: P0

### Phase 1: Foundation
**Estimated Time**: 4 hours

#### Task 1.1: 数据模型完善
- [ ] 检查并补全 `src/core/models.py` 数据模型定义
- [ ] 确保所有 Pydantic 模型有完整类型注解
- [ ] 添加模型验证逻辑
- **Dependencies**: Task 0.1
- **Deliverables**: 数据模型定义完整，类型检查通过
- **Estimated**: 1 hour
- **Priority**: P0

#### Task 1.2: 配置管理优化
- [ ] 检查 `src/config/manager.py` 配置加载逻辑
- [ ] 确保环境变量覆盖 YAML 配置
- [ ] 添加配置验证和默认值处理
- **Dependencies**: Task 1.1
- **Deliverables**: 配置管理稳定，支持多 Provider 配置
- **Estimated**: 2 hours
- **Priority**: P0

#### Task 1.3: 测试框架完善
- [ ] 检查 pytest 配置
- [ ] 确保覆盖率阈值配置正确（≥79.9%）
- [ ] 添加测试 fixtures 共享配置
- **Dependencies**: 无
- **Deliverables**: 测试框架可运行，覆盖率统计正确
- **Estimated**: 1 hour
- **Priority**: P2

### Phase 2: Core Functionality
**Estimated Time**: 16 hours (原 12h + 4h 改进)

#### Task 2.1: APIClient 优化
- [ ] 检查 `src/api/client.py` 异步实现
- [ ] 确认认证处理正确（DEVCLOUD_TOKEN）
- [ ] 测试所有 API 接口调用
- [ ] 编写单元测试（覆盖率 ≥ 80%）
- [ ] **[NEW]** 添加 datetime 解析 fallback 处理
- **Dependencies**: Task 1.1, Task 1.2, Task 0.2
- **Deliverables**: APIClient 稳定可用，测试通过
- **Estimated**: 3 hours
- **Priority**: P0

#### Task 2.2: CacheManager 验证
- [ ] 检查 `src/cache/manager.py` 缓存逻辑
- [ ] 测试 TTL 过期机制
- [ ] 测试缓存读写性能
- **Dependencies**: Task 1.1
- **Deliverables**: 缓存机制稳定
- **Estimated**: 1 hour
- **Priority**: P1

#### Task 2.3: Preprocessor 文本处理
- [ ] 检查 `src/preprocessor/` 文本预处理逻辑
- [ ] 测试关键字段提取
- [ ] 测试分析文本组合策略
- [ ] 编写单元测试
- **Dependencies**: Task 1.1
- **Deliverables**: 预处理逻辑正确，测试覆盖率 ≥ 80%
- **Estimated**: 2 hours
- **Priority**: P0

#### Task 2.4: EmbeddingGenerator 多 Provider + 性能优化
- [ ] 检查 `src/embedding/` Embedding 生成逻辑
- [ ] 测试火山引擎 Provider
- [ ] 测试 OpenAI Provider
- [ ] 测试本地 sentence-transformers Provider
- [ ] 编写单元测试（Mock API）
- [ ] **[NEW]** 添加并发 Embedding 调用（asyncio.gather + semaphore）
- [ ] **[NEW]** 添加 Embedding 缓存（文本 → 向量）
- [ ] **[NEW]** 添加自适应速率限制
- [ ] **[NEW]** 添加 timeout 配置
- **Dependencies**: Task 1.2, Task 0.2
- **Deliverables**: 多 Provider 支持可用，性能优化完成
- **Estimated**: 5 hours (原 3h + 2h 优化)
- **Priority**: P0

#### Task 2.5: ChromaManager 向量存储 + 批量状态
- [ ] 检查 `src/storage/chroma_manager.py` 存储逻辑
- [ ] 测试向量写入和检索
- [ ] 测试元数据管理
- [ ] **[NEW]** 添加批量操作 per-item 状态返回
- **Dependencies**: Task 2.4, Task 0.3
- **Deliverables**: ChromaDB 操作稳定，批量状态可追踪
- **Estimated**: 2 hours (原 1h + 1h 改进)
- **Priority**: P1

#### Task 2.6: ClusterAnalyzer 聚类
- [ ] 检查 `src/clustering/` HDBSCAN 实现
- [ ] 测试聚类参数调优
- [ ] 测试结果输出格式
- [ ] 编写单元测试
- **Dependencies**: Task 2.5
- **Deliverables**: 聚类算法可用，测试覆盖率 ≥ 80%
- **Estimated**: 2 hours
- **Priority**: P0

### Phase 3: Analysis Layer
**Estimated Time**: 12 hours (原 10h + 2h 改进)

#### Task 3.1: LabelGenerator LLM 标签
- [ ] 检查 `src/analyzer/labeling/` 标签生成逻辑
- [ ] 测试 LLM Prompt 构建
- [ ] 测试标签输出解析
- [ ] 编写单元测试（Mock LLM）
- **Dependencies**: Task 2.6
- **Deliverables**: 标签生成可用
- **Estimated**: 2 hours
- **Priority**: P1

#### Task 3.2: RootCauseAnalyzer 深度分析
- [ ] 检查 `src/analyzer/reasoning/` 根因分析逻辑
- [ ] 检查 `src/analysis/root_cause/` 5层追问机制
- [ ] 测试 Prompt 模板
- [ ] 测试根因挖掘逻辑
- [ ] 编写单元测试（Mock LLM）
- **Dependencies**: Task 3.1
- **Deliverables**: 深度根因分析可用
- **Estimated**: 4 hours
- **Priority**: P0

#### Task 3.3: ViolationDetector 规则检测
- [ ] 检查 `src/rules/` 规则引擎
- [ ] 检查 `src/analysis/violation_detector.py` 违规检测
- [ ] 测试规则匹配逻辑
- [ ] 测试违规识别准确性
- [ ] 编写单元测试
- **Dependencies**: Task 1.1
- **Deliverables**: 违规检测可用
- **Estimated**: 2 hours
- **Priority**: P1

#### Task 3.4: ImprovementRecommender 改进建议
- [ ] 检查 `src/analysis/improvement_recommender.py` 改进建议逻辑
- [ ] 测试建议生成与违规项关联
- [ ] 编写单元测试（Mock LLM）
- **Dependencies**: Task 3.2, Task 3.3
- **Deliverables**: 改进建议生成可用
- **Estimated**: 2 hours
- **Priority**: P1

#### Task 3.5: 错误处理框架
- [ ] 创建 `src/exceptions.py` 自定义异常体系
- [ ] 定义 PipelineError, EmbeddingError, LLMError, ChromaDBError 等
- [ ] 替换现有 `except Exception` 为具体异常类型
- [ ] **[NEW]** 添加 LLM Response Guard（验证空响应、畸形 JSON）
- **Dependencies**: 无
- **Deliverables**: 完整异常体系，结构化错误处理
- **Estimated**: 2 hours
- **Priority**: P0

### Phase 4: Pipeline Refactoring
**Estimated Time**: 4 hours
**Source**: GSTACK CEO Review - Code Quality

#### Task 4.0: Pipeline 拆分重构
- [ ] 创建 `src/analyzer/pipeline_base.py` 基础接口
- [ ] 创建 `src/analyzer/handlers/` 各阶段处理器
  - `fetch_handler.py` - 数据获取处理器
  - `preprocess_handler.py` - 预处理处理器
  - `embed_handler.py` - 向量化处理器
  - `cluster_handler.py` - 聚类处理器
  - `analyze_handler.py` - 分析处理器
- [ ] 重构 `pipeline.py` 为 Orchestrator 模式
- [ ] 更新测试
- **Dependencies**: Task 3.5
- **Deliverables**: Pipeline 遵循 SRP，职责清晰
- **Estimated**: 4 hours
- **Priority**: P1

### Phase 5: Output Layer
**Estimated Time**: 6 hours

#### Task 5.1: ReportGenerator 报告
- [ ] 检查 `src/report/` 报告生成逻辑
- [ ] 测试 Excel 导出
- [ ] 测试 HTML 报告模板
- [ ] 编写单元测试
- **Dependencies**: Task 3.4
- **Deliverables**: 报告生成可用
- **Estimated**: 2 hours
- **Priority**: P2

#### Task 5.2: Visualization 图表
- [ ] 检查 `src/visualization/` 图表组件
- [ ] 测试聚类散点图
- [ ] 测试统计图表
- [ ] 编写单元测试
- **Dependencies**: Task 2.6
- **Deliverables**: 可视化组件可用
- **Estimated**: 2 hours
- **Priority**: P2

#### Task 5.3: CLI 命令完善
- [ ] 检查 `src/cli/` CLI 命令
- [ ] 测试 fetch/analyze/report 命令
- [ ] 编写 E2E 测试
- **Dependencies**: 所有核心组件
- **Deliverables**: CLI 可用
- **Estimated**: 1 hour
- **Priority**: P2

#### Task 5.4: Streamlit UI
- [ ] 检查 `src/ui/streamlit_app.py` UI 实现
- [ ] 测试交互式分析界面
- [ ] 编写 E2E 测试（Playwright）
- **Dependencies**: 所有核心组件
- **Deliverables**: UI 可用
- **Estimated**: 1 hour
- **Priority**: P2

### Phase 6: Testing & Quality
**Estimated Time**: 6 hours (原 4h + 2h 改进)

#### Task 6.1: 集成测试完善
- [ ] 编写 Pipeline 端到端测试
- [ ] 测试 Phase1/Phase2 批量流程
- [ ] 测试错误处理和边界情况
- [ ] **[NEW]** 扩展集成测试场景（多故障单、错误处理）
- **Dependencies**: 所有实现任务
- **Deliverables**: 集成测试覆盖率 ≥ 60%
- **Estimated**: 3 hours (原 2h + 1h)
- **Priority**: P2

#### Task 6.2: 变异测试
- [ ] 配置 mutmut 变异测试框架
- [ ] 运行变异测试验证测试有效性
- [ ] 修复发现的测试弱点
- **Dependencies**: Task 6.1
- **Deliverables**: 变异测试通过，测试质量验证
- **Estimated**: 1 hour
- **Priority**: P2

#### Task 6.3: 代码审查与重构
- [ ] 对照 code-review-checklist.md 自查
- [ ] 重构不符合 Clean Code / SOLID 的部分
- [ ] 运行 ruff check/format
- [ ] 运行 mypy 类型检查
- **Dependencies**: 所有实现任务
- **Deliverables**: 代码质量达标
- **Estimated**: 1 hour
- **Priority**: P2

#### Task 6.4: 文档更新
- [ ] 更新 CLAUDE.md（架构变化）
- [ ] 更新 .speckit/analyze.md
- [ ] 更新 README.md
- **Dependencies**: Task 6.3
- **Deliverables**: 文档同步
- **Estimated**: 1 hour
- **Priority**: P3

### Phase 7: Observability
**Estimated Time**: 4 hours
**Source**: GSTACK CEO Review - Observability

#### Task 7.1: 结构化日志
- [ ] 配置 loguru JSON 输出格式
- [ ] 添加日志级别配置（DEV vs PROD）
- [ ] 更新现有日志调用使用结构化格式
- **Dependencies**: 无
- **Deliverables**: 支持 JSON 结构化日志
- **Estimated**: 1 hour
- **Priority**: P2

#### Task 7.2: Prometheus Metrics
- [ ] 创建 `src/metrics.py` Prometheus 指标定义
- [ ] 添加 API 延迟、吞吐量、错误率指标
- [ ] 添加 Embedding 生成耗时指标
- [ ] 添加聚类耗时指标
- **Dependencies**: 无
- **Deliverables**: Prometheus metrics 端点可用
- **Estimated**: 2 hours
- **Priority**: P2

#### Task 7.3: Correlation IDs
- [ ] 创建 `src/utils/correlation.py` correlation ID 管理
- [ ] 为每个 Pipeline 执行生成唯一 ID
- [ ] 在日志和错误中传递 correlation ID
- **Dependencies**: 无
- **Deliverables**: 请求跨组件可追踪
- **Estimated**: 1 hour
- **Priority**: P2

### Phase 8: REST API Layer (Expansion #5)
**Estimated Time**: 8 hours
**Source**: GSTACK CEO Review - Scope Expansions

#### Task 8.1: FastAPI 项目初始化
- [ ] 创建 `src/api/rest/` 目录结构
- [ ] 配置 FastAPI 应用
- [ ] 添加 CORS、认证中间件
- [ ] **[NEW]** 添加 /health 和 /ready 健康检查端点
- **Dependencies**: Phase 4 (Pipeline 拆分)
- **Deliverables**: FastAPI 项目结构就绪
- **Estimated**: 2 hours
- **Priority**: P0

#### Task 8.2: 分析 API 端点
- [ ] POST /api/v1/tasks/{task_id}/analyze - 单任务分析
- [ ] POST /api/v1/tasks/batch-analyze - 批量分析
- [ ] GET /api/v1/tasks/{task_id}/result - 获取分析结果
- [ ] GET /api/v1/clusters - 获取聚类列表
- [ ] GET /api/v1/clusters/{cluster_id} - 获取聚类详情
- **Dependencies**: Task 8.1
- **Deliverables**: REST API 端点可用
- **Estimated**: 3 hours
- **Priority**: P0

#### Task 8.3: API 文档与测试
- [ ] 完善 OpenAPI 文档
- [ ] 编写 API 端点测试
- [ ] 添加请求/响应示例
- **Dependencies**: Task 8.2
- **Deliverables**: API 文档完整，测试通过
- **Estimated**: 2 hours
- **Priority**: P1

#### Task 8.4: API 性能与安全
- [ ] 添加请求速率限制
- [ ] 添加输入验证
- [ ] 添加响应缓存
- **Dependencies**: Task 8.2
- **Deliverables**: API 安全加固
- **Estimated**: 1 hour
- **Priority**: P1

### Phase 9: Feedback Loop (Expansion #2)
**Estimated Time**: 6 hours
**Source**: GSTACK CEO Review - Scope Expansions

#### Task 9.1: 复发追踪数据模型
- [ ] 创建 `src/feedback/models.py` 数据模型
- [ ] 定义 RecurrencePattern, FeedbackRecord
- [ ] 添加 ChromaDB collection 用于反馈存储
- **Dependencies**: Phase 8 (REST API)
- **Deliverables**: 反馈数据模型定义
- **Estimated**: 1 hour
- **Priority**: P1

#### Task 9.2: 复发检测服务
- [ ] 创建 `src/feedback/recurrence_detector.py`
- [ ] 实现基于相似度的复发检测
- [ ] 实现模式识别算法
- **Dependencies**: Task 9.1
- **Deliverables**: 复发检测服务可用
- **Estimated**: 2 hours
- **Priority**: P1

#### Task 9.3: 反馈 API 端点
- [ ] POST /api/v1/feedback - 提交反馈
- [ ] GET /api/v1/recurrences - 获取复发模式
- [ ] GET /api/v1/alerts - 获取模式告警
- **Dependencies**: Task 9.2
- **Deliverables**: 反馈 API 可用
- **Estimated**: 2 hours
- **Priority**: P1

#### Task 9.4: 告警通知
- [ ] 实现告警触发逻辑
- [ ] 添加通知渠道配置（日志/Webhook）
- **Dependencies**: Task 9.3
- **Deliverables**: 模式告警可用
- **Estimated**: 1 hour
- **Priority**: P2

### Phase 10: CI/CD Integration (Expansion #1)
**Estimated Time**: 4 hours
**Source**: GSTACK CEO Review - Scope Expansions

#### Task 10.1: Pre-commit 故障检测 Hook
- [ ] 创建 `.pre-commit-hooks.yaml` 自定义 hook
- [ ] 实现代码变更风险分析
- [ ] 集成 ViolationDetector
- **Dependencies**: Phase 8 (REST API)
- **Deliverables**: Pre-commit hook 可用
- **Estimated**: 2 hours
- **Priority**: P1

#### Task 10.2: CI Pipeline 配置
- [ ] 创建 `.github/workflows/analyze.yml`
- [ ] 配置自动故障分析流水线
- [ ] 添加分析报告生成
- **Dependencies**: Task 10.1
- **Deliverables**: CI Pipeline 可用
- **Estimated**: 2 hours
- **Priority**: P1

### Phase 11: Advanced Expansions (Future)
**Estimated Time**: 12 hours
**Source**: GSTACK CEO Review - Scope Expansions (P3)

#### Task 11.1: Actionable Recommendations Engine (Expansion #3)
- [ ] 创建 `src/recommendations/` 模块
- [ ] 实现代码修复建议生成
- [ ] 实现测试用例生成
- [ ] 集成到 REST API
- **Dependencies**: Phase 9 (Feedback Loop)
- **Deliverables**: 改进建议引擎可用
- **Estimated**: 6 hours
- **Priority**: P3

#### Task 11.2: Real-time Processing (Expansion #4)
- [ ] 添加消息队列支持（Redis/RabbitMQ）
- [ ] 实现流式处理模式
- [ ] 实现增量聚类
- **Dependencies**: Phase 8, Phase 9
- **Deliverables**: 实时处理模式可用
- **Estimated**: 6 hours
- **Priority**: P3

## Task Status Summary

| Phase | Status | Progress | Estimated | Actual |
|-------|--------|----------|-----------|--------|
| 0. Architecture & Security | Not Started | 0% | 8h | - |
| 1. Foundation | Not Started | 0% | 4h | - |
| 2. Core Functionality | Not Started | 0% | 16h | - |
| 3. Analysis Layer | Not Started | 0% | 12h | - |
| 4. Pipeline Refactoring | Not Started | 0% | 4h | - |
| 5. Output Layer | Not Started | 0% | 6h | - |
| 6. Testing & Quality | Not Started | 0% | 6h | - |
| 7. Observability | Not Started | 0% | 4h | - |
| 8. REST API Layer | Not Started | 0% | 8h | - |
| 9. Feedback Loop | Not Started | 0% | 6h | - |
| 10. CI/CD Integration | Not Started | 0% | 4h | - |
| 11. Advanced Expansions | Not Started | 0% | 12h | - |
| **Total** | Not Started | **0%** | **90h** | - |

## Priority Order

### P0 (Critical) - 必须完成，约 30h
- **Phase 0**: Task 0.1, 0.2, 0.3, 0.4, 0.5 (Architecture & Security)
- **Phase 1**: Task 1.1, 1.2 (Foundation)
- **Phase 2**: Task 2.1, 2.3, 2.4, 2.6 (Core)
- **Phase 3**: Task 3.2, 3.5 (Analysis + Error Handling)
- **Phase 8**: Task 8.1, 8.2 (REST API)

### P1 (High) - 重要功能，约 30h
- **Phase 2**: Task 2.2, 2.5 (Cache + ChromaDB)
- **Phase 3**: Task 3.1, 3.3, 3.4 (Analysis Layer)
- **Phase 4**: Task 4.0 (Pipeline Refactoring)
- **Phase 8**: Task 8.3, 8.4 (API Docs + Security)
- **Phase 9**: Task 9.1, 9.2, 9.3 (Feedback Loop)
- **Phase 10**: Task 10.1, 10.2 (CI/CD)

### P2 (Medium) - 输出和质量，约 24h
- **Phase 1**: Task 1.3 (Testing Framework)
- **Phase 5**: Task 5.1, 5.2, 5.3, 5.4 (Output Layer)
- **Phase 6**: Task 6.1, 6.2, 6.3 (Testing)
- **Phase 7**: Task 7.1, 7.2, 7.3 (Observability)
- **Phase 9**: Task 9.4 (Alerts)

### P3 (Low) - 高级功能，约 6h
- **Phase 6**: Task 6.4 (Documentation)
- **Phase 11**: Task 11.1, 11.2 (Advanced Expansions)

## Definition of Done for Each Task
- [ ] 实现完成
- [ ] 测试编写并通过
- [ ] 代码已格式化（`ruff format`）
- [ ] Lint 无错误（`ruff check`）
- [ ] 类型检查通过（`mypy`）
- [ ] 代码审查通过
- [ ] 文档更新（如需）

## Execution Roadmap

### Week 1-2: P0 Critical (30h)
- Phase 0: Architecture & Security Fixes
- Phase 1: Foundation
- Phase 2: Core Functionality (部分)
- Phase 3: Error Handling Framework

### Week 3-4: P0 + P1 (30h)
- Phase 2: Core Functionality (完成)
- Phase 3: Analysis Layer
- Phase 4: Pipeline Refactoring
- Phase 8: REST API Layer

### Week 5-6: P1 + P2 (30h)
- Phase 5: Output Layer
- Phase 6: Testing & Quality
- Phase 7: Observability
- Phase 9: Feedback Loop
- Phase 10: CI/CD Integration

### Month 2+: P3 Advanced (6h+)
- Phase 11: Advanced Expansions
- 持续优化和维护

## Notes
- 所有任务遵循 TDD: Write test → Implement → Refactor
- 每完成一个 Task，运行质量检查
- 更新本文件标记任务状态
- 发现阻塞问题及时记录
- **NEW** 标记为 GSTACK CEO 审查新增任务

## References

- **Specification**: `.speckit/specify.md`
- **Plan**: `.speckit/plan.md` (含 GSTACK CEO Review Report)
- **Constitution**: `.speckit/constitution.md`
- **Code Review Checklist**: `E:\Private\dev-workflow\.codebuddy\skills\dev-workflow\references\code-review-checklist.md`

---

**Status**: Not Started
**Owner**: Development Team
**Last Updated**: 2026-03-30
**Review Source**: GSTACK CEO Review (26 improvements approved)