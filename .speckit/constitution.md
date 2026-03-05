# Project Constitution

## Project Name
fault-review-analyzer（故障复盘分析工具）

## Vision
AI 驱动的故障复盘分析流水线。从外部 REST API 拉取 Bug/故障工单，经过文本预处理、向量 Embedding，通过 HDBSCAN 密度聚类发现相似问题簇，最终生成根因标签和复盘报告——全程无需预定义标签。

## Core Values
1. **Quality**: 通过 TDD、Clean Code、SOLID 原则保证代码质量
2. **Clarity**: 编写自文档代码，变量/函数命名揭示意图
3. **Testability**: 所有代码先写测试（TDD），覆盖率 ≥ 80%
4. **Maintainability**: 遵循分层架构，保持模块边界清晰
5. **Traceability**: 通过 SDD 确保需求→设计→任务→代码的全程可追溯

## Development Principles

### SDD (Specification-Driven Development)
- 每个新功能从 `.speckit/specify.md` 的规格说明开始
- Specification 描述 WHAT（做什么），不描述 HOW（怎么做）
- Plan 将规格翻译为技术设计
- Tasks 将实现分解为具体可执行步骤
- Analyze 确保规格、计划、任务三者一致

### TDD (Test-Driven Development)
- 先写失败的测试，再写让测试通过的实现代码
- 只写让当前测试通过的最少代码
- 通过后立即重构，保持代码整洁
- 所有代码必须有对应测试，覆盖率下限 80%

### Clean Code
- 使用描述性、揭示意图的命名
- 函数短小，只做一件事（≤ 20 行为宜）
- 注释解释"为什么"，不解释"是什么"
- 不重复（DRY 原则）
- 函数参数最多 3-4 个

### SOLID Principles
- **SRP**：每个类/模块只有一个变化原因
- **OCP**：对扩展开放，对修改关闭
- **LSP**：子类型可以无缝替代基类型
- **ISP**：接口小而专一
- **DIP**：依赖抽象，不依赖具体实现

### Clean Architecture
- 依赖方向只能由外向内
- **Entities**：纯业务规则（`src/api/models.py`，Pydantic 数据模型）
- **Use Cases**：编排实体（`src/preprocessor/`，`src/embedding/`，`src/clustering/`）
- **Interface Adapters**：数据转换（`src/cli/`，`src/config/`，`src/cache/`）
- **Frameworks**：外部工具（OpenAI SDK、HDBSCAN、SQLite）

## Current Architecture

```
fault-review-analyzer/
├── .speckit/                    # SDD 工作流文档
│   ├── constitution.md          # 本文件（项目章程）
│   ├── specify.md               # 功能规格说明（每功能一份或按阶段汇总）
│   ├── plan.md                  # 技术实现计划
│   ├── tasks.md                 # 任务分解
│   └── analyze.md               # 一致性分析
├── src/
│   ├── api/                     # API 客户端 + 数据模型
│   ├── cache/                   # SQLite 缓存层
│   ├── config/                  # 配置管理
│   ├── preprocessor/            # 文本预处理
│   ├── embedding/               # OpenAI Embedding 生成
│   ├── clustering/              # HDBSCAN 聚类分析
│   ├── analyzer/                # [待实现] LLM 标签生成 + 根因推理
│   ├── report/                  # [待实现] 报告生成
│   ├── rules/                   # [待实现] 规则引擎
│   └── cli/                     # Typer CLI 命令
├── tests/                       # 测试代码（结构镜像 src/）
├── review/                      # 代码审查报告
├── code-review-checklist.md     # 代码审查清单
├── config.yaml                  # 默认配置
└── pyproject.toml               # 项目配置 + 依赖
```

## Python Toolchain

| 工具 | 用途 | 命令 |
|------|------|------|
| **Ruff** | Lint + Format | `ruff check src/ tests/` / `ruff format src/ tests/` |
| **mypy** | 类型检查 | `mypy src/` |
| **pytest** | 测试 + 覆盖率 | `pytest tests/ -v --cov=src` |

### Quality Gate（提交前必须全部通过）

```bash
ruff check src/ tests/        # Linting
ruff format src/ tests/       # Formatting
mypy src/                     # Type checking
pytest tests/ -v --cov=src    # Tests（覆盖率 ≥ 80%）
```

## Commit Message Format

```
<type>(<scope>): <subject>

<body>（可选）

<footer>（可选，如 Closes #123）
```

### Types
- `feat`：新功能
- `fix`：Bug 修复
- `refactor`：代码重构（不影响功能）
- `test`：新增或修改测试
- `docs`：文档更新
- `chore`：维护性任务（依赖升级等）
- `style`：格式调整（不影响逻辑）
- `perf`：性能优化

### Examples
```
feat(clustering): add cosine distance normalization for HDBSCAN

Use L2 normalization before euclidean metric to approximate
cosine distance, which is more appropriate for embedding vectors.
```

```
fix(api): return None for missing optional datetime fields

_parse_datetime now returns None when value is None or empty,
fixing crash for unresolved tasks without resolveTime field.
```

## Quality Gates

每次提交前必须通过：
- [ ] 所有测试通过（`pytest`）
- [ ] 测试覆盖率 ≥ 80%
- [ ] Ruff lint 无错误
- [ ] 代码已格式化
- [ ] mypy 类型检查通过
- [ ] code-review-checklist.md 核心项已确认
- [ ] SDD 文档与实现保持同步

## Current Development Status

| 阶段 | 模块 | 状态 |
|------|------|------|
| 1. Fetch | `src/api/`, `src/cache/` | ✅ 已实现 |
| 2. Preprocess | `src/preprocessor/` | ✅ 已实现 |
| 3. Embed | `src/embedding/` | ✅ 已实现 |
| 4. Cluster | `src/clustering/` | ✅ 已实现 |
| 5. Label | `src/analyzer/labeling/` | ⏳ 待实现 |
| 6. Reason | `src/analyzer/reasoning/` | ⏳ 待实现 |
| 7. Report | `src/report/` | ⏳ 待实现 |
| 8. Pipeline | 无对应文件 | ⏳ 待实现 |

## Continuous Improvement

本章程是活文档。发现需要改进的地方时：
1. 在 `specify.md` 中记录问题
2. 在 `plan.md` 中提出改进方案
3. 讨论并达成共识
4. 更新本章程
5. 同步给所有参与者

---

**Version**: 1.0
**Last Updated**: 2026-03-04
**Status**: Active
