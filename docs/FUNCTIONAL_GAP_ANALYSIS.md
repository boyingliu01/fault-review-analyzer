# 功能 GAP 分析报告（Functional Gap Analysis）

**分析日期**: 2026-08-25
**分析对象**: Fault Review Analyzer（故障复盘分析工具）
**基线**: `master` @ `9618ad0`
**需求来源**:
- `.sprint-state/specification.yaml` — 《代码变更分析链路补齐方案》
- `.speckit/specify.md` — 《故障复盘分析系统 - 核心流水线》功能规格
- `.speckit/plan.md` + GSTACK CEO Review（26 项改进）
- `.speckit/tasks.md` — 任务分解

---

## 一、总体结论

代码变更分析链路（specification.yaml）**已基本完整实现（6/7）**。核心流水线（specify.md）的功能模块大多已实现，但存在 **4 个关键功能缺口（GAP）** 与 **6 个部分实现（PARTIAL）**，主要集中于：**ChromaDB 存储未接线、簇语义标签为死代码、深度根因分析被占位符绕过、改进建议未接入主流水线、REST API 路径与规范不一致**。

---

## 二、代码变更分析链路（specification.yaml）GAP

| # | 需求项 | 状态 | 证据 |
|---|--------|------|------|
| 1 | `CommitInfo` 含 `diff` 字段 | ✅ 已实现 | `src/api/models.py:23` — `diff: str = Field(default="", ...)` |
| 2 | `APIClient.get_code_diffs()` + 降级 | ⚠️ **GAP** | 方法 `get_code_diffs()` 全仓不存在；功能在 `get_commits()`（`client.py:261`）。降级不完整：`get_commits()` 走 `_request()` 失败时**抛异常**而非返回空，仅 `get_full_task()` 捕获 `NotFoundError` |
| 3 | `run_single()` 集成 `CodeChangeAnalyzer` + `_analyze_code_changes()` | ✅ 已实现 | `pipeline.py:174,224`；`src/analysis/code_change_analyzer.py:68` |
| 4 | `PipelineResult.code_change_analysis` 字段 | ✅ 已实现 | `pipeline.py:75,261,292,866` |
| 5 | `RulesEngine.check()` 改为检查代码 diff（保留 commit message 兜底） | ✅ 已实现 | `src/rules/engine.py:329-350` — diff 优先，message 兜底 |
| 6 | `PipelineResult.violations` 填充真实违规数据 | ✅ 已实现 | `pipeline.py:283,270-275` — RulesEngine + ViolationDetector 双源 |
| 7 | `run_clustering()` 输入改为"故障描述+代码变更分析摘要"，优先代码特征 | ✅ 已实现 | `pipeline.py:418-473` — `clustering_mode: code_change_enhanced / text_only` |

**代码变更链路唯一缺口**: 规范命名的 `get_code_diffs()` 方法未实现（改为 `get_commits()`），且在线抓取路径缺少"API 不可用时返回空"的优雅降级。

---

## 三、核心流水线（specify.md）功能 GAP

### 3.1 数据获取与预处理

| 需求 | 状态 | 证据 / 缺口 |
|------|------|-------------|
| 获取完整故障信息（含代码变更） | ✅ 已实现 | `client.py:395-419` `get_full_task()` 同时取 task + commits |
| 获取**复盘结论** | ⚠️ **PARTIAL** | `get_fault_analysis()`（`client.py:421-432`）仅在 `_analyze_root_cause_deep()` 中调用，且受 `analyze_root_cause_deep`（默认 `False`）门控；**标准 fetch 流程不获取复盘结论** |
| 文本预处理（提取关键字段、组合分析文本） | ✅ 已实现 | `src/preprocessor/processor.py:9-24,187-198` |
| SQLite 缓存（避免重复请求） | ✅ 已实现 | `src/cache/manager.py:61-103`（TTL 86400），`fetch.py:50-65` 接线 |
| **Embedding 生成并存储到 ChromaDB** | ⚠️ **关键 GAP** | Embedding 已实现（`generator.py:193,276`），但 **`ChromaManager` 从未被 pipeline/orchestrator/handler 引用**。`run_clustering()`（`pipeline.py:448-452`）计算 embedding 后直接 `np.array → fit_predict()`，**未持久化到 ChromaDB**。存储层是死代码 |

### 3.2 聚类、标签与根因分析

| 需求 | 状态 | 证据 / 缺口 |
|------|------|-------------|
| HDBSCAN 聚类发现相似问题簇 | ✅ 已实现 | `src/clustering/analyzer.py:29-72`，`pipeline.py:382-473` |
| 小于 min_cluster_size 标记为噪声（-1） | ✅ 已实现 | `analyzer.py:51-52,104`；`test_business_rules.py:262-332` |
| **为每个聚类簇生成语义标签**（如"数据库问题"） | ⚠️ **GAP（死代码）** | `LabelGenerator.generate_for_cluster()`（`generator.py:114-147`）**从未被调用**（grep 仅定义处 1 处匹配）。`run_clustering()` 不生成 `cluster_label`，规范输出字段 `cluster_label`（specify.md:91）从未填充 |
| 深度根因分析（**5 层追问机制**） | ⚠️ **GAP** | (a) 追问机制为 **3 问非 5 层**（`root_cause/prompts.py:40-51`）；(b) 重构后的 orchestrator 路径 `handlers/analyze.py:113-128` 的 `analyze_root_cause_deep()` 是**占位符直接返回 `{}`**，真实逻辑只在旧 `AnalysisPipeline`（`pipeline.py:642-699`） |
| 根因分析优先使用现有复盘结论（规则3） | ⚠️ **PARTIAL** | 实现为"仅供参考、不要直接复制"（`prompts.py:15-27,81`），与规范"**优先使用**现有结论"语义相反 |
| 单样本簇 → 噪声点 | ✅ 已实现 | `analyzer.py:51-52`；`test_business_rules.py:262-278` |
| 无代码变更 → 跳过违规检测，仅根因分析 | ✅ 已实现 | `pipeline.py:224-227,270`；`rules/engine.py:340` |

### 3.3 违规检测与改进建议

| 需求 | 状态 | 证据 / 缺口 |
|------|------|-------------|
| 基于开发规范检测代码变更违规 | ✅ 已实现 | `ViolationDetector.detect()`（`violation_detector.py:147-191`）+ `RulesEngine.check()`（`engine.py:329-381`）+ `StandardsMatcher` |
| **只有 `isCommitCode=Y` 的故障单才做违规检测**（规则1） | ⚠️ **GAP** | `isCommitCode`/`is_commit_code` 字段在 `src/` 中**完全不存在**。`TaskInfo`（`api/models.py:82-93`）无此字段；门控隐式基于 `development.commits` 是否存在，而非规范标志位 |
| **改进建议关联具体规范条款**（引用编号如 J000001）（规则4） | ⚠️ **GAP** | `ImprovementRecommender` 输出 `ImprovementMeasure`（`improvement_recommender.py:13-24`）**无 `rule_id` 字段**，建议来自按类别（"违规类"等）的模板，不引用规范编号。仅 ViolationDetector/StandardsMatcher 输出带 rule_id |
| **生成改进建议和行动项** | ⚠️ **GAP（未接线）** | `ImprovementRecommender` 仅在 `streamlit_app.py`（行 32,456,504）实例化，**未接入 pipeline/orchestrator**。`PipelineResult` **无 `improvements` 字段**（grep 0 匹配）。规范输出字段 `improvements`（specify.md:94）从未作为流水线输出 |
| RulesEngine 加载规则、模式匹配、违规判定 | ✅ 已实现 | `engine.py:229-255`（内置+自定义加载）、`check()` 匹配判定；`knowledge/manager.py:30-75` 加载 J000xxx 规范条款 |

### 3.4 输出层与 REST API

| 需求 | 状态 | 证据 / 缺口 |
|------|------|-------------|
| CLI 批量操作（fetch/analyze/report） | ✅ 已实现 | `src/cli/main.py:17-21` 注册 5 个子应用 |
| Streamlit 交互式 Web 界面 | ✅ 已实现 | `streamlit_app.py:40-85`（5 个页面） |
| **可视化报告（Excel 导出 + 聚类散点图、统计图表）** | ⚠️ **PARTIAL** | 散点图（`cluster_scatter.py` UMAP+Plotly）与统计图表（`charts.py`）已实现；但 **Excel 导出完全缺失**（全仓 grep openpyxl/xlsx 0 匹配）。报告仅 Markdown/HTML/PDF/JSON |
| **REST API 端点** | ⚠️ **PARTIAL** | 端点存在但**路径与规范不一致**：无 `/api/v1` 前缀（全部在根路径）；无 `GET /api/v1/tasks/{id}/result`（最接近为 `GET /reports/{task_id}`）；**无 `/ready` 健康检查**（仅 `/health`）；`GET /clusters` 读内存缓存 `_cluster_cache` 但**无任何路由填充它** → 实际恒为空列表，`GET /clusters/{id}` 恒 404 |
| **反馈循环（RecurrencePattern、recurrence_detector.py）** | ⚠️ **PARTIAL** | Feedback 模型/管理器/SQLite 持久化/API/重训触发器均已实现；但 **`RecurrencePattern` 模型缺失**、**`recurrence_detector.py` 不存在**、模型命名为 `Feedback` 而非 `FeedbackRecord` |

---

## 四、非功能需求 GAP

| 需求 | 状态 | 证据 / 缺口 |
|------|------|-------------|
| 性能：单故障处理 < 30 秒（不含 LLM） | ⚠️ **GAP（不可验证/无强制）** | 无端到端耗时预算/断言。仅 `client.py:32` 设单次 HTTP timeout=30，非整体 SLA。`run_single()` 无 `time.perf_counter` 预算检查 |
| 可扩展性：支持 1000+ 故障单批量 | ⚠️ **PARTIAL** | CLI/聚类路径支持（`pipeline.py:363-380` semaphore+gather，embedding 按 batch_size 分块）；但 REST `/analyze/batch` 被 `server_models.py:8` `MAX_BATCH_TASK_IDS=50` 上限，**通过 HTTP API 无法一次处理 1000+** |
| 可靠性：API 缓存避免重复请求 | ✅ 已实现 | SQLite 缓存 + LRU embedding 缓存 + ChromaDB 降级文件缓存 |
| 可维护性：模块化架构 | ✅ 已实现 | 目录结构与 Clean Architecture 分层一致 |

---

## 五、GAP 汇总（按优先级）

### 🔴 关键缺口（功能不可达 / 死代码）

| # | 缺口 | 影响 | 建议修复 |
|---|------|------|----------|
| G1 | **ChromaDB 存储未接线**（`ChromaManager` 无任何调用方） | 规范 Phase1 "存储到 ChromaDB" 从未执行，向量存储层是死代码 | 在 `run_clustering()`（`pipeline.py:447-452`）embed 后调用 `add_batch_embeddings()` 持久化 |
| G2 | **簇语义标签是死代码**（`generate_for_cluster` 未被调用） | 规范输出 `cluster_label` 从未产生 | 在 `run_clustering()` 中对非噪声簇调用 `generate_for_cluster()` |
| G3 | **深度根因分析被占位符绕过**（`handlers/analyze.py:113-128` 返回 `{}`） | 生产（orchestrator）路径实际不做深度根因分析 | 将 `pipeline.py:642-699` 的真实逻辑移植进 handler |
| G4 | **改进建议未接入主流水线**（`PipelineResult` 无 `improvements` 字段） | 规范输出 `improvements`/行动项不作为流水线产物 | 在 pipeline 实例化 `ImprovementRecommender` 并新增 `improvements` 字段 |

### 🟠 重要缺口（语义偏差 / 部分实现）

| # | 缺口 | 建议 |
|---|------|------|
| G5 | `isCommitCode` 字段不存在，规则1门控不按规范标志位 | 在 `TaskInfo` 增加 `is_commit_code` 字段并在 `_analyze_code_changes()` 显式门控 |
| G6 | 改进建议不关联规范条款（无 `rule_id`） | 为 `ImprovementMeasure` 增加 `rule_ids` 并从违规项回填 |
| G7 | 深度根因"5层追问"实为 3 问 | 将 `prompts.py:40-51` 扩展为 5 层追问 |
| G8 | 复盘结论不在标准 fetch 流程获取 | 在 `get_full_task()`/`FetchHandler.fetch_task()` 中纳入 `get_fault_analysis()` |
| G9 | REST API 路径与规范不一致（无 `/api/v1`、无 `/tasks/{id}/result`、无 `/ready`、clusters 缓存未填充） | 对齐路径或文档化偏差；接线 `update_cluster_cache()` |
| G10 | 反馈循环缺 `RecurrencePattern` / `recurrence_detector.py` | 实现复发检测组件 |
| G11 | Excel 导出缺失 | 为 `ReportGenerator` 增加 `ReportFormat.EXCEL` + openpyxl writer |
| G12 | 根因分析"优先使用现有结论"语义相反 | 调整 prompt 措辞对齐规范 |
| G13 | `get_code_diffs()` 未实现 + 抓取无优雅降级 | 增加别名或改名，`get_commits()` 失败时返回空 |

### 🟡 次要缺口

| # | 缺口 | 建议 |
|---|------|------|
| G14 | <30 秒 SLA 无强制/度量 | `run_single()` 加 `time.perf_counter` 预算断言 |
| G15 | REST 批量上限 50，无法 HTTP 达 1000+ | 提高上限或加服务端分页 |
| G16 | CLI 批量不支持直接传任务号列表/Excel 输入 | 增加从 Excel 读取任务号 |
| G17 | fetch 侧无速率限制（仅 embedding 侧有 `AdaptiveRateLimiter`） | 为 `APIClient`/`FetchHandler` 补限流 |
| G18 | 噪声点（cluster_id=-1）无独立下游分析分支 | 增加单独分析路径 |

---

## 六、结论

**代码变更分析链路（specification.yaml）**：功能完整，仅 1 处方法命名/降级缺口（G13）。

**核心流水线（specify.md）**：骨架完整（获取/预处理/聚类/违规检测/CLI/UI 均实现），但存在 **4 个关键功能缺口（G1-G4）** 使规范要求的若干**输出产物不可达**（ChromaDB 存储、簇语义标签、深度根因分析、改进建议/行动项）。另有 9 个重要语义/接线缺口（G5-G13）。

**建议**：优先修复 G1-G4（关键缺口，直接决定规范输出是否可达），再处理 G5-G13。若 REST API 路径与 Excel 导出的偏差是**有意设计**（规范为愿景，实际用根路径/非 Excel 格式），应在 `.speckit/specify.md` 中**文档化偏差**而非改代码——需与需求方确认。

---

*本报告由对 master@9618ad0 的全量代码审查生成，所有证据均含 file:line 定位。*
