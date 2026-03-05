# 故障聚类分析系统 V3 - 系统设计文档（修订版）

## 1. 系统架构概览（修订）

### 1.1 整体架构图（修订）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           故障聚类分析系统 V3                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     阶段一：数据准备与深度分析                        │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐  │   │
│  │  │ API数据   │──▶│ 规范知识 │──▶│  LLM深度分析(增强版)    │  │   │
│  │  │ 提取      │  │ 库管理   │  │  - 违规检测             │  │   │
│  │  └──────────┘  └──────────┘  │  - 根因分析             │  │   │
│  │                              │  - 可落地性验证           │  │   │
│  │                              │  - 改进措施生成          │  │   │
│  │                              └────────┬─────────────────┘  │   │
│  │                                       │                    │   │
│  │                                       ▼                    │   │
│  │                              ┌──────────────────────────┐  │   │
│  │                              │  文本构建(增强版)       │  │   │
│  │                              │  - 违规检测结果         │  │   │
│  │                              │  - 根因分类             │  │   │
│  │                              │  - 改进措施摘要         │  │   │
│  │                              └────────┬─────────────────┘  │   │
│  │                                       │                    │   │
│  │                                       ▼                    │   │
│  │                              ┌──────────────────────────┐  │   │
│  │                              │  Embedding生成          │  │   │
│  │                              └────────┬─────────────────┘  │   │
│  │                                       │                    │   │
│  │                                       ▼                    │   │
│  │                              ┌──────────────────────────┐  │   │
│  │                              │  Chroma向量存储(增强版)  │  │   │
│  │                              │  - 向量                │  │   │
│  │                              │  - 违规检测结果         │  │   │
│  │                              │  - 根因分类             │  │   │
│  │                              │  - 改进措施             │  │   │
│  │                              └──────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              (一次性执行)                               │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     阶段二：聚类分析与持续改进                        │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐  │   │
│  │  │ 加载向量  │──▶│ 聚类分析  │──▶│  根因统计分析          │  │   │
│  │  │ (Chroma) │  │          │  │  - 高频根因识别         │  │   │
│  │  └──────────┘  └────┬─────┘  │  - 根因趋势分析         │  │   │
│  │                     │            │  - 违规类型分布         │  │   │
│  │                     ▼            └────────┬─────────────────┘  │   │
│  │            ┌──────────────────────────┐          │              │   │
│  │            │  改进措施推荐          │          │              │   │
│  │            │  - 专项改进措施         │          │              │   │
│  │            │  - 优先级排序           │          │              │   │
│  │            │  - 责任人分配          │          │              │   │
│  │            └────────┬─────────────────┘          │              │   │
│  │                     │                               │              │   │
│  │                     ▼                               ▼              │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │  可视化展示(增强版)                                 │  │   │
│  │  │  - 根因分布图(按频率排序)                           │  │   │
│  │  │  - 违规类型分布图                                   │  │   │
│  │  │  - 聚类散点图(按根因着色)                           │  │   │
│  │  │  - 相似度热力图                                     │  │   │
│  │  │  - 改进措施追踪图                                   │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              (可重复执行)                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心组件图（修订）

```
┌────────────────────────────────────────────────────────────────┐
│                        核心组件层                                │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ DataExtractor│  │StandardKB   │  │ LLMAnalyzer │         │
│  │   (API)     │  │(规范知识库)  │  │ (增强版)     │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                     │
│         └────────────────┴────────────────┘                     │
│                          │                                   │
│                          ▼                                   │
│                   ┌─────────────┐                               │
│                   │ Violation   │                               │
│                   │ Detector    │                               │
│                   │ (违规模测)  │                               │
│                   └──────┬──────┘                               │
│                          │                                   │
│                          ▼                                   │
│                   ┌─────────────┐                               │
│                   │ RootCause   │                               │
│                   │ Validator   │                               │
│                   │ (可落地验证)  │                               │
│                   └──────┬──────┘                               │
│                          │                                   │
│                          ▼                                   │
│                   ┌─────────────┐  ┌─────────────┐  ┌────────┐ │
│                   │  Embedding  │  │   Chroma    │  │Cluster │ │
│                   │  Generator  │  │   Manager   │  │Analyzer│ │
│                   └──────┬──────┘  └──────┬──────┘  └───┬────┘ │
│                          │                │             │      │
│                          └────────────────┴─────────────┘      │
│                          │                                   │
│                          ▼                                   │
│                   ┌─────────────┐                               │
│                   │  RootCause  │                               │
│                   │ Statistics │                               │
│                   │ (根因统计)  │                               │
│                   └──────┬──────┘                               │
│                          │                                   │
│                          ▼                                   │
│                   ┌─────────────┐                               │
│                   │Improvement  │                               │
│                   │ Recommender│                               │
│                   │(改进措施推荐)│                               │
│                   └──────┬──────┘                               │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   UMAP      │  │   Plotly    │  │  Streamlit  │             │
│  │  Reducer    │  │ Visualizer  │  │    UI       │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

## 2. 新增模块详细设计

### 2.1 StandardKnowledgeBase - 规范知识库管理器

```python
class StandardKnowledgeBase:
    """规范知识库管理器"""
    
    def __init__(self, data_path: str = "./data/standards"):
        self.data_path = Path(data_path)
        self.standards: dict[str, Standard] = {}
        self._load_standards()
    
    def _load_standards(self):
        """加载所有规范"""
        for file in self.data_path.glob("*.json"):
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                standard = Standard(**data)
                self.standards[standard.standard_id] = standard
    
    def get_standards_by_category(self, category: str) -> list[Standard]:
        """按类别获取规范"""
        return [s for s in self.standards.values() 
                if s.category == category and s.status == "active"]
    
    def get_standard(self, standard_id: str) -> Standard | None:
        """获取单个规范"""
        return self.standards.get(standard_id)
    
    def search_standards(self, keyword: str) -> list[Standard]:
        """搜索规范"""
        results = []
        for standard in self.standards.values():
            if keyword.lower() in standard.title.lower() or \
               keyword.lower() in standard.content.lower():
                results.append(standard)
        return results
    
    def add_standard(self, standard: Standard):
        """添加规范"""
        self.standards[standard.standard_id] = standard
        self._save_standard(standard)
    
    def _save_standard(self, standard: Standard):
        """保存规范到文件"""
        file_path = self.data_path / f"{standard.standard_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(standard.model_dump_json(indent=2))
```

### 2.2 ViolationDetector - 违规检测器

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
        """检测故障是否违规"""
        
        # 获取相关规范
        relevant_standards = self._get_relevant_standards(task_info)
        
        # 构建检测Prompt
        prompt = self._build_detection_prompt(task_info, relevant_standards)
        
        # 调用LLM进行检测
        response = await self.llm.generate(prompt)
        
        # 解析结果
        return self._parse_detection_result(response)
    
    def _get_relevant_standards(
        self,
        task_info: TaskInfo
    ) -> list[Standard]:
        """获取相关规范"""
        # 根据故障信息推断可能相关的规范类别
        relevant_categories = []
        
        # 根据开发语言推断
        if "Java" in task_info.title or "Java" in task_info.description:
            relevant_categories.append("Java代码规范")
        elif "C++" in task_info.title or "C++" in task_info.description:
            relevant_categories.append("C++代码规范")
        
        # 根据关键词推断
        keywords = ["数据库", "SQL", "MySQL", "Oracle"]
        if any(kw in task_info.title or kw in task_info.description for kw in keywords):
            relevant_categories.append("数据库开发规范")
        
        # 获取相关规范
        standards = []
        for category in relevant_categories:
            standards.extend(self.kb.get_standards_by_category(category))
        
        return standards
    
    def _build_detection_prompt(
        self,
        task_info: TaskInfo,
        standards: list[Standard]
    ) -> str:
        """构建违规检测Prompt"""
        prompt = f"""
请分析以下故障是否存在违反公司研发规范的情况。

## 故障信息
- 故障ID: {task_info.task_id}
- 标题: {task_info.title}
- 描述: {task_info.description}
- 复盘结论: {task_info.get('review_conclusion', '无')}

## 相关研发规范
"""
        for standard in standards:
            prompt += f"""
### {standard.title}
{standard.content}
"""
        
        prompt += """
## 分析要求
1. 仔细分析故障过程和引入原因
2. 对照上述研发规范，判断是否存在违规行为
3. 如果存在违规，请明确：
   - 违反了哪条规范
   - 具体的违规行为是什么
   - 违规的证据是什么
4. 给出违规置信度（0-1之间）

## 输出格式（JSON）
{
    "has_violation": true/false,
    "violation_type": "违反Java代码规范/违反数据库开发规范等",
    "violation_detail": "具体的违规描述",
    "violated_standard_id": "规范ID",
    "confidence": 0.95,
    "evidence": ["证据1", "证据2"]
}
"""
        return prompt
    
    def _parse_detection_result(
        self,
        response: str
    ) -> ViolationDetection:
        """解析违规检测结果"""
        try:
            data = json.loads(response)
            return ViolationDetection(**data)
        except Exception as e:
            # 解析失败，返回默认值
            return ViolationDetection(
                has_violation=False,
                violation_type=None,
                violation_detail=None,
                violated_standard_id=None,
                confidence=0.0,
                evidence=[]
            )
```

### 2.3 RootCauseValidator - 根因可落地性验证器

```python
class RootCauseValidator:
    """根因可落地性验证器"""
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider
        self.validation_rules = self._load_validation_rules()
    
    def _load_validation_rules(self) -> list[dict]:
        """加载验证规则"""
        return [
            {
                "name": "改进措施必须包含动词",
                "check": lambda measures: any(
                    verb in measure for measure in measures 
                    for verb in ["添加", "修改", "优化", "完善", "增强", "修复", "删除"]
                ),
                "weight": 0.3
            },
            {
                "name": "改进措施必须明确责任人",
                "check": lambda measures: any(
                    role in measure for measure in measures 
                    for role in ["开发", "测试", "运维", "架构师", "产品经理"]
                ),
                "weight": 0.2
            },
            {
                "name": "改进措施必须包含时间节点",
                "check": lambda measures: any(
                    time in measure for measure in measures 
                    for time in ["周", "月", "季度", "立即", "尽快"]
                ),
                "weight": 0.2
            },
            {
                "name": "改进措施必须包含验证方法",
                "check": lambda measures: any(
                    verify in measure for measure in measures 
                    for verify in ["验证", "测试", "检查", "监控", "审计"]
                ),
                "weight": 0.2
            },
            {
                "name": "改进措施必须具体",
                "check": lambda measures: len(measures) > 0 and 
                           all(len(m) > 10 for m in measures),
                "weight": 0.1
            }
        ]
    
    async def validate_root_cause(
        self,
        root_cause: str,
        task_info: TaskInfo
    ) -> RootCauseValidation:
        """验证根因可落地性"""
        
        # 步骤1: 让LLM生成改进措施
        measures = await self._generate_improvement_measures(
            root_cause, task_info
        )
        
        # 步骤2: 规则验证
        validation_result = self._validate_by_rules(measures)
        
        # 步骤3: 如果不可落地，要求重新分析
        if validation_result["score"] < 0.7:
            measures = await self._regenerate_measures(
                root_cause, task_info, validation_result["failed_rules"]
            )
            validation_result = self._validate_by_rules(measures)
        
        return RootCauseValidation(
            root_cause=root_cause,
            is_actionable=validation_result["score"] >= 0.7,
            actionability_score=validation_result["score"],
            improvement_measures=measures,
            responsible_person=self._extract_responsible_person(measures),
            timeline=self._extract_timeline(measures),
            validation_method=self._extract_validation_method(measures)
        )
    
    async def _generate_improvement_measures(
        self,
        root_cause: str,
        task_info: TaskInfo
    ) -> list[str]:
        """生成改进措施"""
        prompt = f"""
针对以下根因，请生成具体的改进措施。

## 根因
{root_cause}

## 故障信息
- 故障ID: {task_info.task_id}
- 标题: {task_info.title}

## 改进措施要求
1. 必须具体、可执行
2. 必须包含明确的动作动词（如添加、修改、优化等）
3. 必须明确责任人或角色
4. 必须包含时间节点
5. 必须包含验证方法
6. 每条措施要能从根本上解决问题

## 输出格式（JSON）
{{
    "improvement_measures": [
        "措施1",
        "措施2",
        "措施3"
    ]
}}
"""
        response = await self.llm.generate(prompt)
        data = json.loads(response)
        return data.get("improvement_measures", [])
    
    def _validate_by_rules(self, measures: list[str]) -> dict:
        """使用规则验证改进措施"""
        total_score = 0.0
        failed_rules = []
        
        for rule in self.validation_rules:
            if rule["check"](measures):
                total_score += rule["weight"]
            else:
                failed_rules.append(rule["name"])
        
        return {
            "score": total_score,
            "failed_rules": failed_rules
        }
    
    async def _regenerate_measures(
        self,
        root_cause: str,
        task_info: TaskInfo,
        failed_rules: list[str]
    ) -> list[str]:
        """重新生成改进措施"""
        prompt = f"""
之前的改进措施不符合以下要求：
{chr(10).join(f"- {rule}" for rule in failed_rules)}

请针对以下根因重新生成改进措施，确保符合上述要求。

## 根因
{root_cause}

## 输出格式（JSON）
{{
    "improvement_measures": [
        "措施1",
        "措施2",
        "措施3"
    ]
}}
"""
        response = await self.llm.generate(prompt)
        data = json.loads(response)
        return data.get("improvement_measures", [])
    
    def _extract_responsible_person(self, measures: list[str]) -> str | None:
        """提取责任人"""
        for measure in measures:
            if "开发" in measure:
                return "开发团队"
            elif "测试" in measure:
                return "测试团队"
            elif "运维" in measure:
                return "运维团队"
        return None
    
    def _extract_timeline(self, measures: list[str]) -> str | None:
        """提取时间节点"""
        for measure in measures:
            if "立即" in measure:
                return "立即"
            elif "周" in measure:
                return "1周内"
            elif "月" in measure:
                return "1个月内"
        return None
    
    def _extract_validation_method(self, measures: list[str]) -> str | None:
        """提取验证方法"""
        for measure in measures:
            if "验证" in measure:
                return "验证"
            elif "测试" in measure:
                return "测试"
            elif "监控" in measure:
                return "监控"
        return None
```

### 2.4 RootCauseStatistics - 根因统计分析器

```python
class RootCauseStatistics:
    """根因统计分析器"""
    
    def __init__(self):
        self.statistics: dict[str, RootCauseStat] = {}
    
    def analyze(
        self,
        tasks: list[dict]
    ) -> dict[str, RootCauseStat]:
        """分析根因统计"""
        
        # 统计每个根因的出现次数
        root_cause_counts: dict[str, list[int]] = {}
        for task in tasks:
            root_cause = task.get("root_cause_category", "未知")
            if root_cause not in root_cause_counts:
                root_cause_counts[root_cause] = []
            root_cause_counts[root_cause].append(task["task_id"])
        
        # 计算统计信息
        total_tasks = len(tasks)
        for root_cause, task_ids in root_cause_counts.items():
            count = len(task_ids)
            percentage = count / total_tasks * 100
            
            self.statistics[root_cause] = RootCauseStat(
                root_cause=root_cause,
                count=count,
                percentage=percentage,
                trend=self._calculate_trend(task_ids),
                top_faults=task_ids[:10]  # Top 10
            )
        
        return self.statistics
    
    def _calculate_trend(self, task_ids: list[int]) -> str:
        """计算趋势（需要时间信息）"""
        # TODO: 实现趋势计算逻辑
        return "stable"
    
    def get_top_root_causes(self, n: int = 5) -> list[RootCauseStat]:
        """获取Top N高频根因"""
        sorted_stats = sorted(
            self.statistics.values(),
            key=lambda x: x.count,
            reverse=True
        )
        return sorted_stats[:n]
    
    def get_violation_statistics(self, tasks: list[dict]) -> dict:
        """获取违规统计"""
        violation_counts: dict[str, int] = {}
        total_violations = 0
        
        for task in tasks:
            if task.get("has_violation", False):
                violation_type = task.get("violation_type", "未知")
                violation_counts[violation_type] = violation_counts.get(violation_type, 0) + 1
                total_violations += 1
        
        return {
            "total_violations": total_violations,
            "violation_distribution": violation_counts
        }
```

### 2.5 ImprovementRecommender - 改进措施推荐器

```python
class ImprovementRecommender:
    """改进措施推荐器"""
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider
    
    async def recommend_improvements(
        self,
        root_cause_stats: list[RootCauseStat],
        tasks: list[dict]
    ) -> list[ImprovementMeasure]:
        """推荐改进措施"""
        
        recommendations = []
        
        for stat in root_cause_stats:
            # 获取该根因对应的所有故障
            related_tasks = [
                task for task in tasks 
                if task.get("root_cause_category") == stat.root_cause
            ]
            
            # 生成专项改进措施
            measure = await self._generate_special_improvement(
                stat.root_cause,
                related_tasks
            )
            
            recommendations.append(measure)
        
        # 按优先级排序
        recommendations.sort(key=lambda x: self._priority_to_score(x.priority), reverse=True)
        
        return recommendations
    
    async def _generate_special_improvement(
        self,
        root_cause: str,
        related_tasks: list[dict]
    ) -> ImprovementMeasure:
        """生成专项改进措施"""
        
        # 提取关键信息
        task_summaries = [
            f"- 故障{task['task_id']}: {task['title']}"
            for task in related_tasks[:5]
        ]
        
        prompt = f"""
针对以下高频根因，请制定专项改进措施。

## 根因
{root_cause}

## 相关故障（示例）
{chr(10).join(task_summaries)}

## 改进措施要求
1. 必须是专项措施，能从根本上解决该类问题
2. 必须明确责任人和时间节点
3. 必须包含验证方法
4. 必须评估预期影响
5. 措施要具体、可执行

## 输出格式（JSON）
{{
    "measure_id": "唯一ID",
    "root_cause": "{root_cause}",
    "description": "详细的改进措施描述",
    "priority": "high/medium/low",
    "responsible_person": "责任人或团队",
    "timeline": "时间节点",
    "expected_impact": "预期影响",
    "validation_criteria": ["验证标准1", "验证标准2"]
}}
"""
        response = await self.llm.generate(prompt)
        data = json.loads(response)
        return ImprovementMeasure(**data)
    
    def _priority_to_score(self, priority: str) -> int:
        """优先级转换为分数"""
        mapping = {"high": 3, "medium": 2, "low": 1}
        return mapping.get(priority, 0)
```

## 3. 数据模型（修订）

### 3.1 新增数据模型

```python
class Standard(BaseModel):
    """研发规范"""
    standard_id: str
    category: str  # 代码规范/数据库规范/测试规范等
    sub_category: str  # Java/C++/MySQL等
    title: str
    content: str
    version: str
    effective_date: datetime
    status: str  # active/deprecated


class ViolationDetection(BaseModel):
    """违规检测结果"""
    has_violation: bool
    violation_type: str | None
    violation_detail: str | None
    violated_standard_id: str | None
    confidence: float
    evidence: list[str]


class RootCauseValidation(BaseModel):
    """根因可落地性验证"""
    root_cause: str
    is_actionable: bool
    actionability_score: float
    improvement_measures: list[str]
    responsible_person: str | None
    timeline: str | None
    validation_method: str | None


class RootCauseStat(BaseModel):
    """根因统计"""
    root_cause: str
    count: int
    percentage: float
    trend: str
    top_faults: list[int]


class ImprovementMeasure(BaseModel):
    """改进措施"""
    measure_id: str
    root_cause: str
    description: str
    priority: str
    responsible_person: str
    timeline: str
    expected_impact: str
    validation_criteria: list[str]
    status: str = "pending"
```

### 3.2 Chroma集合Schema（修订）

```python
# Collection: fault_embeddings (增强版)
{
    "ids": ["task_11751534", "task_11751363", ...],
    "embeddings": [[0.1, 0.2, ...], [0.3, 0.4, ...], ...],
    "metadatas": [
        {
            # 基础信息
            "task_id": 11751534,
            "title": "催缴邮件重复发送",
            "priority": "P3",
            "create_time": "2024-01-15",
            "status": "closed",
            
            # 违规检测结果
            "has_violation": True,
            "violation_type": "违反Java代码规范",
            "violation_detail": "未实现幂等性控制",
            "violated_standard_id": "java_standard_001",
            "violation_confidence": 0.95,
            
            # 根因信息
            "root_cause_category": "违反Java代码规范",
            "root_cause_detail": "未实现幂等性控制",
            
            # 可落地性验证
            "is_actionable": True,
            "actionability_score": 0.85,
            
            # 改进措施
            "improvement_measures": [
                "添加幂等性校验逻辑",
                "引入分布式锁机制"
            ],
            "responsible_person": "开发团队",
            "timeline": "1周内",
            
            # 聚类信息
            "cluster_id": 2,
            
            # 时间戳
            "analysis_timestamp": "2024-03-05T10:30:00"
        },
        ...
    ],
    "documents": [
        "催缴邮件重复发送 违反Java代码规范 未实现幂等性控制...",
        ...
    ]
}
```

## 4. 可视化设计（修订）

### 4.1 根因分布图

```python
def create_root_cause_distribution_chart(
    statistics: list[RootCauseStat]
) -> go.Figure:
    """创建根因分布图"""
    
    # 按频率排序
    sorted_stats = sorted(statistics, key=lambda x: x.count, reverse=True)
    
    fig = go.Figure(data=[
        go.Bar(
            x=[stat.root_cause for stat in sorted_stats],
            y=[stat.count for stat in sorted_stats],
            text=[f"{stat.percentage:.1f}%" for stat in sorted_stats],
            textposition='auto',
            marker=dict(color=px.colors.qualitative.Set3)
        )
    ])
    
    fig.update_layout(
        title="根因分布（按频率排序）",
        xaxis_title="根因类型",
        yaxis_title="故障数量",
        hovermode='closest'
    )
    
    return fig
```

### 4.2 违规类型分布图

```python
def create_violation_distribution_chart(
    violation_stats: dict
) -> go.Figure:
    """创建违规类型分布图"""
    
    violation_types = list(violation_stats["violation_distribution"].keys())
    counts = list(violation_stats["violation_distribution"].values())
    
    fig = go.Figure(data=[
        go.Pie(
            labels=violation_types,
            values=counts,
            hole=0.3,
            marker=dict(colors=px.colors.qualitative.Pastel1)
        )
    ])
    
    fig.update_layout(
        title=f"违规类型分布（共{violation_stats['total_violations']}起违规）",
        annotations=[dict(text='违规', x=0.5, y=0.5, font_size=20, showarrow=False)]
    )
    
    return fig
```

### 4.3 改进措施追踪图

```python
def create_improvement_tracking_chart(
    measures: list[ImprovementMeasure]
) -> go.Figure:
    """创建改进措施追踪图"""
    
    # 按优先级分组
    priority_order = {"high": 0, "medium": 1, "low": 2}
    sorted_measures = sorted(
        measures,
        key=lambda x: priority_order.get(x.priority, 3)
    )
    
    fig = go.Figure()
    
    for priority in ["high", "medium", "low"]:
        priority_measures = [m for m in sorted_measures if m.priority == priority]
        if priority_measures:
            fig.add_trace(go.Bar(
                name=priority,
                x=[m.measure_id for m in priority_measures],
                y=[m.timeline for m in priority_measures],
                text=[m.responsible_person for m in priority_measures],
                textposition='auto',
                marker=dict(
                    color={"high": "red", "medium": "orange", "low": "green"}[priority]
                )
            ))
    
    fig.update_layout(
        title="改进措施追踪",
        xaxis_title="措施ID",
        yaxis_title="时间节点",
        barmode='group',
        hovermode='closest'
    )
    
    return fig
```

## 5. Streamlit界面设计（修订）

### 5.1 主界面布局

```
┌────────────────────────────────────────────────────────────────┐
│                    故障聚类分析系统 V3                           │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  标签页: [数据准备] [聚类分析] [根因统计] [改进措施]      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────┐  ┌────────────────────────────────┐  │
│  │    控制面板           │  │         可视化区域              │  │
│  │                      │  │                                │  │
│  │  聚类算法: [下拉框]   │  │   ┌────────────────────────┐   │  │
│  │  - HDBSCAN           │  │   │                        │   │  │
│  │  - 层次聚类          │  │   │    根因分布图           │   │  │
│  │  - K-Means           │  │   │                        │   │  │
│  │                      │  │   │   ████ ████ ████      │   │  │
│  │  最小聚类大小: [滑块] │  │   │   ████ ████ ████      │   │  │
│  │  距离度量: [下拉框]   │  │   │                        │   │  │
│  │                      │  │   └────────────────────────┘   │  │
│  │  [执行聚类] 按钮     │  │                                │  │
│  │                      │  │   ┌────────────────────────┐   │  │
│  │  根因统计:           │  │   │      违规类型分布图       │   │  │
│  │  - 总故障数: 100     │  │   │                        │   │  │
│  │  - 违规故障: 35      │  │   │       ●  ●  ●         │   │  │
│  │  - 违规率: 35%      │  │   │     ●    ●  ●         │   │  │
│  │  - Top根因:         │  │   │   ●  ●    ●         │   │  │
│  │    1. 违反Java规范   │  │   │                        │   │  │
│  │    2. 违反DB规范     │  │   └────────────────────────┘   │  │
│  │    3. 边界条件处理不当 │  │                                │  │
│  │                      │  │   ┌────────────────────────┐   │  │
│  └──────────────────────┘  │   │    聚类散点图          │   │  │
│                            │   │                        │   │  │
│                            │   │   ●  ●    ●          │   │  │
│                            │   │      ●  ●  ●          │   │  │
│                            │   │   ●    ●             │   │  │
│                            │   │                        │   │  │
│                            │   └────────────────────────┘   │  │
│                            │                                │  │
│                            └────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    改进措施表格                           │  │
│  │  | 措施ID | 根因 | 优先级 | 责任人 | 时间节点 | 状态 |  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

**文档版本**: V3.0  
**创建日期**: 2026-03-05  
**状态**: 待评审
