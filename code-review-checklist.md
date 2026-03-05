# Code Review Checklist

> 提交代码前，使用本清单确保代码质量。Python 项目专版。

## General

- [ ] 代码遵循项目编码规范（snake_case 变量、Pydantic v2、类型注解）
- [ ] 代码已格式化（`ruff format src/ tests/`）
- [ ] 没有未附说明的 TODO / FIXME / HACK 注释
- [ ] 没有注释掉的死代码
- [ ] 没有未使用的 import 或变量
- [ ] 没有无法到达的死代码
- [ ] Git commit message 清晰，遵循 Conventional Commits 格式

---

## Clean Code

### Naming
- [ ] 变量、函数、类名描述性强，揭示意图
- [ ] 命名可发音、可搜索
- [ ] 不使用缩写（除非广为人知，如 `id`、`url`、`api`）
- [ ] 布尔变量使用 `is_`、`has_`、`should_` 前缀
- [ ] 集合变量名用复数（`tasks`、`commits`、`labels`）

### Functions
- [ ] 函数短小（理想 < 20 行）
- [ ] 函数只做一件事
- [ ] 函数名为动词或动词短语，清晰描述行为
- [ ] 参数不超过 4 个
- [ ] 没有控制行为的布尔参数（flag arguments）
- [ ] 返回值类型一致

### Classes
- [ ] 类名为名词
- [ ] 类职责单一，不是"上帝类"
- [ ] 公开方法最少，内部逻辑私有

### Comments
- [ ] 注释解释"为什么"，不解释"是什么"
- [ ] 没有重述代码的冗余注释
- [ ] 过时注释已删除或更新
- [ ] 复杂算法有解释性注释

### Code Duplication
- [ ] 没有重复代码（DRY）
- [ ] 相似逻辑已提取为共享函数

---

## SOLID Principles

### Single Responsibility Principle (SRP)
- [ ] 类/模块只有一个变化原因
- [ ] 类/模块只有一个职责

### Open/Closed Principle (OCP)
- [ ] 新功能通过扩展实现，而非修改已有代码

### Liskov Substitution Principle (LSP)
- [ ] 子类型可以无缝替代基类型

### Interface Segregation Principle (ISP)
- [ ] 接口/抽象类小而专一

### Dependency Inversion Principle (DIP)
- [ ] 依赖抽象（Protocol / ABC），不依赖具体实现
- [ ] 依赖通过构造函数注入，不在内部创建

---

## Clean Architecture

### Dependency Rule
- [ ] 依赖方向只能向内（外层依赖内层，内层不依赖外层）
- [ ] CLI / Framework 层不泄漏进业务逻辑

### Layers（本项目）
- [ ] `src/api/models.py`：纯数据模型，无外部依赖
- [ ] `src/preprocessor/`、`src/embedding/`、`src/clustering/`：业务逻辑，只依赖内层
- [ ] `src/cli/`、`src/config/`、`src/cache/`：接口适配层
- [ ] OpenAI SDK、HDBSCAN 等仅在最外层使用

### Testing
- [ ] 业务逻辑可脱离外部依赖独立测试（Mock / Fake）
- [ ] 测试覆盖所有层

---

## TDD (Test-Driven Development)

### Test Coverage
- [ ] 新代码有对应测试
- [ ] 测试覆盖正常路径（happy path）
- [ ] 测试覆盖错误路径（异常、边界输入）
- [ ] 关键/复杂代码覆盖率 ≥ 80%（`pytest --cov=src --cov-fail-under=80`）

### Test Quality
- [ ] 测试可读，描述行为而非实现细节
- [ ] 测试相互独立（可以任意顺序运行）
- [ ] 测试确定性（无 flaky test）
- [ ] 遵循 Arrange-Act-Assert 模式
- [ ] 测试名称描述被测场景

### Test Organization
- [ ] 测试组织合理（按 class 或功能分组）
- [ ] 使用 `conftest.py` 共享 fixtures，不在类内重复定义
- [ ] 慢速测试（需要真实网络/DB）与快速单元测试分离

### Async Tests
- [ ] 异步测试无需 `@pytest.mark.asyncio`（已配置 `asyncio_mode = "auto"`）
- [ ] 网络调用、`asyncio.sleep` 均已 mock

---

## Error Handling

### Exceptions
- [ ] 错误使用具体异常类型，不捕获裸 `Exception`
- [ ] 错误信息描述性强，包含上下文
- [ ] 资源在 `finally` 或 `with` 中清理（context manager）
- [ ] 异步资源使用 `async with` / `__aexit__`

### Validation
- [ ] 在系统边界（用户输入、API 响应）进行输入校验
- [ ] Optional 字段有明确的 `None` 处理
- [ ] Pydantic 模型使用 v2 风格（`model_config = ConfigDict(...)`）

### Logging
- [ ] 重要事件已记录（loguru）
- [ ] 日志不包含敏感信息（API key、token）
- [ ] 日志级别合适（DEBUG/INFO/WARNING/ERROR）

---

## Performance

### Efficiency
- [ ] 没有明显的低效算法
- [ ] OpenAI API 调用批量处理（`embed_batch`）
- [ ] 大数据集分批处理，不全量加载到内存

### Resource Management
- [ ] `httpx.AsyncClient` 通过 `async with` 管理，不泄漏
- [ ] SQLite 连接正确关闭
- [ ] Embedding 生成异常时不产生零向量

---

## Security

### Secrets Management
- [ ] API key / token 不硬编码在代码中
- [ ] 敏感信息从环境变量或 `config.yaml` 读取
- [ ] 密钥不出现在日志或错误信息中

---

## Python Specific

- [ ] 代码通过 `ruff check src/ tests/`（Linting）
- [ ] 代码通过 `ruff format src/ tests/`（Formatting）
- [ ] 代码通过 `mypy src/`（Type checking）
- [ ] 函数签名有类型注解
- [ ] 使用 f-string 进行字符串格式化
- [ ] 资源管理使用 `with` / `async with`（context manager）
- [ ] 没有不必要的 `type: ignore` 注释

---

## Code Smells

- [ ] 没有超长方法（> 50 行）
- [ ] 没有超大类（> 300 行）
- [ ] 没有过长参数列表（> 4 个）
- [ ] 没有魔法数字（使用具名常量）
- [ ] 没有深层嵌套条件（提取为函数）
- [ ] 没有上帝类（God class）

---

## Pre-Commit Checklist

提交前确认：

```bash
ruff check src/ tests/        # Linting 无错误
ruff format src/ tests/       # 格式化
mypy src/                     # 类型检查通过
pytest tests/ -v --cov=src    # 测试通过，覆盖率 ≥ 80%
```

- [ ] 所有测试通过
- [ ] 覆盖率 ≥ 80%
- [ ] 代码审查清单核心项已确认
- [ ] SDD 文档已更新（如有架构变更）

---

## Reviewer's Notes

**Reviewer**: ________________________
**Date**: ________________________
**Overall Assessment**:
- [ ] Approve
- [ ] Request Changes
- [ ] Comment Only

**Strengths**:
-
-

**Issues**:
-
-

---

## References
- [SDD 工作流](.speckit/constitution.md)
- [架构说明](CLAUDE.md)
- [代码审查报告](review/code_review.md)
