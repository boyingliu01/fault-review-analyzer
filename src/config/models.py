from pydantic import BaseModel, Field, field_validator


class APIConfig(BaseModel):
    base_url: str = Field(default="", description="API基础URL")
    timeout: int = Field(default=30, ge=1, description="请求超时时间(秒)")
    retry: int = Field(default=3, ge=0, le=10, description="重试次数")
    api_key: str = Field(default="", description="API认证token")
    rate_limit_qps: float = Field(
        default=0.0, ge=0.0, description="API请求速率限制(QPS)，0表示不限制"
    )
    api_path_prefix: str = Field(
        default="/portal/ai-gateway/devspace/rpc/v3/work-item", description="API路径前缀"
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("timeout must be greater than 0")
        return v


class LLMConfig(BaseModel):
    provider: str = Field(default="openai", description="LLM服务提供商")
    model: str = Field(default="gpt-4", description="模型名称")
    api_key: str = Field(default="", description="API密钥")
    temperature: float = Field(default=0.2, ge=0.0, le=1.0, description="温度参数")
    max_tokens: int = Field(default=4096, ge=1, le=128000, description="最大token数")
    base_url: str = Field(default="", description="API基础URL(可选)")


class EmbeddingConfig(BaseModel):
    provider: str = Field(default="openai", description="Embedding服务提供商")
    model: str = Field(default="text-embedding-3-small", description="模型名称")
    api_key: str = Field(default="", description="API密钥")
    base_url: str = Field(default="", description="API基础URL(可选)")
    batch_size: int = Field(default=100, ge=1, le=512, description="批量嵌入时的最大文本条数")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = [
            "openai",
            "bge",
            "m3e",
            "codebert",
            "zhipu",
            "local",
            "volcengine",
            "custom",
            "whalecloud",
            "sentence-transformers",
        ]
        if v not in allowed:
            raise ValueError(f"provider must be one of {allowed}")
        return v


class ClusteringConfig(BaseModel):
    algorithm: str = Field(default="hdbscan", description="聚类算法")
    min_cluster_size: int = Field(default=5, ge=2, description="最小聚类大小")
    min_samples: int = Field(default=3, ge=1, description="最小样本数")
    metric: str = Field(default="cosine", description="距离度量")

    @field_validator("algorithm")
    @classmethod
    def validate_algorithm(cls, v: str) -> str:
        allowed = ["hdbscan", "kmeans", "dbscan"]
        if v not in allowed:
            raise ValueError(f"algorithm must be one of {allowed}")
        return v

    @field_validator("metric")
    @classmethod
    def validate_metric(cls, v: str) -> str:
        allowed = ["cosine", "euclidean", "manhattan"]
        if v not in allowed:
            raise ValueError(f"metric must be one of {allowed}")
        return v


class CacheConfig(BaseModel):
    enabled: bool = Field(default=True, description="是否启用缓存")
    ttl: int = Field(default=86400, ge=0, description="缓存过期时间(秒)")
    storage: str = Field(default="sqlite", description="存储类型")
    db_path: str = Field(default="./data/cache/cache.db", description="缓存数据库路径")

    @field_validator("storage")
    @classmethod
    def validate_storage(cls, v: str) -> str:
        allowed = ["sqlite", "file", "memory"]
        if v not in allowed:
            raise ValueError(f"storage must be one of {allowed}")
        return v


class RulesConfig(BaseModel):
    builtin_enabled: bool = Field(default=True, description="是否启用内置规范")
    custom_paths: list[str] = Field(default_factory=list, description="自定义规范路径")


class OutputConfig(BaseModel):
    format: str = Field(default="markdown", description="输出格式")
    directory: str = Field(default="./output/", description="输出目录")

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        allowed = ["markdown", "html", "json"]
        if v not in allowed:
            raise ValueError(f"format must be one of {allowed}")
        return v


class LoggingConfig(BaseModel):
    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(
        default="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        description="日志格式",
    )
    file: str | None = Field(default=None, description="日志文件路径")

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"level must be one of {allowed}")
        return v_upper


class ReviewerConfig(BaseModel):
    """单个 Delphi 评审专家配置。"""

    persona: str = Field(default="strict_rule_checker", description="评审视角标识")
    model: str = Field(default="", description="覆盖主LLM模型名（空=继承主配置）")
    base_url: str = Field(default="", description="覆盖LLM base_url（空=继承主配置）")
    api_key: str = Field(default="", description="覆盖API密钥（空=继承主配置）")
    temperature: float = Field(default=0.1, ge=0.0, le=1.0, description="评审温度")


class ConclusionReviewConfig(BaseModel):
    """结论域 Delphi 复审配置（复盘根因结论 confirmed/refuted 复核）。

    双模型交叉专家（事实核对 + 修复/引入判定）。base_url/api_key 省略时继承
    主 LLM 配置（当前 .env 指向 whalecloud 网关）；主配置切换网关后双模型名
    将失效（复审全兜底 diverged，可观测），生产环境建议显式覆盖。
    """

    enabled: bool = Field(
        default=False,
        description="是否启用结论Delphi复审（默认灰度关闭，批量脚本编程传参显式启用）",
    )
    max_rounds: int = Field(default=2, ge=1, le=5, description="最大评审轮数")
    context_lines: int = Field(default=12, ge=2, le=50, description="证据命中行上下文行数")
    reviewers: list[ReviewerConfig] = Field(
        default_factory=lambda: [
            ReviewerConfig(persona="fact_evidence_auditor", model="g-deepseek-v4-flash"),
            ReviewerConfig(persona="fix_vs_intro_discriminator", model="g-qwen3.8-flash"),
        ],
        description="评审专家列表（独立会话互不可见，匿名互评）",
    )


class DelphiReviewConfig(BaseModel):
    """Delphi 式违规复审配置（多专家匿名多轮共识，类似代码走查）。

    初筛（正则）召回高但精确率有限，语义级判定（集合是否跨线程共享、
    拼接目标是否用户输入、语言是否匹配条款）交给独立评审专家复核。
    """

    enabled: bool = Field(default=False, description="是否启用违规Delphi复审")
    max_rounds: int = Field(default=2, ge=1, le=5, description="最大评审轮数")
    context_lines: int = Field(default=12, ge=2, le=50, description="命中行上下文行数")
    reviewers: list[ReviewerConfig] = Field(
        default_factory=lambda: [
            ReviewerConfig(persona="strict_rule_checker"),
            ReviewerConfig(persona="runtime_behavior_analyst"),
        ],
        description="评审专家列表（独立会话互不可见，匿名互评）",
    )
    conclusion_review: ConclusionReviewConfig = Field(
        default_factory=ConclusionReviewConfig,
        description="结论域复审配置（review.conclusion_review 段，独立灰度开关）",
    )


class AppConfig(BaseModel):
    api: APIConfig = Field(default_factory=APIConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    clustering: ClusteringConfig = Field(default_factory=ClusteringConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    rules: RulesConfig = Field(default_factory=RulesConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    review: DelphiReviewConfig = Field(default_factory=DelphiReviewConfig)
