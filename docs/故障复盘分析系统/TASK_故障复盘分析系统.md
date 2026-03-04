# 故障复盘分析系统 - 原子任务拆分

## 一、任务概览

```
Phase 1: 项目初始化
├── TASK-001: 项目结构创建
├── TASK-002: 依赖配置
└── TASK-003: 配置模块开发

Phase 2: 基础设施层
├── TASK-004: API客户端开发
├── TASK-005: 缓存模块开发
└── TASK-006: 日志与工具模块

Phase 3: 核心分析引擎
├── TASK-007: 数据预处理模块
├── TASK-008: Embedding模块
├── TASK-009: 聚类分析模块
├── TASK-010: 标签生成模块
└── TASK-011: 根因推理模块

Phase 4: 规范引擎
├── TASK-012: 规范引擎开发
└── TASK-013: 内置规范定义

Phase 5: 报告生成
├── TASK-014: 报告模板设计
└── TASK-015: 报告生成器开发

Phase 6: CLI接口
├── TASK-016: CLI框架搭建
├── TASK-017: fetch命令开发
├── TASK-018: analyze命令开发
├── TASK-019: report命令开发
└── TASK-020: config/cache命令开发

Phase 7: 测试与文档
├── TASK-021: 单元测试
├── TASK-022: 集成测试
└── TASK-023: 使用文档
```

---

## 二、TDD开发流程（每个任务必遵循）

```
┌─────────────────────────────────────────────────────────────┐
│                     TDD 开发循环                             │
│                                                              │
│    ┌──────────┐      ┌──────────┐      ┌──────────┐        │
│    │  RED     │ ──→  │  GREEN   │ ──→  │ REFACTOR │        │
│    │ 编写测试  │      │ 编写代码  │      │  重构    │        │
│    │ (失败)   │      │ (通过)   │      │ (优化)   │        │
│    └──────────┘      └──────────┘      └──────────┘        │
│         ↑                                     │              │
│         └─────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### 每个任务执行步骤：

1. **RED - 编写测试用例**
   - 根据验收标准编写测试用例
   - 运行 `pytest tests/test_xxx.py -v`，确认测试失败
   
2. **GREEN - 编写实现代码**
   - 编写最少代码使测试通过
   - 运行测试确认通过
   
3. **REFACTOR - 重构优化**
   - 优化代码结构、命名、注释
   - 运行测试确保仍然通过

4. **提交前检查**
   ```bash
   pytest tests/ -v --cov=src --cov-fail-under=80
   ruff check src/ tests/
   ruff format src/ tests/ --check
   mypy src/
   ```

---

## 三、详细任务定义

### Phase 1: 项目初始化

---

#### TASK-001: 项目结构创建

**描述**: 创建项目基础目录结构和文件

**TDD执行步骤**:
1. 创建目录结构
2. 创建 `__init__.py` 文件
3. 创建 `.gitignore` 文件
4. 创建基础 `README.md`

**输入契约**:
- 架构设计文档

**输出契约**:
- 完整的项目目录结构
- `__init__.py` 文件
- `.gitignore` 文件
- `README.md` 文件

**实现约束**:
- 使用 Python 3.10+ 特性
- 遵循 src layout 布局

**依赖关系**: 无

**验收标准**:
- [ ] 目录结构符合设计文档
- [ ] 所有包有 `__init__.py`
- [ ] `.gitignore` 包含常见忽略项

---

#### TASK-002: 依赖配置

**描述**: 配置项目依赖和开发环境

**TDD执行步骤**:
1. 创建 `pyproject.toml`
2. 创建 `.env.example`
3. 创建 `.pre-commit-config.yaml`
4. 测试：`pip install -e ".[dev]"` 成功

**输入契约**:
- 技术选型清单

**输出契约**:
- `pyproject.toml` 文件
- `.env.example` 文件
- `.pre-commit-config.yaml` 文件

**实现约束**:
- 使用 pyproject.toml 管理依赖
- 区分生产依赖和开发依赖
- 配置 ruff + mypy + pytest

**依赖关系**: TASK-001

**验收标准**:
- [ ] 所有依赖正确声明
- [ ] `pip install -e ".[dev]"` 可正常安装
- [ ] `.env.example` 包含所有必要配置项
- [ ] pre-commit 钩子可安装

---

#### TASK-003: 配置模块开发

**描述**: 开发配置管理模块

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/test_config.py
   def test_load_config_from_yaml():
       """测试从YAML文件加载配置"""
       
   def test_env_override_config():
       """测试环境变量覆盖配置"""
       
   def test_config_validation():
       """测试配置验证"""
   ```
2. **GREEN**: 实现配置模块
3. **REFACTOR**: 优化代码结构

**输入契约**:
- 配置结构设计

**输出契约**:
- `src/config/` 模块
- 配置模型定义
- 配置加载逻辑

**实现约束**:
- 使用 Pydantic 进行配置验证
- 支持环境变量覆盖
- 支持多环境配置

**依赖关系**: TASK-001, TASK-002

**验收标准**:
- [ ] 配置可从 YAML 文件加载
- [ ] 环境变量可覆盖配置
- [ ] 配置验证正确工作
- [ ] 单元测试通过
- [ ] 覆盖率 ≥ 80%

---

### Phase 2: 基础设施层

---

#### TASK-004: API客户端开发

**描述**: 开发研发管理系统API客户端

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/test_api_client.py
   @pytest.mark.asyncio
   async def test_get_task_detail():
       """测试获取任务详情"""
       
   @pytest.mark.asyncio
   async def test_authentication():
       """测试认证机制"""
       
   @pytest.mark.asyncio
   async def test_retry_on_failure():
       """测试失败重试"""
       
   @pytest.mark.asyncio
   async def test_error_handling():
       """测试错误处理"""
   ```
2. **GREEN**: 实现API客户端
3. **REFACTOR**: 优化代码结构

**输入契约**:
- OpenAPI文档
- API接口规范

**输出契约**:
- `src/api/` 模块
- API客户端类
- 数据模型定义
- 异常处理

**实现约束**:
- 使用 httpx 作为HTTP客户端
- 支持异步调用
- 实现重试机制
- 支持Bearer Token认证

**依赖关系**: TASK-003

**验收标准**:
- [ ] 可获取任务详情
- [ ] 可获取代码提交记录
- [ ] 认证机制正确
- [ ] 错误处理完善
- [ ] 单元测试通过
- [ ] 覆盖率 ≥ 80%

---

#### TASK-005: 缓存模块开发

**描述**: 开发本地缓存模块

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/test_cache.py
   def test_save_and_load_cache():
       """测试缓存存储和读取"""
       
   def test_cache_ttl():
       """测试TTL过期机制"""
       
   def test_cache_invalidation():
       """测试缓存失效"""
       
   def test_cache_index():
       """测试缓存索引查询"""
   ```
2. **GREEN**: 实现缓存模块
3. **REFACTOR**: 优化代码结构

**输入契约**:
- 缓存策略设计

**输出契约**:
- `src/cache/` 模块
- 缓存管理器
- SQLite存储实现
- 缓存索引

**实现约束**:
- 使用 SQLite 作为存储后端
- 支持TTL过期
- 支持缓存失效

**依赖关系**: TASK-003

**验收标准**:
- [ ] 可存储和读取缓存数据
- [ ] TTL机制正确工作
- [ ] 缓存索引可查询
- [ ] 单元测试通过
- [ ] 覆盖率 ≥ 80%

---

#### TASK-006: 日志与工具模块

**描述**: 开发日志和通用工具模块

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/test_utils.py
   def test_logger_configuration():
       """测试日志配置"""
       
   def test_helper_functions():
       """测试工具函数"""
   ```
2. **GREEN**: 实现日志和工具模块
3. **REFACTOR**: 优化代码结构

**输入契约**:
- 无

**输出契约**:
- `src/utils/logger.py` 日志模块
- `src/utils/helpers.py` 工具函数

**实现约束**:
- 使用 loguru 作为日志库
- 支持日志级别配置
- 支持日志文件输出

**依赖关系**: TASK-002

**验收标准**:
- [ ] 日志可配置
- [ ] 工具函数可用
- [ ] 单元测试通过
- [ ] 覆盖率 ≥ 80%

---

### Phase 3: 核心分析引擎

---

#### TASK-007: 数据预处理模块

**描述**: 开发数据预处理模块

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/test_preprocessor.py
   def test_extract_key_info():
       """测试关键信息提取"""
       
   def test_clean_data():
       """测试数据清洗"""
       
   def test_normalize_format():
       """测试数据标准化"""
   ```
2. **GREEN**: 实现预处理模块
3. **REFACTOR**: 优化代码结构

**输入契约**:
- 故障数据模型

**输出契约**:
- `src/analyzer/preprocessor/` 模块
- 数据清洗器
- 数据标准化器
- 信息提取器

**实现约束**:
- 提取关键信息：标题、描述、日志、代码变更
- 清洗无效数据
- 标准化数据格式

**依赖关系**: TASK-004, TASK-005

**验收标准**:
- [ ] 可提取关键信息
- [ ] 数据清洗正确
- [ ] 输出格式标准化
- [ ] 单元测试通过
- [ ] 覆盖率 ≥ 80%

---

#### TASK-008: Embedding模块

**描述**: 开发文本向量化模块

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/test_embedding.py
   @pytest.mark.asyncio
   async def test_openai_embedding():
       """测试OpenAI Embedding"""
       
   @pytest.mark.asyncio
   async def test_bge_embedding():
       """测试BGE Embedding"""
       
   @pytest.mark.asyncio
   async def test_batch_embedding():
       """测试批量向量化"""
   ```
2. **GREEN**: 实现Embedding模块
3. **REFACTOR**: 优化代码结构

**输入契约**:
- 预处理后的数据

**输出契约**:
- `src/analyzer/embedding/` 模块
- OpenAI Embedding Provider
- BGE Embedding Provider
- Embedding管理器

**实现约束**:
- 支持多种Embedding模型
- 可配置切换
- 支持批量处理

**依赖关系**: TASK-003, TASK-007

**验收标准**:
- [ ] OpenAI Embedding可用
- [ ] BGE Embedding可用
- [ ] 批量处理正确
- [ ] 单元测试通过
- [ ] 覆盖率 ≥ 80%

---

#### TASK-009: 聚类分析模块

**描述**: 开发聚类分析模块

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/test_clustering.py
   def test_hdbscan_clustering():
       """测试HDBSCAN聚类"""
       
   def test_topic_extraction():
       """测试主题提取"""
       
   def test_similarity_calculation():
       """测试相似度计算"""
   ```
2. **GREEN**: 实现聚类模块
3. **REFACTOR**: 优化代码结构

**输入契约**:
- 文本向量

**输出契约**:
- `src/analyzer/clustering/` 模块
- HDBSCAN聚类实现
- 主题提取
- 相似度计算

**实现约束**:
- 使用 HDBSCAN 算法
- 支持参数配置
- 输出聚类标签和概率

**依赖关系**: TASK-008

**验收标准**:
- [ ] 聚类结果正确
- [ ] 可提取聚类主题
- [ ] 相似度计算正确
- [ ] 单元测试通过
- [ ] 覆盖率 ≥ 80%

---

#### TASK-010: 标签生成模块

**描述**: 开发标签生成模块

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/test_labeling.py
   @pytest.mark.asyncio
   async def test_generate_tags():
       """测试标签生成"""
       
   def test_tag_deduplication():
       """测试标签去重"""
       
   def test_tag_merging():
       """测试标签合并"""
   ```
2. **GREEN**: 实现标签生成模块
3. **REFACTOR**: 优化代码结构

**输入契约**:
- 预处理后的数据
- LLM Provider

**输出契约**:
- `src/analyzer/labeling/` 模块
- 标签生成器
- 标签管理器

**实现约束**:
- 使用 LLM 生成技术标签
- 标签数量可配置
- 支持标签去重和合并

**依赖关系**: TASK-003, TASK-007

**验收标准**:
- [ ] 可生成技术标签
- [ ] 标签质量合理
- [ ] 单元测试通过
- [ ] 覆盖率 ≥ 80%

---

#### TASK-011: 根因推理模块

**描述**: 开发根因推理模块

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/test_reasoning.py
   @pytest.mark.asyncio
   async def test_technical_root_cause():
       """测试技术根因分析"""
       
   @pytest.mark.asyncio
   async def test_process_root_cause():
       """测试过程根因分析"""
       
   @pytest.mark.asyncio
   async def test_suggestion_generation():
       """测试建议生成"""
   ```
2. **GREEN**: 实现根因推理模块
3. **REFACTOR**: 优化代码结构

**输入契约**:
- 预处理数据
- 标签信息
- 规范引擎

**输出契约**:
- `src/analyzer/reasoning/` 模块
- 根因分析器
- 规范检查器
- 建议生成器

**实现约束**:
- 使用 LLM 进行根因推理
- 多层次根因分析（技术/过程/管理）
- 基于规范生成改进建议

**依赖关系**: TASK-010, TASK-012

**验收标准**:
- [ ] 可分析技术根因
- [ ] 可分析过程根因
- [ ] 可生成改进建议
- [ ] 单元测试通过
- [ ] 覆盖率 ≥ 80%

---

### Phase 4: 规范引擎

---

#### TASK-012: 规范引擎开发

**描述**: 开发规范检查引擎（预留公司定制规范接口）

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/test_rules.py
   def test_load_rules_from_yaml():
       """测试从YAML加载规范"""
       
   def test_check_rule_violation():
       """测试规范冲突检查"""
       
   def test_custom_rule_loader():
       """测试自定义规范加载器"""
   ```
2. **GREEN**: 实现规范引擎
3. **REFACTOR**: 优化代码结构

**输入契约**:
- 规范文档结构设计

**输出契约**:
- `src/rules/` 模块
- 规范加载器接口（IRuleLoader）
- 内置规范加载器
- 自定义规范加载器
- 规范检查器
- 规范管理器

**实现约束**:
- 支持 YAML 格式规范文档
- 支持正则匹配
- 支持自定义规范
- 预留公司定制规范扩展接口

**依赖关系**: TASK-003

**验收标准**:
- [ ] 可加载规范文档
- [ ] 可检查规范冲突
- [ ] 支持自定义规范
- [ ] 公司定制规范接口预留
- [ ] 单元测试通过
- [ ] 覆盖率 ≥ 80%

---

#### TASK-013: 内置规范定义

**描述**: 定义内置的研发规范

**TDD执行步骤**:
1. 创建规范YAML文件
2. 编写测试验证规范可加载
3. 验证规范格式正确

**输入契约**:
- 通用研发规范知识

**输出契约**:
- `src/rules/builtin/` 规范文件
- 编码规范
- 安全规范
- 性能规范

**实现约束**:
- 规范可配置开关
- 规范有明确的ID和描述

**依赖关系**: TASK-012

**验收标准**:
- [ ] 至少包含10条内置规范
- [ ] 规范格式正确
- [ ] 可被规范引擎加载

---

### Phase 5: 报告生成

---

#### TASK-014: 报告模板设计

**描述**: 设计分析报告模板

**TDD执行步骤**:
1. 创建Jinja2模板文件
2. 编写测试验证模板渲染
3. 验证输出格式正确

**输入契约**:
- 报告内容需求

**输出契约**:
- `src/report/templates/` 模板文件
- 单个分析报告模板
- 批量分析报告模板
- 聚类报告模板

**实现约束**:
- 使用 Jinja2 模板引擎
- Markdown 格式输出

**依赖关系**: TASK-001

**验收标准**:
- [ ] 模板格式正确
- [ ] 包含所有必要字段
- [ ] 渲染输出美观

---

#### TASK-015: 报告生成器开发

**描述**: 开发报告生成器

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/test_report.py
   def test_generate_single_report():
       """测试生成单个分析报告"""
       
   def test_generate_batch_report():
       """测试生成批量分析报告"""
       
   def test_generate_cluster_report():
       """测试生成聚类报告"""
   ```
2. **GREEN**: 实现报告生成器
3. **REFACTOR**: 优化代码结构

**输入契约**:
- 分析结果
- 报告模板

**输出契约**:
- `src/report/` 模块
- 报告生成器
- 报告导出器

**实现约束**:
- 支持 Markdown 输出
- 支持自定义输出目录
- 支持文件命名规则

**依赖关系**: TASK-014, TASK-011

**验收标准**:
- [ ] 可生成单个分析报告
- [ ] 可生成批量分析报告
- [ ] 可生成聚类报告
- [ ] 单元测试通过
- [ ] 覆盖率 ≥ 80%

---

### Phase 6: CLI接口

---

#### TASK-016: CLI框架搭建

**描述**: 搭建命令行界面框架

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/test_cli.py
   def test_cli_help():
       """测试帮助信息"""
       
   def test_cli_version():
       """测试版本信息"""
       
   def test_subcommands_registered():
       """测试子命令注册"""
   ```
2. **GREEN**: 实现CLI框架
3. **REFACTOR**: 优化代码结构

**输入契约**:
- 命令设计规范

**输出契约**:
- `src/cli/` 模块
- CLI入口点
- 命令注册

**实现约束**:
- 使用 typer 框架
- 支持子命令
- 支持帮助信息

**依赖关系**: TASK-003

**验收标准**:
- [ ] `fault-analyzer --help` 可用
- [ ] 子命令注册正确
- [ ] 帮助信息清晰
- [ ] 单元测试通过
- [ ] 覆盖率 ≥ 80%

---

#### TASK-017: fetch命令开发

**描述**: 开发数据获取命令

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/test_cli_fetch.py
   def test_fetch_single_task():
       """测试获取单个任务"""
       
   def test_fetch_batch_tasks():
       """测试批量获取任务"""
       
   def test_fetch_with_cache():
       """测试缓存机制"""
   ```
2. **GREEN**: 实现fetch命令
3. **REFACTOR**: 优化代码结构

**输入契约**:
- API客户端
- 缓存模块

**输出契约**:
- `src/cli/commands/fetch.py`
- fetch命令实现

**实现约束**:
- 支持单个获取
- 支持批量获取
- 支持强制刷新

**依赖关系**: TASK-016, TASK-004, TASK-005

**验收标准**:
- [ ] 可获取单个任务
- [ ] 可批量获取任务
- [ ] 缓存机制正确
- [ ] 进度显示友好
- [ ] 单元测试通过
- [ ] 覆盖率 ≥ 80%

---

#### TASK-018: analyze命令开发

**描述**: 开发数据分析命令

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/test_cli_analyze.py
   def test_analyze_single_task():
       """测试分析单个任务"""
       
   def test_analyze_batch_tasks():
       """测试批量分析任务"""
       
   def test_analyze_with_clustering():
       """测试聚类分析"""
   ```
2. **GREEN**: 实现analyze命令
3. **REFACTOR**: 优化代码结构

**输入契约**:
- 分析引擎
- 缓存模块

**输出契约**:
- `src/cli/commands/analyze.py`
- analyze命令实现

**实现约束**:
- 支持单个分析
- 支持批量分析
- 支持聚类分析

**依赖关系**: TASK-016, TASK-011

**验收标准**:
- [ ] 可分析单个任务
- [ ] 可批量分析任务
- [ ] 聚类分析正确
- [ ] 进度显示友好
- [ ] 单元测试通过
- [ ] 覆盖率 ≥ 80%

---

#### TASK-019: report命令开发

**描述**: 开发报告生成命令

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/test_cli_report.py
   def test_generate_report():
       """测试生成报告"""
       
   def test_output_directory():
       """测试输出目录"""
   ```
2. **GREEN**: 实现report命令
3. **REFACTOR**: 优化代码结构

**输入契约**:
- 报告生成器
- 分析结果

**输出契约**:
- `src/cli/commands/report.py`
- report命令实现

**实现约束**:
- 支持指定输出目录
- 支持指定报告格式

**依赖关系**: TASK-016, TASK-015

**验收标准**:
- [ ] 可生成报告
- [ ] 输出目录正确
- [ ] 文件命名规范
- [ ] 单元测试通过
- [ ] 覆盖率 ≥ 80%

---

#### TASK-020: config/cache命令开发

**描述**: 开发配置和缓存管理命令

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/test_cli_config.py
   def test_config_list():
       """测试配置列表"""
       
   def test_config_set():
       """测试配置设置"""
       
   # tests/test_cli_cache.py
   def test_cache_list():
       """测试缓存列表"""
       
   def test_cache_clear():
       """测试缓存清理"""
   ```
2. **GREEN**: 实现config/cache命令
3. **REFACTOR**: 优化代码结构

**输入契约**:
- 配置模块
- 缓存模块

**输出契约**:
- `src/cli/commands/config.py`
- `src/cli/commands/cache.py`

**实现约束**:
- 支持查看/设置配置
- 支持查看/清理缓存

**依赖关系**: TASK-016, TASK-003, TASK-005

**验收标准**:
- [ ] config命令可用
- [ ] cache命令可用
- [ ] 帮助信息清晰
- [ ] 单元测试通过
- [ ] 覆盖率 ≥ 80%

---

### Phase 7: 测试与文档

---

#### TASK-021: 单元测试完善

**描述**: 完善单元测试，确保覆盖率达标

**TDD执行步骤**:
1. 运行覆盖率报告
2. 补充缺失的测试用例
3. 确保覆盖率 ≥ 80%

**输入契约**:
- 所有模块代码

**输出契约**:
- 完整的单元测试套件
- 测试覆盖率报告

**实现约束**:
- 使用 pytest 框架
- 测试覆盖率 ≥ 80%

**依赖关系**: TASK-001 ~ TASK-020

**验收标准**:
- [ ] 所有测试通过
- [ ] 覆盖率 ≥ 80%
- [ ] 边界情况覆盖

---

#### TASK-022: 集成测试

**描述**: 编写集成测试

**TDD执行步骤**:
1. **RED**: 编写测试用例
   ```python
   # tests/integration/test_workflow.py
   async def test_full_workflow():
       """测试完整工作流：fetch -> analyze -> report"""
       
   async def test_batch_analysis_workflow():
       """测试批量分析工作流"""
   ```
2. **GREEN**: 实现集成测试
3. **REFACTOR**: 优化测试代码

**输入契约**:
- 完整系统

**输出契约**:
- 集成测试用例
- E2E测试脚本

**实现约束**:
- 测试完整工作流
- 使用 Mock 数据

**依赖关系**: TASK-021

**验收标准**:
- [ ] 完整流程测试通过
- [ ] 边界情况处理正确

---

#### TASK-023: 使用文档

**描述**: 编写使用文档

**输入契约**:
- 完整系统

**输出契约**:
- README.md 更新
- 使用示例
- 配置说明

**实现约束**:
- 包含安装说明
- 包含使用示例
- 包含配置说明

**依赖关系**: TASK-001 ~ TASK-022

**验收标准**:
- [ ] 安装说明清晰
- [ ] 使用示例完整
- [ ] 配置说明详细

---

## 四、任务依赖关系图

```
TASK-001 ─┬─→ TASK-002 ─┬─→ TASK-003 ─┬─→ TASK-004 ─→ TASK-007 ─→ TASK-008 ─→ TASK-009
          │             │             │                                      │
          │             │             ├─→ TASK-005 ────────────────────────────┤
          │             │             │                                      │
          │             │             ├─→ TASK-006                            │
          │             │             │                                      │
          │             │             ├─→ TASK-012 ─→ TASK-013 ───────────────┼─→ TASK-011 ─→ TASK-015 ─→ TASK-019
          │             │             │                                      │
          │             │             └─→ TASK-016 ─┬─→ TASK-017              │
          │             │                           │                         │
          │             │                           ├─→ TASK-018 ─────────────┘
          │             │                           │
          │             │                           ├─→ TASK-019
          │             │                           │
          │             │                           └─→ TASK-020
          │             │
          │             └─→ TASK-014 ──────────────────────────→ TASK-015
          │
          └─→ TASK-021 ─→ TASK-022 ─→ TASK-023
```

---

## 五、执行检查清单

### 5.1 完整性检查
- [ ] 所有模块都有对应任务
- [ ] 所有任务都有输入/输出契约
- [ ] 所有任务都有验收标准
- [ ] 所有任务都有TDD执行步骤

### 5.2 一致性检查
- [ ] 任务依赖关系无循环
- [ ] 接口契约与设计文档一致
- [ ] 技术选型与依赖配置一致

### 5.3 可行性检查
- [ ] 每个任务可在1-2天内完成
- [ ] 任务边界清晰
- [ ] 依赖关系合理

### 5.4 可控性检查
- [ ] 每个任务有明确的验收标准
- [ ] 任务可独立测试
- [ ] 任务可增量交付

### 5.5 可测性检查
- [ ] 每个模块可独立测试
- [ ] 测试用例可设计
- [ ] 验收标准可验证

---

## 六、下一步

进入 **阶段5: Automate (自动化执行)**，按任务顺序开始开发。
