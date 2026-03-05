# 故障聚类分析系统 V4 - 系统设计文档（最终版）

## 1. 系统架构

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           故障聚类分析系统 V4                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        阶段一：数据准备                            │   │
│  │                    （只需执行一次，可增量更新）                       │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │   │
│  │  │  API客户端    │───▶│  信息提取器   │───▶│  规范知识库   │       │   │
│  │  └──────────────┘    └──────────────┘    └──────────────┘       │   │
│  │         │                   │                   │                  │   │
│  │         ▼                   ▼                   ▼                  │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │   │
│  │  │  违规检测器   │◀───│  LLM分析器   │───▶│  根因验证器   │       │   │
│  │  └──────────────┘    └──────────────┘    └──────────────┘       │   │
│  │         │                   │                   │                  │   │
│  │         └───────────────────┼───────────────────┘                  │   │
│  │                             ▼                                      │   │
│  │                    ┌──────────────┐                                │   │
│  │                    │  向量化器     │                                │   │
│  │                    └──────────────┘                                │   │
│  │                             │                                      │   │
│  │                             ▼                                      │   │
│  │                    ┌──────────────┐                                │   │
│  │                    │ Chroma向量库  │                                │   │
│  │                    └──────────────┘                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                    │
│                                    ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        阶段二：聚类分析                            │   │
│  │                     （可重复执行，参数可调）                          │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │   │
│  │  │  数据加载器   │───▶│  聚类分析器   │───▶│  根因统计器   │       │   │
│  │  └──────────────┘    └──────────────┘    └──────────────┘       │   │
│  │         │                   │                   │                  │   │
│  │         ▼                   ▼                   ▼                  │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │   │
│  │  │  可视化器     │◀───│  改进推荐器   │───▶│  相似度计算器  │       │   │
│  │  └──────────────┘    └──────────────┘    └──────────────┘       │   │
│  │         │                                                          │   │
│  │         ▼                                                          │   │
│  │  ┌──────────────┐                                                   │   │
│  │  │ Streamlit界面 │                                                   │   │
│  │  └──────────────┘                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 分层设计

```
┌─────────────────────────────────────────────────────────────────┐
│                      表现层 (Presentation)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Streamlit UI │  │  可视化组件   │  │  报告生成器   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────────┐
│                      业务层 (Business)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  违规检测器   │  │  根因验证器   │  │  改进推荐器   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  聚类分析器   │  │  根因统计器   │  │  相似度计算器  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────────┐
│                      数据层 (Data)                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  API客户端    │  │  向量化器     │  │  Chroma管理器  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  规范知识库   │  │  LLM Provider│  │  配置管理器   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 核心组件

| 组件 | 职责 | 优先级 |
|-----|------|-------|
| **规范知识库 (StandardKnowledgeBase)** | 存储和管理公司研发规范 | P0 |
| **违规检测器 (ViolationDetector)** | 检测故障是否违反规范 | P0 |
| **根因验证器 (RootCauseValidator)** | 验证根因可落地性 | P0 |
| **改进推荐器 (ImprovementRecommender)** | 针对高频根因生成改进措施 | P0 |
| **根因统计器 (RootCauseStatistics)** | 统计高频根因 | P0 |
| **LLM分析器 (LLMAnalyzer)** | 使用LLM进行根因分析 | P0 |
| **向量化器 (EmbeddingGenerator)** | 将文本转换为向量 | P0 |
| **Chroma管理器 (ChromaManager)** | 管理向量数据库 | P0 |
| **聚类分析器 (ClusterAnalyzer)** | 执行聚类分析 | P0 |
| **可视化器 (Visualizer)** | 生成各类图表 | P0 |
| **相似度计算器 (SimilarityCalculator)** | 计算故障间相似度 | P1 |
| **Streamlit界面 (StreamlitApp)** | 交互式Web界面 | P1 |

---

## 2. 模块设计

### 2.1 规范知识库模块

**文件路径**: `src/knowledge/standard_kb.py`

**职责**:
- 存储和管理公司研发规范
- 支持规范的增删改查
- 支持按类别查询规范
- 支持关键词搜索

**数据结构**:
```python
@dataclass
class StandardRule:
    """规范规则"""
    id: str  # 规则ID
    category: str  # 规范类别（Java编码规范、数据库设计规范等）
    subcategory: str  # 子类别
    title: str  # 规则标题
    content: str  # 规则内容
    level: str  # 级别（强制/推荐）
    code: str  # 规则编号（如J000001）
    examples: List[str]  # 示例

@dataclass
class StandardCategory:
    """规范类别"""
    id: str  # 类别ID
    name: str  # 类别名称
    description: str  # 描述
    rules: List[StandardRule]  # 规则列表
```

**核心接口**:
```python
class StandardKnowledgeBase:
    """规范知识库"""
    
    def load_standards(self, pdf_path: str) -> None:
        """从PDF加载规范"""
        pass
    
    def get_category(self, category_id: str) -> Optional[StandardCategory]:
        """获取规范类别"""
        pass
    
    def get_all_categories(self) -> List[StandardCategory]:
        """获取所有规范类别"""
        pass
    
    def search_rules(self, keyword: str) -> List[StandardRule]:
        """搜索规则"""
        pass
    
    def get_rules_by_category(self, category_id: str) -> List[StandardRule]:
        """按类别获取规则"""
        pass
    
    def add_rule(self, rule: StandardRule) -> None:
        """添加规则"""
        pass
    
    def update_rule(self, rule_id: str, rule: StandardRule) -> None:
        """更新规则"""
        pass
    
    def delete_rule(self, rule_id: str) -> None:
        """删除规则"""
        pass
```

**规范类别映射**:
```python
VIOLATION_CATEGORIES = {
    "java_coding": "违反Java编码规范",
    "javascript_coding": "违反JavaScript编码规范",
    "cpp_coding": "违反C/C++编码规范",
    "python_coding": "违反Python编码规范",
    "golang_coding": "违反Golang编码规范",
    "database_design": "违反数据库设计规范",
    "sql_development": "违反SQL开发规范",
    "database_ops": "违反数据库运维规范",
    "security": "违反安全规范",
    "config_management": "违反配置管理规范",
    "delivery_process": "违反交付流程规范",
}
```

---

### 2.2 违规检测模块

**文件路径**: `src/analysis/violation_detector.py`

**职责**:
- 基于规范知识库检测故障是否违规
- 识别具体违规类型
- 提供违规证据
- 计算违规置信度

**数据结构**:
```python
@dataclass
class ViolationDetection:
    """违规检测结果"""
    is_violation: bool  # 是否违规
    violation_type: Optional[str]  # 违规类型
    violation_category: Optional[str]  # 违规类别
    violated_rules: List[str]  # 违反的规则ID列表
    evidence: str  # 违规证据
    confidence: float  # 置信度
    relevant_standards: List[str]  # 相关规范内容
```

**核心接口**:
```python
class ViolationDetector:
    """违规检测器"""
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        knowledge_base: StandardKnowledgeBase
    ):
        self.llm = llm_provider
        self.kb = knowledge_base
    
    async def detect_violation(
        self,
        task_info: TaskInfo
    ) -> ViolationDetection:
        """检测故障是否违规
        
        流程:
        1. 提取技术栈信息
        2. 匹配相关规范
        3. 构建检测Prompt
        4. 调用LLM进行检测
        5. 解析检测结果
        """
        # 提取技术栈
        tech_stack = self._extract_tech_stack(task_info)
        
        # 获取相关规范
        relevant_standards = self._get_relevant_standards(tech_stack)
        
        # 构建检测Prompt
        prompt = self._build_detection_prompt(task_info, relevant_standards)
        
        # 调用LLM
        response = await self.llm.generate(prompt)
        
        # 解析结果
        return self._parse_detection_result(response)
    
    def _extract_tech_stack(self, task_info: TaskInfo) -> List[str]:
        """提取技术栈信息"""
        pass
    
    def _get_relevant_standards(self, tech_stack: List[str]) -> List[StandardRule]:
        """获取相关规范"""
        pass
    
    def _build_detection_prompt(
        self,
        task_info: TaskInfo,
        standards: List[StandardRule]
    ) -> str:
        """构建检测Prompt"""
        pass
    
    def _parse_detection_result(self, response: str) -> ViolationDetection:
        """解析检测结果"""
        pass
```

**检测Prompt模板**:
```python
VIOLATION_DETECTION_PROMPT = """
你是一个技术规范审查专家，请根据以下公司研发规范，判断故障是否违反规范。

## 故障信息
任务ID: {task_id}
标题: {title}
描述: {description}
技术栈: {tech_stack}
故障现象: {symptom}
故障原因: {cause}

## 相关规范
{standards}

## 分析要求
1. 仔细阅读故障信息和相关规范
2. 判断故障是否违反了上述规范
3. 如果违反，指出违反的具体规则编号和内容
4. 提供违规证据（引用故障信息中的具体内容）
5. 评估违规的置信度（0-1之间的小数）

## 输出格式（JSON）
{{
    "is_violation": true/false,
    "violation_type": "违规类型",
    "violation_category": "违规类别",
    "violated_rules": ["规则ID1", "规则ID2"],
    "evidence": "违规证据",
    "confidence": 0.95
}}
"""
```

---

### 2.3 根因验证模块

**文件路径**: `src/analysis/root_cause_validator.py`

**职责**:
- 验证根因可落地性
- 生成具体改进措施
- 明确验收标准
- 如果不可落地，要求重新分析

**数据结构**:
```python
@dataclass
class RootCauseValidation:
    """根因验证结果"""
    root_cause: str  # 根因
    is_actionable: bool  # 是否可落地
    actionability_score: float  # 可落地性评分
    improvement_measures: List[ImprovementMeasure]  # 改进措施
    validation_reason: str  # 验证原因
    needs_reanalysis: bool  # 是否需要重新分析
    reanalysis_feedback: str  # 重新分析反馈

@dataclass
class ImprovementMeasure:
    """改进措施"""
    id: str  # 措施ID
    description: str  # 措施描述
    acceptance_criteria: str  # 验收标准
    expected_impact: str  # 预期影响
    priority: str  # 优先级
```

**核心接口**:
```python
class RootCauseValidator:
    """根因验证器"""
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider
    
    async def validate_root_cause(
        self,
        task_info: TaskInfo,
        root_cause: str
    ) -> RootCauseValidation:
        """验证根因可落地性
        
        流程:
        1. 应用可落地性规则检查
        2. 如果不可落地，生成反馈
        3. 如果可落地，生成改进措施
        4. 明确验收标准
        """
        # 规则检查
        rule_check = self._check_actionability_rules(root_cause)
        
        if not rule_check.is_actionable:
            return RootCauseValidation(
                root_cause=root_cause,
                is_actionable=False,
                actionability_score=rule_check.score,
                improvement_measures=[],
                validation_reason=rule_check.reason,
                needs_reanalysis=True,
                reanalysis_feedback=rule_check.feedback
            )
        
        # 生成改进措施
        measures = await self._generate_improvement_measures(
            task_info, root_cause
        )
        
        return RootCauseValidation(
            root_cause=root_cause,
            is_actionable=True,
            actionability_score=rule_check.score,
            improvement_measures=measures,
            validation_reason=rule_check.reason,
            needs_reanalysis=False,
            reanalysis_feedback=""
        )
    
    def _check_actionability_rules(
        self,
        root_cause: str
    ) -> RuleCheckResult:
        """应用可落地性规则检查"""
        pass
    
    async def _generate_improvement_measures(
        self,
        task_info: TaskInfo,
        root_cause: str
    ) -> List[ImprovementMeasure]:
        """生成改进措施"""
        pass
```

**可落地性规则**:
```python
ACTIONABILITY_RULES = [
    {
        "pattern": r"场景考虑不足|测试遗漏|场景不全",
        "is_actionable": False,
        "reason": "过于笼统，无法确定具体改进方向",
        "feedback": "请具体说明是哪个场景考虑不足？是正常场景、异常场景、边界场景还是并发场景？请提供具体的技术细节。"
    },
    {
        "pattern": r"沟通不畅|协作问题|配合不当",
        "is_actionable": False,
        "reason": "推卸责任，无法量化改进措施",
        "feedback": "请从技术角度分析根本原因，而不是归咎于沟通或协作问题。是否存在流程缺陷、工具缺失或规范不明确等问题？"
    },
    {
        "pattern": r"代码bug|配置错误|逻辑错误",
        "is_actionable": False,
        "reason": "表面原因，未触及根本原因",
        "feedback": "请深入分析为什么会出现这个bug？是编码规范未遵循？测试覆盖不足？还是设计缺陷？请提供更深层次的原因分析。"
    },
    {
        "pattern": r"时间紧迫|资源不足|人手不够",
        "is_actionable": False,
        "reason": "不可控因素，无法通过措施消除",
        "feedback": "请分析在现有资源约束下，如何通过技术或流程改进来避免类似问题？是否存在流程优化、工具自动化或规范完善的空间？"
    }
]
```

**改进措施生成Prompt**:
```python
IMPROVEMENT_MEASURE_PROMPT = """
你是一个技术改进专家，请为以下根因生成具体的改进措施。

## 故障信息
任务ID: {task_id}
标题: {title}
描述: {description}
根因: {root_cause}

## 改进措施要求
1. 措施必须具体、可执行
2. 明确验收标准（如何验证措施已落实）
3. 说明预期影响（预计能解决什么问题）
4. 避免使用"加强"、"完善"等模糊词汇

## 输出格式（JSON）
{{
    "measures": [
        {{
            "id": "measure_1",
            "description": "具体措施描述",
            "acceptance_criteria": "验收标准",
            "expected_impact": "预期影响",
            "priority": "high/medium/low"
        }}
    ]
}}
"""
```

---

### 2.4 改进推荐模块

**文件路径**: `src/analysis/improvement_recommender.py`

**职责**:
- 针对高频根因生成专项改进措施
- 明确预期影响
- 按优先级排序

**数据结构**:
```python
@dataclass
class RootCauseStat:
    """根因统计"""
    root_cause: str  # 根因
    count: int  # 故障数量
    percentage: float  # 百分比
    related_tasks: List[str]  # 相关任务ID
    trend: str  # 趋势（上升/下降/稳定）

@dataclass
class ImprovementRecommendation:
    """改进推荐"""
    root_cause: str  # 根因
    frequency: int  # 频率
    measures: List[ImprovementMeasure]  # 改进措施
    priority: str  # 优先级
    expected_impact: str  # 预期影响
```

**核心接口**:
```python
class ImprovementRecommender:
    """改进措施推荐器"""
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider
    
    async def generate_recommendations(
        self,
        root_cause_stats: List[RootCauseStat],
        top_n: int = 5
    ) -> List[ImprovementRecommendation]:
        """生成改进推荐
        
        流程:
        1. 选择Top N高频根因
        2. 针对每个根因生成专项改进措施
        3. 明确预期影响
        4. 按优先级排序
        """
        recommendations = []
        
        # 选择Top N
        top_causes = root_cause_stats[:top_n]
        
        for stat in top_causes:
            measures = await self._generate_measures_for_cause(stat)
            recommendations.append(ImprovementRecommendation(
                root_cause=stat.root_cause,
                frequency=stat.count,
                measures=measures,
                priority=self._calculate_priority(stat),
                expected_impact=self._estimate_impact(stat)
            ))
        
        return recommendations
    
    async def _generate_measures_for_cause(
        self,
        stat: RootCauseStat
    ) -> List[ImprovementMeasure]:
        """为根因生成改进措施"""
        pass
    
    def _calculate_priority(self, stat: RootCauseStat) -> str:
        """计算优先级"""
        pass
    
    def _estimate_impact(self, stat: RootCauseStat) -> str:
        """估计预期影响"""
        pass
```

---

### 2.5 根因统计模块

**文件路径**: `src/analysis/root_cause_statistics.py`

**职责**:
- 统计各类根因的出现频率
- 按频率排序
- 分析根因趋势
- 统计违规类型分布

**核心接口**:
```python
class RootCauseStatistics:
    """根因统计分析器"""
    
    def calculate_statistics(
        self,
        tasks: List[TaskInfo]
    ) -> List[RootCauseStat]:
        """计算根因统计
        
        流程:
        1. 统计各类根因的出现次数
        2. 计算百分比
        3. 按频率排序
        4. 分析趋势
        """
        pass
    
    def get_violation_distribution(
        self,
        tasks: List[TaskInfo]
    ) -> Dict[str, int]:
        """获取违规类型分布"""
        pass
    
    def analyze_trend(
        self,
        tasks: List[TaskInfo],
        window: int = 7
    ) -> Dict[str, str]:
        """分析根因趋势"""
        pass
```

---

### 2.6 LLM分析模块（代码变更增强版）

**文件路径**: `src/analysis/llm_analyzer.py`

**职责**:
- 整合违规检测、根因分析、根因验证
- 集成代码变更分析
- 输出完整的分析结果

**数据结构**:
```python
@dataclass
class CodeChange:
    """代码变更"""
    commit_id: str  # 提交ID
    author: str  # 作者
    timestamp: datetime  # 提交时间
    message: str  # 提交信息
    diff: str  # 代码diff
    files_changed: List[str]  # 变更的文件列表

@dataclass
class LLMAnalysisResult:
    """LLM分析结果"""
    task_id: str  # 任务ID
    violation_detection: ViolationDetection  # 违规检测
    root_cause: str  # 根因
    root_cause_validation: RootCauseValidation  # 根因验证
    code_changes: List[CodeChange]  # 代码变更
    analysis_text: str  # 完整分析文本
    timestamp: datetime  # 分析时间
```

**核心接口**:
```python
class LLMAnalyzer:
    """LLM分析器（代码变更增强版）"""
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        violation_detector: ViolationDetector,
        root_cause_validator: RootCauseValidator,
        api_client: APIClient = None
    ):
        self.llm = llm_provider
        self.violation_detector = violation_detector
        self.root_cause_validator = root_cause_validator
        self.api_client = api_client
    
    async def analyze_task(
        self,
        task_info: TaskInfo
    ) -> LLMAnalysisResult:
        """分析故障
        
        流程:
        1. 违规检测
        2. 获取代码变更记录
        3. 根因分析（结合代码变更）
        4. 根因验证
        5. 生成改进措施
        6. 输出完整结果
        """
        # 步骤1：违规检测
        violation_result = await self.violation_detector.detect_violation(task_info)
        
        # 步骤2：获取代码变更
        code_changes = []
        if self.api_client:
            code_changes = await self.api_client.get_code_changes(task_info.task_id)
        
        # 步骤3：根因分析
        root_cause = await self._analyze_root_cause(
            task_info, violation_result, code_changes
        )
        
        # 步骤4：根因验证
        validation_result = await self.root_cause_validator.validate_root_cause(
            task_info, root_cause
        )
        
        # 步骤5：如果不可落地，重新分析
        if validation_result.needs_reanalysis:
            root_cause = await self._reanalyze_root_cause(
                task_info, root_cause, validation_result.reanalysis_feedback, code_changes
            )
            validation_result = await self.root_cause_validator.validate_root_cause(
                task_info, root_cause
            )
        
        return LLMAnalysisResult(
            task_id=task_info.task_id,
            violation_detection=violation_result,
            root_cause=root_cause,
            root_cause_validation=validation_result,
            code_changes=code_changes,
            analysis_text=self._generate_analysis_text(
                violation_result, root_cause, validation_result, code_changes
            ),
            timestamp=datetime.now()
        )
    
    async def _analyze_root_cause(
        self,
        task_info: TaskInfo,
        violation_result: ViolationDetection,
        code_changes: List[CodeChange]
    ) -> str:
        """分析根因（结合代码变更）"""
        # 构建包含代码变更的分析文本
        code_diff_text = self._format_code_changes(code_changes)
        # 调用LLM分析
        pass
    
    async def _reanalyze_root_cause(
        self,
        task_info: TaskInfo,
        original_cause: str,
        feedback: str,
        code_changes: List[CodeChange]
    ) -> str:
        """重新分析根因"""
        pass
    
    def _format_code_changes(
        self,
        code_changes: List[CodeChange]
    ) -> str:
        """格式化代码变更"""
        parts = []
        for change in code_changes:
            parts.append(f"Commit: {change.commit_id}")
            parts.append(f"Author: {change.author}")
            parts.append(f"Message: {change.message}")
            parts.append(f"Files: {', '.join(change.files_changed)}")
            parts.append(f"Diff: {change.diff[:1000]}...")  # 截断长diff
            parts.append("---")
        return "\n".join(parts)
    
    def _generate_analysis_text(
        self,
        violation_result: ViolationDetection,
        root_cause: str,
        validation_result: RootCauseValidation,
        code_changes: List[CodeChange]
    ) -> str:
        """生成分析文本"""
        pass
```

---

### 2.7 向量化模块（多模态增强版）

**文件路径**: `src/embedding/generator.py`

**职责**:
- 支持文本和图像等多模态内容的向量化
- 统一生成向量表示
- 支持Volcano Engine多模态模型

**数据结构**:
```python
@dataclass
class EmbeddingResult:
    """向量化结果"""
    task_id: str  # 任务ID
    embedding: List[float]  # 向量
    text: str  # 文本内容
    media_type: str  # 媒体类型（text/image/mixed）
    metadata: Dict[str, Any]  # 元数据（包含违规检测、根因、改进措施）

@dataclass
class MediaContent:
    """媒体内容"""
    type: str  # text/image
    content: str  # 文本内容或图片URL/base64
    filename: Optional[str] = None  # 文件名
```

**核心接口**:
```python
class EmbeddingGenerator:
    """向量化器（多模态增强版）"""
    
    def __init__(self, config: Config):
        self.config = config
        self.client = self._init_client()
    
    async def generate_embedding(
        self,
        analysis_result: LLMAnalysisResult,
        media_contents: List[MediaContent] = None
    ) -> EmbeddingResult:
        """生成向量
        
        流程:
        1. 检测内容类型
        2. 分别处理文本和图像
        3. 调用Volcano Engine多模态API
        4. 返回统一向量结果
        """
        # 构建基础文本
        text = self._build_embedding_text(analysis_result)
        
        # 处理多模态内容
        media_type = "text"
        if media_contents:
            media_type = "mixed"
            # 处理图像等非文本内容
            # 调用多模态API
        
        # 生成向量
        embedding = await self._call_api(text, media_contents)
        
        # 构建元数据
        metadata = self._build_metadata(analysis_result, media_type)
        
        return EmbeddingResult(
            task_id=analysis_result.task_id,
            embedding=embedding,
            text=text,
            media_type=media_type,
            metadata=metadata
        )
    
    def _build_embedding_text(
        self,
        analysis_result: LLMAnalysisResult
    ) -> str:
        """构建向量化文本"""
        parts = []
        
        # 基础信息
        parts.append(f"任务ID: {analysis_result.task_id}")
        
        # 违规检测
        if analysis_result.violation_detection.is_violation:
            parts.append(f"违规类型: {analysis_result.violation_detection.violation_type}")
            parts.append(f"违规类别: {analysis_result.violation_detection.violation_category}")
        
        # 根因
        parts.append(f"根因: {analysis_result.root_cause}")
        
        # 改进措施
        for measure in analysis_result.root_cause_validation.improvement_measures:
            parts.append(f"改进措施: {measure.description}")
        
        return "\n".join(parts)
    
    def _build_metadata(
        self,
        analysis_result: LLMAnalysisResult,
        media_type: str
    ) -> Dict[str, Any]:
        """构建元数据"""
        return {
            "task_id": analysis_result.task_id,
            "is_violation": analysis_result.violation_detection.is_violation,
            "violation_type": analysis_result.violation_detection.violation_type,
            "violation_category": analysis_result.violation_detection.violation_category,
            "root_cause": analysis_result.root_cause,
            "is_actionable": analysis_result.root_cause_validation.is_actionable,
            "improvement_measures": [
                m.description for m in analysis_result.root_cause_validation.improvement_measures
            ],
            "media_type": media_type,
            "timestamp": analysis_result.timestamp.isoformat()
        }
    
    async def _call_api(
        self,
        text: str,
        media_contents: List[MediaContent] = None
    ) -> List[float]:
        """调用Volcano Engine多模态API"""
        # 处理多模态内容
        # 调用API
        # 返回向量
        pass
```

---

### 2.8 Chroma管理模块（增强版）

**文件路径**: `src/storage/chroma_manager.py`

**职责**:
- 管理Chroma向量数据库
- 支持增删改查
- 支持批量操作

**核心接口**:
```python
class ChromaManager:
    """Chroma管理器（增强版）"""
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name="fault_embeddings",
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_embeddings(
        self,
        embeddings: List[EmbeddingResult]
    ) -> None:
        """添加向量
        
        流程:
        1. 提取向量、ID、元数据
        2. 调用Chroma add接口
        3. 持久化
        """
        ids = [e.task_id for e in embeddings]
        vectors = [e.embedding for e in embeddings]
        metadatas = [e.metadata for e in embeddings]
        
        self.collection.add(
            ids=ids,
            embeddings=vectors,
            metadatas=metadatas
        )
    
    def get_all_embeddings(self) -> Dict[str, Any]:
        """获取所有向量"""
        return self.collection.get()
    
    def get_embedding_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取向量"""
        result = self.collection.get(ids=[task_id])
        if result["ids"]:
            return {
                "id": result["ids"][0],
                "embedding": result["embeddings"][0],
                "metadata": result["metadatas"][0]
            }
        return None
    
    def update_metadata(
        self,
        task_id: str,
        metadata: Dict[str, Any]
    ) -> None:
        """更新元数据"""
        self.collection.update(
            ids=[task_id],
            metadatas=[metadata]
        )
    
    def query_similar(
        self,
        query_embedding: List[float],
        n_results: int = 10
    ) -> Dict[str, Any]:
        """查询相似向量"""
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
```

---

### 2.9 聚类分析模块（增强版）

**文件路径**: `src/clustering/analyzer.py`

**职责**:
- 执行聚类分析
- 支持多种算法
- 支持参数调整
- 评估聚类质量

**数据结构**:
```python
@dataclass
class ClusteringResult:
    """聚类结果"""
    labels: List[int]  # 聚类标签
    n_clusters: int  # 聚类数量
    n_noise: int  # 噪声点数量
    silhouette_score: float  # 轮廓系数
    algorithm: str  # 使用的算法
    parameters: Dict[str, Any]  # 参数
```

**核心接口**:
```python
class ClusterAnalyzer:
    """聚类分析器（增强版）"""
    
    def __init__(self):
        pass
    
    def cluster(
        self,
        embeddings: List[List[float]],
        algorithm: str = "hdbscan",
        **kwargs
    ) -> ClusteringResult:
        """执行聚类
        
        支持的算法:
        - hdbscan: HDBSCAN（默认）
        - hierarchical: 层次聚类
        - kmeans: K-Means
        
        参数:
        - algorithm: 聚类算法
        - min_cluster_size: 最小聚类大小（HDBSCAN）
        - min_samples: 最小样本数（HDBSCAN）
        - n_clusters: 聚类数量（K-Means）
        - metric: 距离度量（cosine, euclidean）
        """
        if algorithm == "hdbscan":
            return self._hdbscan_cluster(embeddings, **kwargs)
        elif algorithm == "hierarchical":
            return self._hierarchical_cluster(embeddings, **kwargs)
        elif algorithm == "kmeans":
            return self._kmeans_cluster(embeddings, **kwargs)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")
    
    def _hdbscan_cluster(
        self,
        embeddings: List[List[float]],
        min_cluster_size: int = 5,
        min_samples: int = 3,
        metric: str = "cosine"
    ) -> ClusteringResult:
        """HDBSCAN聚类"""
        pass
    
    def _hierarchical_cluster(
        self,
        embeddings: List[List[float]],
        n_clusters: int = None,
        linkage: str = "ward",
        metric: str = "euclidean"
    ) -> ClusteringResult:
        """层次聚类
        
        技术约束:
        - linkage="ward"时只支持欧氏距离（metric="euclidean"）
        - 使用余弦距离时，linkage必须是"complete"/"average"/"single"
        - 参数合法性校验: ward + cosine会抛出ValueError
        """
        pass
    
    def _kmeans_cluster(
        self,
        embeddings: List[List[float]],
        n_clusters: int = 5,
        metric: str = "cosine"
    ) -> ClusteringResult:
        """K-Means聚类
        
        技术约束:
        - sklearn.cluster.KMeans不原生支持余弦距离
        - 使用余弦距离时，先对向量进行L2归一化，再使用欧氏距离
        - 数学上等价: cosine_distance(u,v) = 1 - dot(u_norm, v_norm)
        """
        pass
    
    def calculate_silhouette_score(
        self,
        embeddings: List[List[float]],
        labels: List[int]
    ) -> float:
        """计算轮廓系数"""
        pass
```

---

### 2.10 可视化模块（增强版）

**文件路径**: `src/visualization/visualizer.py`

**职责**:
- 生成根因分布图
- 生成违规类型分布图
- 生成改进措施追踪图
- 生成UMAP散点图（按根因着色）
- 生成热力图
- 生成树状图

**核心接口**:
```python
class Visualizer:
    """可视化器（增强版）"""
    
    def plot_root_cause_distribution(
        self,
        stats: List[RootCauseStat],
        save_path: str = None
    ) -> go.Figure:
        """根因分布图（柱状图）"""
        pass
    
    def plot_violation_distribution(
        self,
        violation_counts: Dict[str, int],
        save_path: str = None
    ) -> go.Figure:
        """违规类型分布图（饼图）"""
        pass
    
    def plot_improvement_tracking(
        self,
        recommendations: List[ImprovementRecommendation],
        save_path: str = None
    ) -> go.Figure:
        """改进措施追踪图（按优先级分组的柱状图）"""
        pass
    
    def plot_umap_scatter(
        self,
        embeddings: List[List[float]],
        root_causes: List[str],
        save_path: str = None
    ) -> go.Figure:
        """UMAP散点图（按根因着色）"""
        pass
    
    def plot_similarity_heatmap(
        self,
        similarity_matrix: np.ndarray,
        task_ids: List[str],
        save_path: str = None
    ) -> go.Figure:
        """相似度热力图"""
        pass
    
    def plot_dendrogram(
        self,
        linkage_matrix: np.ndarray,
        task_ids: List[str],
        save_path: str = None
    ) -> go.Figure:
        """树状图"""
        pass
```

---

### 2.11 Streamlit界面模块

**文件路径**: `app.py`

**职责**:
- 提供交互式Web界面
- 支持参数调整
- 支持相似度查询
- 支持结果探索

**界面结构**:
```python
import streamlit as st

def main():
    st.set_page_config(
        page_title="故障聚类分析系统",
        layout="wide"
    )
    
    # 侧边栏
    st.sidebar.title("导航")
    page = st.sidebar.radio(
        "选择功能",
        ["数据准备", "聚类分析", "根因统计", "改进措施"]
    )
    
    if page == "数据准备":
        show_data_preparation_page()
    elif page == "聚类分析":
        show_clustering_page()
    elif page == "根因统计":
        show_root_cause_stats_page()
    elif page == "改进措施":
        show_improvement_measures_page()

def show_data_preparation_page():
    st.header("数据准备")
    
    # 上传故障单ID列表
    task_ids = st.text_area("故障单ID列表（每行一个）")
    
    # 执行数据准备
    if st.button("执行数据准备"):
        with st.spinner("正在执行数据准备..."):
            # 方案1: 使用subprocess调用阶段一脚本（推荐）
            # 避免asyncio.run()在Streamlit事件循环中的冲突
            import subprocess
            result = subprocess.run(
                ["python", "scripts/phase1_prepare.py", "--task-ids", task_ids],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                st.success("数据准备完成")
            else:
                st.error(f"执行失败: {result.stderr}")
            
            # 方案2: 使用nest_asyncio（备选）
            # import nest_asyncio
            # nest_asyncio.apply()
            # asyncio.run(phase1_engine.prepare_data(task_ids))
    
    # 显示进度
    st.success("数据准备完成")

def show_clustering_page():
    st.header("聚类分析")
    
    # 参数调整
    col1, col2 = st.columns(2)
    with col1:
        algorithm = st.selectbox(
            "聚类算法",
            ["hdbscan", "hierarchical", "kmeans"]
        )
    with col2:
        metric = st.selectbox(
            "距离度量",
            ["cosine", "euclidean"]
        )
    
    # 执行聚类
    if st.button("执行聚类"):
        with st.spinner("正在执行聚类..."):
            # 调用聚类分析器
            pass
    
    # 显示结果
    st.success("聚类完成")
    
    # UMAP散点图
    st.subheader("UMAP散点图（按根因着色）")
    # 显示散点图
    
    # 相似度查询
    st.subheader("相似度查询")
    task_id = st.text_input("输入故障单ID")
    n_results = st.slider("相似故障数量", 1, 20, 5)
    
    if st.button("查询"):
        # 查询相似故障
        pass

def show_root_cause_stats_page():
    st.header("根因统计")
    
    # 根因分布图
    st.subheader("根因分布图")
    # 显示根因分布图
    
    # 违规类型分布图
    st.subheader("违规类型分布图")
    # 显示违规分布图

def show_improvement_measures_page():
    st.header("改进措施")
    
    # 改进措施追踪图
    st.subheader("改进措施追踪图")
    # 显示改进措施追踪图
    
    # 详细措施列表
    st.subheader("详细措施列表")
    # 显示详细措施
```

---

## 3. 数据流设计

### 3.1 阶段一：数据准备流程

```
┌──────────────┐
│ 故障单ID列表  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  API客户端    │───▶ 获取故障详细信息
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  信息提取器   │───▶ 提取需求、设计、实现、测试、运维信息
└──────┬───────┘
       │
       ├──────────────────────┐
       │                      │
       ▼                      ▼
┌──────────────┐      ┌──────────────┐
│  规范知识库   │      │  LLM分析器   │
└──────┬───────┘      └──────┬───────┘
       │                     │
       │                     ▼
       │              ┌──────────────┐
       │              │  违规检测器   │◀───
       │              └──────┬───────┘
       │                     │
       │                     ▼
       │              ┌──────────────┐
       │              │  根因验证器   │
       │              └──────┬───────┘
       │                     │
       └─────────────────────┤
                             ▼
                      ┌──────────────┐
                      │  分析结果     │
                      └──────┬───────┘
                             │
                             ▼
                      ┌──────────────┐
                      │  向量化器     │
                      └──────┬───────┘
                             │
                             ▼
                      ┌──────────────┐
                      │ Chroma向量库  │
                      └──────────────┘
```

### 3.2 阶段二：聚类分析流程

```
┌──────────────┐
│ Chroma向量库  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  数据加载器   │───▶ 加载所有向量和元数据
└──────┬───────┘
       │
       ├──────────────────────┐
       │                      │
       ▼                      ▼
┌──────────────┐      ┌──────────────┐
│  聚类分析器   │      │  根因统计器   │
└──────┬───────┘      └──────┬───────┘
       │                     │
       │                     ▼
       │              ┌──────────────┐
       │              │  改进推荐器   │
       │              └──────┬───────┘
       │                     │
       └─────────────────────┤
                             ▼
                      ┌──────────────┐
                      │  可视化器     │
                      └──────┬───────┘
                             │
                             ▼
                      ┌──────────────┐
                      │ Streamlit界面 │
                      └──────────────┘
```

---

## 4. 接口设计

### 4.1 API字段提取清单

**API提取的完整字段列表**（覆盖完整流程）：

| 字段类别 | 字段名称 | 数据类型 | 描述 | 来源 |
|---------|---------|---------|------|------|
| **基础信息** | `task_id` | String | 故障单ID | 故障单接口 |
| | `title` | String | 标题 | 故障单接口 |
| | `description` | String | 描述 | 故障单接口 |
| | `created_at` | DateTime | 创建时间 | 故障单接口 |
| | `updated_at` | DateTime | 更新时间 | 故障单接口 |
| **完整流程信息** | `requirement` | String | 需求信息 | 需求接口 |
| | `design` | String | 设计信息 | 设计接口 |
| | `implementation` | String | 实现信息 | 开发接口 |
| | `testing` | String | 测试信息 | 测试接口 |
| | `operations` | String | 运维信息 | 运维接口 |
| **故障相关** | `symptom` | String | 故障现象 | 故障单接口 |
| | `cause` | String | 故障原因 | 故障单接口 |
| | `solution` | String | 解决方案 | 故障单接口 |
| | `impact` | String | 影响范围 | 故障单接口 |
| | `severity` | String | 严重程度 | 故障单接口 |
| **技术信息** | `tech_stack` | List[String] | 技术栈 | 技术接口 |
| | `modules` | List[String] | 涉及模块 | 技术接口 |
| | `environment` | String | 环境 | 技术接口 |
| **代码变更** | `code_changes.commit_id` | String | 提交ID | 代码变更接口 |
| | `code_changes.author` | String | 作者 | 代码变更接口 |
| | `code_changes.timestamp` | DateTime | 提交时间 | 代码变更接口 |
| | `code_changes.message` | String | 提交信息 | 代码变更接口 |
| | `code_changes.diff` | String | 代码diff | 代码变更接口 |
| | `code_changes.files_changed` | List[String] | 变更的文件列表 | 代码变更接口 |
| | `code_changes.branch` | String | 分支 | 代码变更接口 |
| | `code_changes.repository` | String | 仓库 | 代码变更接口 |
| **构建与部署** | `build_info` | Dict | 构建信息 | 构建接口 |
| | `deploy_info` | Dict | 部署信息 | 部署接口 |
| **测试信息** | `test_results` | List[Dict] | 测试结果 | 测试接口 |
| | `test_coverage` | Float | 测试覆盖率 | 测试接口 |
| **多模态内容** | `attachments` | List[Dict] | 附件信息 | 附件接口 |
| | `media_contents.type` | String | 媒体类型 | 附件接口 |
| | `media_contents.content` | String | 媒体内容 | 附件接口 |
| | `media_contents.filename` | String | 文件名 | 附件接口 |
| | `media_contents.content_type` | String | 内容类型 | 附件接口 |

### 4.2 阶段一脚本接口

**文件路径**: `scripts/phase1_prepare.py`

```python
import asyncio
from pathlib import Path

async def main():
    """阶段一：数据准备"""
    
    # 1. 初始化组件
    config = load_config()
    api_client = APIClient(config)
    kb = StandardKnowledgeBase()
    kb.load_standards("docs/浩鲸在线规范库.pdf")
    
    llm = LLMProvider(config)
    violation_detector = ViolationDetector(llm, kb)
    root_cause_validator = RootCauseValidator(llm)
    llm_analyzer = LLMAnalyzer(llm, violation_detector, root_cause_validator, api_client)
    
    embedding_generator = EmbeddingGenerator(config)
    chroma_manager = ChromaManager()
    
    # 2. 读取故障单ID列表
    task_ids = read_task_ids("data/task_ids.txt")
    
    # 3. 处理每个故障单
    all_embeddings = []
    for task_id in task_ids:
        # 获取故障信息（包含完整流程信息）
        task_info = await api_client.get_task_info(task_id)
        
        # LLM分析（包含代码变更分析）
        analysis_result = await llm_analyzer.analyze_task(task_info)
        
        # 向量化（支持多模态）
        embedding = await embedding_generator.generate_embedding(
            analysis_result, 
            task_info.media_contents
        )
        all_embeddings.append(embedding)
        
        print(f"✓ 已处理: {task_id}")
    
    # 4. 保存到Chroma
    chroma_manager.add_embeddings(all_embeddings)
    
    print(f"✓ 数据准备完成，共处理 {len(all_embeddings)} 个故障单")

if __name__ == "__main__":
    asyncio.run(main())
```

### 4.3 阶段二脚本接口

**文件路径**: `scripts/phase2_analyze.py`

```python
async def main():
    """阶段二：聚类分析"""
    
    # 1. 初始化组件
    chroma_manager = ChromaManager()
    cluster_analyzer = ClusterAnalyzer()
    root_cause_stats = RootCauseStatistics()
    improvement_recommender = ImprovementRecommender(llm)
    visualizer = Visualizer()
    
    # 2. 加载数据
    data = chroma_manager.get_all_embeddings()
    embeddings = data["embeddings"]
    metadatas = data["metadatas"]
    
    # 3. 聚类分析
    clustering_result = cluster_analyzer.cluster(
        embeddings,
        algorithm="hdbscan",
        min_cluster_size=5,
        metric="cosine"
    )
    
    print(f"✓ 聚类完成: {clustering_result.n_clusters} 个聚类, {clustering_result.n_noise} 个噪声点")
    
    # 4. 根因统计
    root_cause_list = [m["root_cause"] for m in metadatas]
    stats = root_cause_stats.calculate_statistics(root_cause_list)
    
    # 5. 改进推荐
    recommendations = await improvement_recommender.generate_recommendations(
        stats, top_n=5
    )
    
    # 6. 可视化
    # 根因分布图
    fig1 = visualizer.plot_root_cause_distribution(stats)
    fig1.write_html("output/root_cause_distribution.html")
    
    # 违规分布图
    violation_counts = root_cause_stats.get_violation_distribution(metadatas)
    fig2 = visualizer.plot_violation_distribution(violation_counts)
    fig2.write_html("output/violation_distribution.html")
    
    # 改进措施追踪图
    fig3 = visualizer.plot_improvement_tracking(recommendations)
    fig3.write_html("output/improvement_tracking.html")
    
    # UMAP散点图（按根因着色）
    fig4 = visualizer.plot_umap_scatter(embeddings, root_cause_list)
    fig4.write_html("output/umap_scatter.html")
    
    print("✓ 分析完成，结果已保存到 output/ 目录")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 5. 数据模型

### 5.1 核心数据模型

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional

@dataclass
class TaskInfo:
    """故障单信息"""
    # 基础信息
    task_id: str  # 故障单ID
    title: str  # 标题
    description: str  # 描述
    created_at: datetime  # 创建时间
    updated_at: datetime  # 更新时间
    
    # 完整流程信息
    requirement: str  # 需求信息
    design: str  # 设计信息
    implementation: str  # 实现信息
    testing: str  # 测试信息
    operations: str  # 运维信息
    
    # 故障相关
    symptom: str  # 故障现象
    cause: str  # 故障原因
    solution: str  # 解决方案
    impact: str  # 影响范围
    severity: str  # 严重程度
    
    # 技术信息
    tech_stack: List[str]  # 技术栈
    modules: List[str]  # 涉及模块
    environment: str  # 环境
    
    # 代码变更（新增）
    code_changes: List[CodeChange]  # 代码变更列表
    
    # 构建与部署
    build_info: Dict[str, Any]  # 构建信息
    deploy_info: Dict[str, Any]  # 部署信息
    
    # 测试信息
    test_results: List[Dict[str, Any]]  # 测试结果
    test_coverage: float  # 测试覆盖率
    
    # 附件与多模态内容
    attachments: List[Dict[str, Any]]  # 附件信息
    media_contents: List[MediaContent]  # 多模态内容

@dataclass
class CodeChange:
    """代码变更"""
    commit_id: str  # 提交ID
    author: str  # 作者
    timestamp: datetime  # 提交时间
    message: str  # 提交信息
    diff: str  # 代码diff
    files_changed: List[str]  # 变更的文件列表
    branch: str  # 分支
    repository: str  # 仓库

@dataclass
class MediaContent:
    """媒体内容"""
    type: str  # text/image
    content: str  # 文本内容或图片URL/base64
    filename: Optional[str] = None  # 文件名
    content_type: Optional[str] = None  # 内容类型


@dataclass
class LLMAnalysisResult:
    """LLM分析结果"""
    task_id: str
    violation_detection: ViolationDetection
    root_cause: str
    root_cause_validation: RootCauseValidation
    code_changes: List[CodeChange]  # 代码变更（新增）
    analysis_text: str
    timestamp: datetime

@dataclass
class ViolationDetection:
    """违规检测结果"""
    is_violation: bool
    violation_type: Optional[str]
    violation_category: Optional[str]
    violated_rules: List[str]
    evidence: str
    confidence: float
    relevant_standards: List[str]

@dataclass
class RootCauseValidation:
    """根因验证结果"""
    root_cause: str
    is_actionable: bool
    actionability_score: float
    improvement_measures: List[ImprovementMeasure]
    validation_reason: str
    needs_reanalysis: bool
    reanalysis_feedback: str

@dataclass
class ImprovementMeasure:
    """改进措施"""
    id: str
    description: str
    acceptance_criteria: str
    expected_impact: str
    priority: str

@dataclass
class RootCauseStat:
    """根因统计"""
    root_cause: str
    count: int
    percentage: float
    related_tasks: List[str]
    trend: str

@dataclass
class ImprovementRecommendation:
    """改进推荐"""
    root_cause: str
    frequency: int
    measures: List[ImprovementMeasure]
    priority: str
    expected_impact: str

@dataclass
class ClusteringResult:
    """聚类结果"""
    labels: List[int]
    n_clusters: int
    n_noise: int
    silhouette_score: float
    algorithm: str
    parameters: Dict[str, Any]

@dataclass
class EmbeddingResult:
    """向量化结果"""
    task_id: str
    embedding: List[float]
    text: str
    media_type: str  # 媒体类型（text/image/mixed）（新增）
    metadata: Dict[str, Any]
```

---

## 6. 配置管理

### 6.1 配置文件结构

**文件路径**: `config.yaml`

```yaml
# API配置
api:
  base_url: "https://api.example.com"
  timeout: 30

# LLM配置
llm:
  provider: "volcengine"
  model: "doubao-seed-1-8-251228"
  api_key: "${LLM_API_KEY}"
  base_url: "https://ark.cn-beijing.volces.com/api/v3"
  temperature: 0.7
  max_tokens: 4096

# Embedding配置
embedding:
  provider: "volcengine"
  model: "doubao-embedding-vision-251215"
  api_key: "${EMBEDDING_API_KEY}"
  base_url: "https://ark.cn-beijing.volces.com/api/v3"

# Chroma配置
chroma:
  persist_directory: "./chroma_db"
  collection_name: "fault_embeddings"

# 聚类配置
clustering:
  default_algorithm: "hdbscan"
  hdbscan:
    min_cluster_size: 5
    min_samples: 3
    metric: "cosine"
  hierarchical:
    linkage: "ward"
  kmeans:
    n_clusters: 5

# 可视化配置
visualization:
  output_dir: "./output"
  figure_size: [12, 8]
  color_scheme: "viridis"

# 规范知识库配置
standards:
  pdf_path: "docs/浩鲸在线规范库.pdf"
  json_path: "data/standards.json"
```

---

## 7. 质量保证

### 7.1 测试策略

| 测试类型 | 覆盖范围 | 目标覆盖率 |
|---------|---------|-----------|
| 单元测试 | 各模块核心功能 | ≥80% |
| 集成测试 | 模块间交互 | 核心流程100% |
| 端到端测试 | 完整分析流程 | 阶段一、阶段二各1个 |
| 性能测试 | 大规模数据处理 | 1000+故障单 |

### 7.2 验收标准

| 功能 | 验收标准 |
|-----|---------|
| 违规检测 | 准确率≥90%（人工抽样验证） |
| 根因可落地性 | ≥95%（人工审核） |
| 聚类质量 | 轮廓系数≥0.5 |
| 可视化 | 所有图表清晰可读 |
| 性能 | 阶段一处理1000个故障单<30分钟 |

---

## 8. 部署架构

### 8.1 开发环境

```
故障聚类分析系统/
├── src/                    # 源代码
│   ├── knowledge/          # 规范知识库
│   ├── analysis/          # 分析模块
│   ├── embedding/         # 向量化模块
│   ├── storage/           # 存储模块
│   ├── clustering/        # 聚类模块
│   ├── visualization/     # 可视化模块
│   └── api/              # API客户端
├── scripts/              # 脚本
│   ├── phase1_prepare.py  # 阶段一脚本
│   └── phase2_analyze.py  # 阶段二脚本
├── data/                 # 数据目录
│   ├── standards.json     # 规范数据
│   └── task_ids.txt      # 故障单ID列表
├── chroma_db/           # Chroma向量数据库
├── output/              # 输出目录
├── docs/                # 文档
├── app.py              # Streamlit应用
├── config.yaml         # 配置文件
└── requirements.txt    # 依赖包
```

### 8.2 运行环境

**依赖**:
- Python >= 3.10
- chromadb
- hdbscan
- umap-learn
- plotly
- streamlit
- httpx
- pydantic
- loguru

**安装**:
```bash
pip install -r requirements.txt
```

**运行**:
```bash
# 阶段一：数据准备
python scripts/phase1_prepare.py

# 阶段二：聚类分析
python scripts/phase2_analyze.py

# Streamlit界面
streamlit run app.py
```

---

**文档版本**: V4.0（最终版）  
**创建日期**: 2026-03-05  
**状态**: 待评审  
**基于文档**: ALIGNMENT_故障聚类分析_v4.md
