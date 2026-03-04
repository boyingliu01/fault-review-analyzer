# 故障复盘分析系统 - 架构设计文档

## 一、系统架构概览

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户层 (CLI)                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  fetch      │  │  analyze    │  │  report     │  │  config             │ │
│  │  获取数据   │  │  分析数据   │  │  生成报告   │  │  配置管理           │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              应用层 (Core)                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         分析引擎 (Analyzer)                          │    │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────────┐ │    │
│  │  │ 数据预处理 │→│ 特征提取  │→│ 聚类分析  │→│ 根因推理          │ │    │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌───────────────────┐    │
│  │ 规范引擎 (Rules)    │  │ 报告生成器 (Report) │  │ 知识库 (Knowledge)│    │
│  └─────────────────────┘  └─────────────────────┘  └───────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              基础设施层 (Infrastructure)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ API Client  │  │ Cache Mgr   │  │ LLM Client  │  │ Embedding Client    │ │
│  │ API客户端   │  │ 缓存管理   │  │ 大模型调用  │  │ 向量化服务          │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                          │
│  │ Config Mgr  │  │ Logger      │  │ File Handler│                          │
│  │ 配置管理   │  │ 日志服务   │  │ 文件处理   │                          │
│  └─────────────┘  └─────────────┘  └─────────────┘                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              外部服务层 (External)                           │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  │
│  │ 研发管理系统API     │  │ LLM服务             │  │ Embedding服务       │  │
│  │ (任务/缺陷数据)     │  │ (OpenAI/国产模型)   │  │ (向量化)            │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 数据流架构

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  数据源  │───▶│  采集层  │───▶│  缓存层  │───▶│  分析层  │───▶│  输出层  │
│          │    │          │    │          │    │          │    │          │
│ API/文件 │    │ 格式转换 │    │ 本地存储 │    │ 智能处理 │    │ 报告生成 │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

---

## 二、核心模块设计

### 2.1 CLI模块 (cli/)

```
cli/
├── __init__.py
├── main.py              # CLI入口点
├── commands/
│   ├── __init__.py
│   ├── fetch.py         # fetch命令 - 获取数据
│   ├── analyze.py       # analyze命令 - 分析数据
│   ├── report.py        # report命令 - 生成报告
│   ├── config.py        # config命令 - 配置管理
│   └── cache.py         # cache命令 - 缓存管理
└── utils/
    ├── __init__.py
    ├── output.py        # 输出格式化
    └── progress.py      # 进度显示
```

**命令设计**：

```bash
# 获取故障数据
fault-analyzer fetch --task-id 12345
fault-analyzer fetch --batch --query "status=resolved&date=2024-01"

# 分析故障
fault-analyzer analyze --task-id 12345                    # 单个分析
fault-analyzer analyze --batch --from-cache               # 批量分析
fault-analyzer analyze --cluster --min-samples 5          # 聚类分析

# 生成报告
fault-analyzer report --task-id 12345 --output ./reports/
fault-analyzer report --cluster 1 --output ./reports/

# 配置管理
fault-analyzer config set llm.provider openai
fault-analyzer config set llm.api_key sk-xxx
fault-analyzer config list

# 缓存管理
fault-analyzer cache list
fault-analyzer cache clear
```

### 2.2 API客户端模块 (api/)

```
api/
├── __init__.py
├── client.py            # API客户端基类
├── task_api.py          # 任务/缺陷API
├── user_api.py          # 用户API
├── code_api.py          # 代码提交API
├── models.py            # 数据模型定义
└── exceptions.py        # API异常定义
```

**数据模型**：

```python
class TaskInfo(BaseModel):
    task_id: int
    title: str
    description: str
    status: str
    priority: str
    create_time: datetime
    resolve_time: Optional[datetime]
    
    requirement: Optional[RequirementInfo]
    design: Optional[DesignInfo]
    development: Optional[DevelopmentInfo]
    testing: Optional[TestingInfo]
    production: Optional[ProductionInfo]

class DevelopmentInfo(BaseModel):
    commits: List[CommitInfo]
    code_changes: List[CodeChange]
    code_reviews: List[CodeReview]

class ProductionInfo(BaseModel):
    incident_time: datetime
    symptoms: str
    logs: List[str]
    stack_traces: List[str]
    resolution: str
    timeline: List[TimelineEvent]
```

### 2.3 缓存模块 (cache/)

```
cache/
├── __init__.py
├── manager.py           # 缓存管理器
├── storage.py           # 存储后端
├── models.py            # 缓存数据模型
└── index.py             # 缓存索引
```

**缓存策略**：

```python
class CacheManager:
    def get_task(self, task_id: int) -> Optional[TaskInfo]:
        """获取任务数据，优先从缓存读取"""
        
    def save_task(self, task: TaskInfo) -> None:
        """保存任务数据到缓存"""
        
    def get_cache_status(self, task_id: int) -> CacheStatus:
        """获取缓存状态：过期/有效/不存在"""
        
    def invalidate(self, task_id: Optional[int] = None) -> None:
        """使缓存失效"""
```

**存储结构**：

```
data/cache/
├── index.db             # SQLite索引数据库
├── tasks/
│   ├── 12345.json       # 任务详情
│   ├── 12346.json
│   └── ...
├── commits/
│   ├── abc123.json      # 代码提交详情
│   └── ...
└── metadata/
    └── sync_status.json # 同步状态记录
```

### 2.4 分析引擎模块 (analyzer/)

```
analyzer/
├── __init__.py
├── engine.py            # 分析引擎主类
├── preprocessor/        # 数据预处理
│   ├── __init__.py
│   ├── cleaner.py       # 数据清洗
│   ├── normalizer.py    # 数据标准化
│   └── extractor.py     # 信息提取
├── embedding/           # 向量化
│   ├── __init__.py
│   ├── base.py          # 基类
│   ├── openai.py        # OpenAI Embedding
│   ├── bge.py           # BGE模型
│   └── codebert.py      # CodeBERT模型
├── clustering/          # 聚类分析
│   ├── __init__.py
│   ├── hdbscan_cluster.py    # HDBSCAN聚类
│   ├── topic_model.py        # 主题建模
│   └── similarity.py         # 相似度计算
├── labeling/            # 标签生成
│   ├── __init__.py
│   ├── tag_generator.py      # 标签生成器
│   └── tag_manager.py        # 标签管理
└── reasoning/           # 根因推理
    ├── __init__.py
    ├── root_cause.py         # 根因分析
    ├── rule_checker.py       # 规范检查
    └── suggestion.py         # 建议生成
```

**分析流程**：

```python
class AnalysisEngine:
    async def analyze_single(self, task: TaskInfo) -> AnalysisResult:
        """单个故障分析"""
        # 1. 数据预处理
        preprocessed = await self.preprocessor.process(task)
        
        # 2. 特征提取
        features = await self.embedding.extract(preprocessed)
        
        # 3. 标签生成
        tags = await self.labeling.generate(preprocessed)
        
        # 4. 根因推理
        root_cause = await self.reasoning.analyze(preprocessed, tags)
        
        # 5. 规范检查
        violations = await self.reasoning.check_rules(preprocessed, root_cause)
        
        # 6. 生成建议
        suggestions = await self.reasoning.suggest(root_cause, violations)
        
        return AnalysisResult(
            task_id=task.task_id,
            tags=tags,
            root_cause=root_cause,
            violations=violations,
            suggestions=suggestions
        )
    
    async def analyze_batch(self, tasks: List[TaskInfo]) -> BatchAnalysisResult:
        """批量故障分析 + 聚类"""
        # 1. 批量预处理
        preprocessed_list = await self.preprocessor.process_batch(tasks)
        
        # 2. 批量向量化
        embeddings = await self.embedding.extract_batch(preprocessed_list)
        
        # 3. 聚类分析
        clusters = await self.clustering.cluster(embeddings)
        
        # 4. 为每个聚类生成主题
        topics = await self.clustering.extract_topics(clusters, preprocessed_list)
        
        # 5. 批量根因分析
        results = await self.reasoning.analyze_batch(clusters, preprocessed_list)
        
        return BatchAnalysisResult(
            clusters=clusters,
            topics=topics,
            results=results
        )
```

### 2.5 规范引擎模块 (rules/)

```
rules/
├── __init__.py
├── engine.py            # 规范引擎
├── loader.py            # 规范加载器
├── checker.py           # 规范检查器
├── builtin/             # 内置规范
│   ├── __init__.py
│   ├── coding.py        # 编码规范
│   ├── security.py      # 安全规范
│   └── performance.py   # 性能规范
└── custom/              # 用户自定义规范
    └── template.yaml    # 规范模板
```

**规范结构**：

```yaml
rule:
  id: "RULE-001"
  name: "SQL查询规范"
  category: "performance"
  description: "禁止在循环中执行SQL查询"
  patterns:
    - type: "code"
      regex: "for.*\\{.*executeQuery"
    - type: "log"
      regex: "N\\+1 query detected"
  severity: "high"
  suggestions:
    - "使用批量查询替代循环查询"
    - "考虑使用JOIN优化查询"
```

### 2.6 报告生成模块 (report/)

```
report/
├── __init__.py
├── generator.py         # 报告生成器
├── templates/           # 报告模板
│   ├── single.md.j2     # 单个分析报告模板
│   ├── batch.md.j2      # 批量分析报告模板
│   └── cluster.md.j2    # 聚类报告模板
└── exporter.py          # 报告导出
```

**报告模板示例**：

```markdown
# 故障复盘分析报告

## 基本信息
- **故障ID**: {{ task_id }}
- **故障标题**: {{ title }}
- **分析时间**: {{ analysis_time }}

## 故障聚类
{% if cluster %}
- **聚类ID**: {{ cluster.id }}
- **聚类主题**: {{ cluster.topic }}
- **相似故障数量**: {{ cluster.size }}
{% endif %}

## 根因分析
### 技术根因
{{ root_cause.technical }}

### 过程根因
{{ root_cause.process }}

### 管理根因
{{ root_cause.management }}

## 规范冲突识别
{% for violation in violations %}
### {{ violation.rule_name }}
- **规范条款**: {{ violation.rule_id }}
- **冲突描述**: {{ violation.description }}
- **证据**: {{ violation.evidence }}
{% endfor %}

## 改进建议
{% for suggestion in suggestions %}
### {{ suggestion.category }}
{{ suggestion.content }}
{% endfor %}
```

### 2.7 配置管理模块 (config/)

```
config/
├── __init__.py
├── manager.py           # 配置管理器
├── models.py            # 配置模型
└── defaults.py          # 默认配置
```

**配置结构**：

```yaml
api:
  base_url: "https://zcmtest.iwhalecloud.com:25000"
  timeout: 30
  retry: 3

llm:
  provider: "openai"
  model: "gpt-4"
  api_key: "${OPENAI_API_KEY}"
  temperature: 0.7
  max_tokens: 4096

embedding:
  provider: "openai"
  model: "text-embedding-3-small"
  api_key: "${OPENAI_API_KEY}"

clustering:
  algorithm: "hdbscan"
  min_cluster_size: 5
  min_samples: 3
  metric: "cosine"

cache:
  enabled: true
  ttl: 86400
  storage: "sqlite"

rules:
  builtin_enabled: true
  custom_path: "./data/rules/custom/"

output:
  format: "markdown"
  directory: "./output/"
```

---

## 三、接口契约定义

### 3.1 CLI接口

```python
# fetch命令
def fetch(
    task_id: Optional[int] = None,
    batch: bool = False,
    query: Optional[str] = None,
    force: bool = False
) -> FetchResult:
    """
    获取故障数据
    
    Args:
        task_id: 单个任务ID
        batch: 是否批量获取
        query: 查询条件 (status=resolved&date=2024-01)
        force: 强制刷新缓存
    
    Returns:
        FetchResult: 获取结果
    """

# analyze命令
def analyze(
    task_id: Optional[int] = None,
    batch: bool = False,
    from_cache: bool = True,
    cluster: bool = True,
    output: Optional[str] = None
) -> AnalysisResult:
    """
    分析故障数据
    
    Args:
        task_id: 单个任务ID
        batch: 是否批量分析
        from_cache: 是否从缓存读取
        cluster: 是否进行聚类分析
        output: 输出目录
    
    Returns:
        AnalysisResult: 分析结果
    """
```

### 3.2 分析引擎接口

```python
class IEmbeddingProvider(Protocol):
    async def embed(self, text: str) -> List[float]:
        """单个文本向量化"""
        
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量文本向量化"""

class IClusteringProvider(Protocol):
    def fit(self, embeddings: np.ndarray) -> np.ndarray:
        """聚类拟合，返回标签"""
        
    def fit_predict(self, embeddings: np.ndarray) -> Tuple[np.ndarray, dict]:
        """聚类并预测，返回标签和聚类信息"""

class ILLMProvider(Protocol):
    async def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        
    async def generate_with_context(
        self, 
        prompt: str, 
        context: List[str],
        **kwargs
    ) -> str:
        """带上下文的生成"""
```

---

## 四、模块依赖关系

```
┌─────────────────────────────────────────────────────────────────┐
│                           CLI Layer                             │
│  main.py ──┬── fetch.py ──┬── api/client.py                    │
│            │              └── cache/manager.py                  │
│            ├── analyze.py ──┬── analyzer/engine.py              │
│            │               ├── cache/manager.py                 │
│            │               └── report/generator.py              │
│            ├── report.py ──── report/generator.py               │
│            └── config.py ──── config/manager.py                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Core Layer                              │
│  analyzer/engine.py ───┬── preprocessor/                        │
│                        ├── embedding/ ──── llm_provider         │
│                        ├── clustering/                          │
│                        ├── labeling/ ───── llm_provider         │
│                        └── reasoning/ ──── rules/engine.py      │
│                                                                   │
│  rules/engine.py ────┬── loader.py                               │
│                      └── checker.py                              │
│                                                                   │
│  report/generator.py ──── templates/                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                         │
│  api/client.py ──── httpx                                        │
│  cache/manager.py ──── sqlite3                                   │
│  config/manager.py ──── pydantic, yaml                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 五、技术选型详情

### 5.1 核心依赖

| 功能 | 库 | 版本 | 说明 |
|-----|---|------|------|
| CLI框架 | typer | ^0.9.0 | 现代CLI框架，基于click |
| 配置管理 | pydantic | ^2.0.0 | 数据验证和配置管理 |
| 配置文件 | pyyaml | ^6.0.0 | YAML配置文件解析 |
| HTTP客户端 | httpx | ^0.25.0 | 异步HTTP客户端 |
| 缓存数据库 | sqlite3 | 内置 | 轻量级本地数据库 |
| LLM调用 | openai | ^1.0.0 | OpenAI API客户端 |
| LLM框架 | langchain | ^0.1.0 | LLM应用框架 |
| Embedding | sentence-transformers | ^2.2.0 | 文本向量化 |
| 聚类 | hdbscan | ^0.8.0 | 层次密度聚类 |
| 降维 | umap-learn | ^0.5.0 | 流形学习降维 |
| 数据处理 | pandas | ^2.0.0 | 数据处理 |
| 数值计算 | numpy | ^1.24.0 | 数值计算 |
| 模板引擎 | jinja2 | ^3.1.0 | 报告模板 |
| 日志 | loguru | ^0.7.0 | 日志记录 |
| 进度条 | rich | ^13.0.0 | 终端美化输出 |
| 异步 | asyncio | 内置 | 异步编程 |

### 5.2 开发依赖

| 功能 | 库 | 版本 |
|-----|---|------|
| 测试 | pytest | ^7.0.0 |
| 测试覆盖率 | pytest-cov | ^4.0.0 |
| 异步测试 | pytest-asyncio | ^0.21.0 |
| 代码格式化 | black | ^23.0.0 |
| 类型检查 | mypy | ^1.0.0 |
| 代码检查 | ruff | ^0.1.0 |

---

## 六、安全设计

### 6.1 敏感信息管理
- API Key等敏感信息存储在 `.env` 文件中
- `.env` 文件加入 `.gitignore`
- 提供 `.env.example` 作为模板
- 运行时从环境变量读取敏感配置

### 6.2 数据安全
- 缓存数据本地存储，不上传云端
- 敏感字段（如用户信息）可选脱敏
- 日志中不记录敏感信息

---

## 七、扩展性设计

### 7.1 插件化设计
- Embedding Provider：支持扩展新的向量化模型
- LLM Provider：支持扩展新的大模型服务
- Rule Checker：支持扩展新的规范检查器

### 7.2 配置驱动
- 所有核心参数可配置
- 支持多环境配置（开发/测试/生产）

---

## 八、下一步

进入 **阶段3: Atomize (原子化阶段)**，将架构设计拆分为可执行的原子任务。
