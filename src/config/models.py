
from pydantic import BaseModel, Field, field_validator


class APIConfig(BaseModel):
    base_url: str = Field(default="", description="API基础URL")
    timeout: int = Field(default=30, ge=1, description="请求超时时间(秒)")
    retry: int = Field(default=3, ge=0, le=10, description="重试次数")
    api_key: str = Field(default="", description="API认证token")
    api_path_prefix: str = Field(
        default="/portal/ai-gateway/devspace/rpc/v3/work-item",
        description="API路径前缀"
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
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="温度参数")
    max_tokens: int = Field(default=4096, ge=1, le=128000, description="最大token数")
    base_url: str = Field(default="", description="API基础URL(可选)")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = ["openai", "qwen", "wenxin", "zhipu", "custom"]
        if v not in allowed:
            raise ValueError(f"provider must be one of {allowed}")
        return v


class EmbeddingConfig(BaseModel):
    provider: str = Field(default="openai", description="Embedding服务提供商")
    model: str = Field(default="text-embedding-3-small", description="模型名称")
    api_key: str = Field(default="", description="API密钥")
    base_url: str = Field(default="", description="API基础URL(可选)")
    batch_size: int = Field(default=100, ge=1, le=512, description="批量嵌入时的最大文本条数")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = ["openai", "bge", "m3e", "codebert", "custom"]
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


class AppConfig(BaseModel):
    api: APIConfig = Field(default_factory=APIConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    clustering: ClusteringConfig = Field(default_factory=ClusteringConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    rules: RulesConfig = Field(default_factory=RulesConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
