# 故障聚类分析系统 V2 - 系统设计文档

## 1. 系统架构概览

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           故障聚类分析系统 V2                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     阶段一：数据准备与向量化                        │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │   │
│  │  │  API数据提取  │───▶│  信息整合    │───▶│  Embedding生成   │  │   │
│  │  └──────────────┘    └──────────────┘    └────────┬─────────┘  │   │
│  │                                                   │            │   │
│  │                                                   ▼            │   │
│  │                                          ┌──────────────────┐  │   │
│  │                                          │  Chroma向量存储   │  │   │
│  │                                          └──────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              (一次性执行)                               │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     阶段二：聚类分析与可视化                        │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │   │
│  │  │ 加载向量数据  │───▶│  聚类分析    │───▶│  结果可视化      │  │   │
│  │  │  (Chroma)    │    │ (HDBSCAN等)  │    │ (UMAP/Plotly)    │  │   │
│  │  └──────────────┘    └──────┬───────┘    └──────────────────┘  │   │
│  │                             │                                   │   │
│  │                             ▼                                   │   │
│  │                    ┌──────────────────┐                        │   │
│  │                    │  交互式探索      │                        │   │
│  │                    │  - 参数调整      │                        │   │
│  │                    │  - 相似度查询    │                        │   │
│  │                    │  - 聚类解释      │                        │   │
│  │                    └──────────────────┘                        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              (可重复执行)                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心组件图

```
┌────────────────────────────────────────────────────────────────┐
│                        核心组件层                                │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────┐ │
│  │ DataExtractor│  │  Embedding  │  │   Chroma    │  │Cluster │ │
│  │   (API)     │  │  Generator  │  │   Manager   │  │Analyzer│ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └───┬────┘ │
│         │                │                │             │      │
│         └────────────────┴────────────────┴─────────────┘      │
│                          │                                      │
│                          ▼                                      │
│                   ┌─────────────┐                               │
│                   │  Analyzer   │                               │
│                   │   Engine    │                               │
│                   └──────┬──────┘                               │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   UMAP      │  │   Plotly    │  │  Streamlit  │             │
│  │  Reducer    │  │ Visualizer  │  │    UI       │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

## 2. 数据流设计

### 2.1 阶段一：数据准备与向量化

```
故障单ID列表
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. 数据提取 (DataExtractor)                                  │
│    - 调用API获取故障单详情                                    │
│    - 调用API获取代码提交记录                                  │
│    - 调用API获取生产环境信息                                  │
│    - 整合所有信息为TaskInfo对象                               │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. LLM深度分析 (LLMAnalyzer)                                 │
│    - 构建分析Prompt（包含故障标题、描述、复盘结论等）          │
│    - 调用火山引擎LLM进行根因分析                              │
│    - 提取：根因分类、根因详情、受影响阶段、严重程度、改进建议   │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. 文本构建 (TextBuilder)                                    │
│    - 整合故障标题 + LLM分析结果                               │
│    - 生成用于向量化的分析文本                                 │
│    示例："催缴邮件重复发送 代码bug 未实现幂等性控制..."        │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. 向量化 (EmbeddingGenerator)                               │
│    - 调用火山引擎Embedding API                               │
│    - 生成固定维度向量（如2048维）                             │
│    - 每个故障单对应一个向量                                   │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. 向量存储 (ChromaManager)                                  │
│    - 存储向量到Chroma集合                                     │
│    - 存储元数据：task_id, title, priority, create_time等     │
│    - 存储原始分析文本（用于后续查询）                          │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 阶段二：聚类分析与可视化

```
从Chroma加载向量和元数据
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. 数据加载 (ChromaManager.load_collection)                  │
│    - 查询所有向量                                             │
│    - 获取对应的元数据                                         │
│    - 构建numpy数组                                            │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. 聚类分析 (ClusterAnalyzer)                                │
│    - 参数配置：algorithm, min_cluster_size, metric等         │
│    - 执行聚类算法（HDBSCAN/层次聚类/K-Means）                 │
│    - 生成聚类标签                                             │
│    - 计算聚类中心                                             │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. 降维可视化 (UMAPReducer + Visualizer)                     │
│    - UMAP降维到2D/3D                                         │
│    - 生成散点图                                               │
│    - 按聚类ID着色                                             │
│    - 添加悬停提示（显示故障详情）                              │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. 相似度计算 (SimilarityCalculator)                         │
│    - 计算故障间相似度矩阵                                     │
│    - 生成热力图                                               │
│    - 支持查询最相似故障                                       │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. 交互式界面 (Streamlit UI)                                 │
│    - 参数调整面板                                             │
│    - 可视化展示                                               │
│    - 相似度查询                                               │
│    - 聚类结果导出                                             │
└─────────────────────────────────────────────────────────────┘
```

## 3. 模块详细设计

### 3.1 ChromaManager - 向量数据库管理器

```python
class ChromaManager:
    """Chroma向量数据库管理器"""
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = None
    
    def create_collection(self, name: str = "fault_embeddings"):
        """创建集合"""
        self.collection = self.client.create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_embeddings(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        documents: list[str]
    ):
        """添加向量"""
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )
    
    def get_all(self) -> tuple[list, list, list]:
        """获取所有向量"""
        result = self.collection.get(include=["embeddings", "metadatas", "documents"])
        return result["ids"], result["embeddings"], result["metadatas"]
    
    def query_similar(
        self,
        query_embedding: list[float],
        n_results: int = 5
    ) -> list[dict]:
        """查询相似向量"""
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["metadatas", "documents", "distances"]
        )
    
    def update_metadata(self, ids: list[str], metadatas: list[dict]):
        """更新元数据（如聚类结果）"""
        self.collection.update(ids=ids, metadatas=metadatas)
```

### 3.2 ClusterAnalyzer - 聚类分析器（增强版）

```python
class ClusterAnalyzer:
    """支持多种算法的聚类分析器"""
    
    SUPPORTED_ALGORITHMS = ["hdbscan", "hierarchical", "kmeans", "dbscan"]
    SUPPORTED_METRICS = ["cosine", "euclidean", "manhattan"]
    
    def __init__(
        self,
        algorithm: str = "hdbscan",
        min_cluster_size: int = 3,
        min_samples: int = 2,
        n_clusters: int | None = None,  # For K-Means
        metric: str = "cosine"
    ):
        self.algorithm = algorithm
        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.n_clusters = n_clusters
        self.metric = metric
        self._model = None
        self.labels_ = None
    
    def fit_predict(self, embeddings: np.ndarray) -> np.ndarray:
        """执行聚类"""
        # 归一化（用于余弦相似度）
        if self.metric == "cosine":
            embeddings = self._normalize(embeddings)
        
        if self.algorithm == "hdbscan":
            self.labels_ = self._fit_hdbscan(embeddings)
        elif self.algorithm == "hierarchical":
            self.labels_ = self._fit_hierarchical(embeddings)
        elif self.algorithm == "kmeans":
            self.labels_ = self._fit_kmeans(embeddings)
        elif self.algorithm == "dbscan":
            self.labels_ = self._fit_dbscan(embeddings)
        
        return self.labels_
    
    def _normalize(self, embeddings: np.ndarray) -> np.ndarray:
        """L2归一化"""
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        return embeddings / norms
    
    def get_cluster_info(self) -> list[ClusterInfo]:
        """获取聚类详细信息"""
        # 计算每个簇的大小、中心点、成员等
        pass
    
    def get_silhouette_score(self) -> float:
        """计算轮廓系数评估聚类质量"""
        from sklearn.metrics import silhouette_score
        return silhouette_score(embeddings, self.labels_)
```

### 3.3 UMAPVisualizer - 降维可视化器

```python
class UMAPVisualizer:
    """UMAP降维和可视化"""
    
    def __init__(
        self,
        n_components: int = 2,
        n_neighbors: int = 15,
        min_dist: float = 0.1,
        random_state: int = 42
    ):
        self.n_components = n_components
        self.n_neighbors = n_neighbors
        self.min_dist = min_dist
        self.random_state = random_state
        self.reducer = None
    
    def fit_transform(self, embeddings: np.ndarray) -> np.ndarray:
        """降维"""
        import umap
        self.reducer = umap.UMAP(
            n_components=self.n_components,
            n_neighbors=self.n_neighbors,
            min_dist=self.min_dist,
            random_state=self.random_state,
            metric="cosine"
        )
        return self.reducer.fit_transform(embeddings)
    
    def create_scatter_plot(
        self,
        reduced_embeddings: np.ndarray,
        labels: np.ndarray,
        metadata: list[dict],
        title: str = "故障聚类可视化"
    ) -> go.Figure:
        """创建散点图"""
        import plotly.graph_objects as go
        
        fig = go.Figure()
        
        # 为每个聚类添加散点
        unique_labels = set(labels)
        for label in unique_labels:
            mask = labels == label
            cluster_data = reduced_embeddings[mask]
            cluster_meta = [m for m, msk in zip(metadata, mask) if msk]
            
            fig.add_trace(go.Scatter(
                x=cluster_data[:, 0],
                y=cluster_data[:, 1],
                mode='markers+text',
                name=f'聚类 {label}' if label != -1 else '噪声',
                text=[m.get('task_id', '') for m in cluster_meta],
                hovertemplate='<b>故障单:</b> %{text}<br>' +
                             '<b>标题:</b> %{customdata[0]}<br>' +
                             '<b>聚类:</b> %{customdata[1]}<extra></extra>',
                customdata=[[m.get('title', ''), label] for m in cluster_meta],
                marker=dict(size=10, opacity=0.7)
            ))
        
        fig.update_layout(
            title=title,
            xaxis_title="UMAP 1",
            yaxis_title="UMAP 2",
            hovermode='closest'
        )
        
        return fig
```

### 3.4 SimilarityCalculator - 相似度计算器

```python
class SimilarityCalculator:
    """相似度计算和查询"""
    
    def __init__(self, metric: str = "cosine"):
        self.metric = metric
    
    def compute_similarity_matrix(
        self,
        embeddings: np.ndarray
    ) -> np.ndarray:
        """计算相似度矩阵"""
        from sklearn.metrics.pairwise import cosine_similarity
        return cosine_similarity(embeddings)
    
    def find_similar_faults(
        self,
        query_idx: int,
        embeddings: np.ndarray,
        top_k: int = 5
    ) -> list[tuple[int, float]]:
        """查找与指定故障最相似的其他故障"""
        sim_matrix = self.compute_similarity_matrix(embeddings)
        similarities = sim_matrix[query_idx]
        
        # 排除自身，取top_k
        similar_indices = np.argsort(similarities)[::-1][1:top_k+1]
        return [(idx, similarities[idx]) for idx in similar_indices]
    
    def create_heatmap(
        self,
        similarity_matrix: np.ndarray,
        labels: np.ndarray,
        task_ids: list[str]
    ) -> go.Figure:
        """创建相似度热力图"""
        import plotly.express as px
        
        # 按聚类标签排序
        sorted_indices = np.argsort(labels)
        sorted_matrix = similarity_matrix[sorted_indices][:, sorted_indices]
        sorted_ids = [task_ids[i] for i in sorted_indices]
        
        fig = px.imshow(
            sorted_matrix,
            x=sorted_ids,
            y=sorted_ids,
            color_continuous_scale="Viridis",
            title="故障相似度热力图"
        )
        
        return fig
```

## 4. 交互式界面设计

### 4.1 Streamlit界面布局

```
┌────────────────────────────────────────────────────────────────┐
│                    故障聚类分析系统 V2                           │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  标签页: [数据准备] [聚类分析] [相似度查询] [结果导出]      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────┐  ┌────────────────────────────────┐  │
│  │    控制面板           │  │         可视化区域              │  │
│  │                      │  │                                │  │
│  │  聚类算法: [下拉框]   │  │   ┌────────────────────────┐   │  │
│  │  - HDBSCAN           │  │   │                        │   │  │
│  │  - 层次聚类          │  │   │    UMAP散点图           │   │  │
│  │  - K-Means           │  │   │                        │   │  │
│  │                      │  │   │   ●  ●    ●             │   │  │
│  │  最小聚类大小: [滑块] │  │   │      ●  ●  ●            │   │  │
│  │  距离度量: [下拉框]   │  │   │   ●    ●                │   │  │
│  │                      │  │   │                        │   │  │
│  │  [执行聚类] 按钮     │  │   └────────────────────────┘   │  │
│  │                      │  │                                │  │
│  │  聚类统计:           │  │   ┌────────────────────────┐   │  │
│  │  - 聚类数量: 5       │  │   │      热力图             │   │  │
│  │  - 噪声点: 2         │  │   │                        │   │  │
│  │  - 轮廓系数: 0.65    │  │   └────────────────────────┘   │  │
│  │                      │  │                                │  │
│  └──────────────────────┘  └────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    聚类详情表格                           │  │
│  │  | 聚类ID | 故障数量 | 主要根因 | 样本故障 | 操作 |       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### 4.2 界面交互流程

1. **数据准备标签页**
   - 输入故障单ID列表
   - 点击"提取并向量化"按钮
   - 显示进度条和状态
   - 完成后提示保存到Chroma

2. **聚类分析标签页**
   - 从Chroma加载数据
   - 调整聚类参数
   - 实时显示UMAP散点图
   - 显示聚类统计信息
   - 显示热力图

3. **相似度查询标签页**
   - 选择查询故障单
   - 设置相似度阈值
   - 显示最相似的N个故障
   - 显示相似度分数

4. **结果导出标签页**
   - 导出聚类结果为CSV
   - 导出可视化图表为PNG/PDF
   - 导出完整分析报告为Markdown

## 5. 数据模型设计

### 5.1 Chroma集合Schema

```python
# Collection: fault_embeddings
{
    "ids": ["task_11751534", "task_11751363", ...],
    "embeddings": [[0.1, 0.2, ...], [0.3, 0.4, ...], ...],
    "metadatas": [
        {
            "task_id": 11751534,
            "title": "催缴邮件重复发送",
            "priority": "P3",
            "create_time": "2024-01-15",
            "status": "closed",
            "root_cause_category": "代码bug",
            "affected_stage": "生产",
            "severity": "中",
            "cluster_id": 2,  # 聚类后更新
            "analysis_timestamp": "2024-03-05T10:30:00"
        },
        ...
    ],
    "documents": [
        "催缴邮件重复发送 代码bug 未实现幂等性控制...",
        ...
    ]
}
```

### 5.2 聚类结果模型

```python
class ClusterResult(BaseModel):
    """聚类结果"""
    algorithm: str
    parameters: dict
    labels: list[int]
    n_clusters: int
    n_noise: int
    silhouette_score: float
    clusters: list[ClusterDetail]
    timestamp: datetime

class ClusterDetail(BaseModel):
    """单个聚类详情"""
    cluster_id: int
    size: int
    centroid: list[float]
    member_indices: list[int]
    member_task_ids: list[int]
    dominant_root_cause: str  # 主要根因
    common_keywords: list[str]  # 共同关键词
```

## 6. 接口设计

### 6.1 核心类接口

```python
# 主分析引擎
class FaultClusteringEngine:
    def __init__(self, config: Config):
        self.data_extractor = DataExtractor(config.api)
        self.llm_analyzer = LLMAnalyzer(config.llm)
        self.embedding_gen = EmbeddingGenerator(config.embedding)
        self.chroma_manager = ChromaManager(config.chroma_path)
        self.cluster_analyzer = ClusterAnalyzer()
        self.visualizer = UMAPVisualizer()
        self.similarity_calc = SimilarityCalculator()
    
    async def phase1_prepare_data(
        self,
        task_ids: list[int]
    ) -> list[FaultEmbedding]:
        """阶段一：数据准备"""
        pass
    
    def phase2_cluster_analysis(
        self,
        algorithm: str = "hdbscan",
        **kwargs
    ) -> ClusterResult:
        """阶段二：聚类分析"""
        pass
    
    def visualize_clusters(
        self,
        cluster_result: ClusterResult,
        plot_type: str = "scatter"
    ) -> go.Figure:
        """可视化聚类结果"""
        pass
    
    def find_similar_faults(
        self,
        task_id: int,
        top_k: int = 5
    ) -> list[SimilarFault]:
        """查找相似故障"""
        pass
```

## 7. 部署与运行

### 7.1 目录结构

```
project/
├── src/
│   ├── api/              # API客户端
│   ├── embedding/        # 向量化
│   ├── storage/          # Chroma管理
│   ├── clustering/       # 聚类算法
│   ├── visualization/    # 可视化
│   ├── analysis/         # 分析引擎
│   └── ui/               # Streamlit界面
├── data/
│   └── chroma_db/        # 向量数据库
├── output/
│   ├── visualizations/   # 可视化图表
│   └── reports/          # 分析报告
├── docs/
│   └── 任务名/            # 设计文档
├── tests/
├── app.py                # Streamlit入口
├── phase1_prepare.py     # 阶段一脚本
├── phase2_analyze.py     # 阶段二脚本
└── config.yaml
```

### 7.2 使用流程

```bash
# 1. 安装依赖
pip install -e ".[dev]"

# 2. 阶段一：数据准备（一次性）
python phase1_prepare.py --task-ids 11751534,11751363,...

# 3. 阶段二：交互式分析
streamlit run app.py

# 或在命令行执行聚类
python phase2_analyze.py --algorithm hdbscan --min-cluster-size 3
```

---

**文档版本**: V1.0  
**创建日期**: 2026-03-05  
**状态**: 待评审
