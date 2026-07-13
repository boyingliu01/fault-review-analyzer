# Project Constitution

## Project Name
fault-review-analyzer（故障复盘分析工具）

## Vision
AI 驱动的故障复盘分析流水线。从研发云平台 REST API 拉取故障工单，经过文本预处理、向量 Embedding，通过 HDBSCAN 密度聚类发现相似问题簇，结合开发规范进行违规检测，最终生成根因分析和改进建议——全程无需预定义标签。

## Core Values
1. **Quality**: 通过 TDD、Clean Code、SOLID 原则保证代码质量
2. **Clarity**: 编写自文档代码，变量/函数命名揭示意图
3. **Testability**: 所有代码先写测试（TDD），覆盖率 ≥ 79.9%
4. **Maintainability**: 遵循 Clean Architecture，保持模块边界清晰
5. **Collaboration**: 使用 SDD 确保需求→设计→任务→代码的全程可追溯

## Development Principles

### SDD (Specification-Driven Development)
- 每个新功能从 `.speckit/specify.md` 的规格说明开始
- Specification 描述 WHAT（做什么），不描述 HOW（怎么做）
- Plan 将规格翻译为技术设计
- Tasks 将实现分解为具体可执行步骤
- Analysis 确保规格、计划、任务三者一致

### TDD (Test-Driven Development)
- 先写失败的测试，再写让测试通过的实现代码
- 只写让当前测试通过的最少代码
- 通过后立即重构，保持代码整洁
- 所有代码必须有对应测试

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
- **Entities**：纯业务规则（`src/core/models.py`，Pydantic 数据模型）
- **Use Cases**：编排实体（`src/analyzer/`，`src/analysis/`）
- **Interface Adapters**：数据转换（`src/api/`，`src/cli/`，`src/ui/`）
- **Frameworks**：外部工具（LLM SDK、HDBSCAN、ChromaDB、SQLite）

## Python Standards

### Toolchain
| 工具 | 用途 | 命令 |
|------|------|------|
| **Ruff** | Linter + Formatter | `ruff check src/ tests/` / `ruff format src/ tests/` |
| **Pyright** | 类型检查 | `pyright src/` 或 `mypy src/` |
| **Pytest** | 测试 + 覆盖率 | `pytest tests/ -v --cov=src` |

### Workflow
1. Before writing code:
   - Create specification in `specify.md`
   - Create plan in `plan.md`
   - Create tasks in `tasks.md`

2. During development:
   - Follow TDD: Write test → Implement → Refactor
   - Run linter: `ruff check src/ tests/`
   - Run formatter: `ruff format src/ tests/`
   - Run type checker: `mypy src/`
   - Run tests: `pytest tests/ -v --cov=src`

3. Before committing:
   - Update `analyze.md` to ensure consistency
   - Run all quality checks
   - Review code using `code-review-checklist.md`

## Repository Structure
```
fault-review-analyzer/
├── .speckit/                    # SDD workflow
│   ├── constitution.md          # This file
│   ├── specify.md               # Feature specifications
│   ├── plan.md                  # Implementation plans
│   ├── tasks.md                 # Task breakdown
│   └── analyze.md               # Consistency analysis
├── src/                         # Source code
│   ├── api/                     # REST API client
│   ├── cache/                   # SQLite cache layer
│   ├── config/                  # Configuration management
│   ├── core/                    # Shared data models
│   ├── preprocessor/            # Text preprocessing
│   ├── embedding/               # Vector embedding generation
│   ├── clustering/              # HDBSCAN clustering
│   ├── analyzer/                # Pipeline orchestration
│   ├── analysis/                # Analysis modules
│   ├── storage/                 # ChromaDB management
│   ├── rules/                   # Violation detection engine
│   ├── knowledge/               # Development standards
│   ├── report/                  # Report generation
│   ├── visualization/           # Charts and scatter plots
│   ├── cli/                     # CLI commands
│   └── ui/                      # Streamlit dashboard
├── tests/                       # Tests (mirrors src/)
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scripts/                     # Batch scripts
├── data/                        # Data storage
│   ├── chroma/                  # ChromaDB
│   ├── standards/               # Dev standards JSON
│   └── rules/custom/            # Custom rules
├── docs/                        # Documentation
├── config/                      # Configuration files
├── code-review-checklist.md     # Code review checklist
├── .gitignore
├── pyproject.toml               # Project config + dependencies
└── CLAUDE.md                    # Project instructions
```

## Commit Guidelines

### Commit Message Format
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

All code must pass:
- [ ] All tests pass (`pytest tests/ -v --cov=src`)
- [ ] Test coverage ≥ 79.9%
- [ ] Linter passes with no errors (`ruff check src/ tests/`)
- [ ] Code is formatted (`ruff format src/ tests/`)
- [ ] Type checking passes (`mypy src/`)
- [ ] Code review checklist is complete
- [ ] SDD documents are updated

## Communication

### Channels
- **Feature Requests**: `specify.md`
- **Technical Discussion**: `plan.md`
- **Task Assignment**: `tasks.md`
- **Progress Tracking**: `tasks.md`

### Review Process
1. Create/update `specify.md` with requirements
2. Create/update `plan.md` with technical design
3. Create/update `tasks.md` with task breakdown
4. Implement following TDD
5. Update `analyze.md` to verify consistency
6. Code review using code-review-checklist.md

## Continuous Improvement

This constitution is a living document. If you find areas for improvement:
1. Document the issue in `specify.md`
2. Propose changes in `plan.md`
3. Discuss with team
4. Update constitution
5. Communicate changes to team

## Version
Version: 2.0
Last Updated: 2026-03-30

---

**Remember**: The goal is to build maintainable, testable, and high-quality software. These principles and standards help us achieve that goal together.