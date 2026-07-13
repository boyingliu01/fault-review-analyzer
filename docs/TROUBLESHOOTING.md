# 故障排查指南

本指南提供了故障复盘分析工具常见问题的排查方法和解决方案。

## 目录

- [安装问题](#安装问题)
- [配置问题](#配置问题)
- [API 调用问题](#api-调用问题)
- [LLM 服务问题](#llm-服务问题)
- [嵌入生成问题](#嵌入生成问题)
- [聚类分析问题](#聚类分析问题)
- [性能问题](#性能问题)
- [内存问题](#内存问题)
- [数据存储问题](#数据存储问题)
- [日志问题](#日志问题)
- [测试问题](#测试问题)
- [API 服务问题](#api-服务问题)
- [Docker 部署问题](#docker-部署问题)
- [Kubernetes 部署问题](#kubernetes-部署问题)
- [获取帮助](#获取帮助)

## 安装问题

### 问题：Python 版本不兼容

**症状**：安装依赖时出现 Python 版本不兼容的错误。

**原因**：使用的 Python 版本低于要求的版本。

**解决方案**：
```bash
# 检查 Python 版本
python --version

# 确保使用 Python 3.10 或更高版本
# 如果版本过低，升级 Python 或使用虚拟环境
python3.10 -m venv .venv
source .venv/bin/activate
```

### 问题：依赖安装失败

**症状**：`pip install` 命令失败。

**原因**：网络问题或依赖包冲突。

**解决方案**：
```bash
# 升级 pip
pip install --upgrade pip

# 尝试使用国内镜像源
pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple

# 如果遇到特定包的问题，尝试单独安装
pip install <package-name>

# 清理缓存后重试
pip cache purge
pip install -e ".[dev]"
```

### 问题：系统依赖缺失

**症状**：安装某些包时出现编译错误。

**原因**：缺少必要的系统依赖。

**解决方案**：

**对于 Ubuntu/Debian**：
```bash
sudo apt-get update
sudo apt-get install -y build-essential git libopenblas-dev liblapack-dev
```

**对于 macOS**：
```bash
xcode-select --install
brew install openblas lapack
```

**对于 Windows**：
- 安装 Visual C++ Build Tools
- 使用预编译的 wheel 包

## 配置问题

### 问题：环境变量未加载

**症状**：系统提示配置缺失，即使已经设置了 .env 文件。

**原因**：.env 文件未正确加载或格式错误。

**解决方案**：
```bash
# 检查 .env 文件是否存在
ls -la .env

# 检查 .env 文件格式
cat .env

# 确保 .env 文件格式正确，没有语法错误
# 例如：不要在值周围使用不必要的引号
```

**Python 代码中手动加载**：
```python
from dotenv import load_dotenv
import os

# 手动加载 .env 文件
load_dotenv()

# 验证变量是否加载
print(os.getenv("API_BASE_URL"))
```

### 问题：配置验证失败

**症状**：系统启动时提示配置验证失败。

**原因**：配置项缺失或格式错误。

**解决方案**：
```bash
# 查看 .env.example 文件了解必需的配置
cat .env.example

# 确保所有必需的配置项都已设置
# API_BASE_URL
# DEVCLOUD_TOKEN
# LLM_PROVIDER
# LLM_MODEL
# LLM_API_KEY
# EMBEDDING_PROVIDER
# EMBEDDING_MODEL
# EMBEDDING_API_KEY
```

## API 调用问题

### 问题：API 认证失败

**症状**：调用 API 时出现 401 Unauthorized 错误。

**原因**：DEVCLOUD_TOKEN 无效或过期。

**解决方案**：
```bash
# 检查 DEVCLOUD_TOKEN 配置
echo $DEVCLOUD_TOKEN

# 确保 Token 有效且未过期
# 如果 Token 过期，重新获取并更新 .env 文件
```

**验证 API 连接**：
```python
import httpx
from src.api.client import APIClient
from src.config.manager import ConfigManager

config = ConfigManager()

# 使用 httpx 直接测试 API
response = httpx.post(
    f"{config.api.base_url}/portal/ai-gateway/devspace/rpc/v3/work-item/11745664/detail",
    headers={"Authorization": f"Bearer {config.api.devcloud_token}"},
    json={}
)
print(response.status_code)
print(response.json())
```

### 问题：API 连接超时

**症状**：调用 API 时出现超时错误。

**原因**：网络问题或 API 服务响应慢。

**解决方案**：
```bash
# 检查网络连接
ping dev.iwhalecloud.com

# 检查 API 服务是否可用
# 使用浏览器或 curl 访问 API 文档
```

**增加超时时间**：
```python
# 在 .env 文件中增加 API_TIMEOUT
API_TIMEOUT=60
```

**使用重试机制**：
```python
# 在 .env 文件中增加 API_RETRY
API_RETRY=5
```

### 问题：API 接口 404

**症状**：调用 API 时出现 404 Not Found 错误。

**原因**：API 路径错误或接口不存在。

**解决方案**：
```bash
# 检查 API_BASE_URL 配置
echo $API_BASE_URL

# 检查 API 文档确认接口路径
# 查看 swagger.txt 文件
```

**检查 API 路径前缀**：
```python
from src.api.client import APIClient
from src.config.manager import ConfigManager

config = ConfigManager()

# 查看 API 路径配置
print(config.api)

# 尝试直接访问 API 文档
print(f"{config.api.base_url}/portal/ai-gateway/devspace/apidocs")
```

## LLM 服务问题

### 问题：LLM API 认证失败

**症状**：调用 LLM 服务时出现 401 Unauthorized 错误。

**原因**：LLM_API_KEY 无效或过期。

**解决方案**：
```bash
# 检查 LLM 配置
echo $LLM_PROVIDER
echo $LLM_API_KEY
echo $LLM_BASE_URL

# 确保 API Key 有效
# 如果 Key 过期，重新获取并更新 .env 文件
```

**验证 LLM 连接**：
```python
import httpx
from src.config.manager import ConfigManager

config = ConfigManager()

# 测试 LLM API 连接
headers = {"Authorization": f"Bearer {config.llm.api_key}"}
if config.llm.provider == "openai":
    url = f"{config.llm.base_url or 'https://api.openai.com/v1'}/models"
elif config.llm.provider == "qwen":
    url = f"{config.llm.base_url or 'https://dashscope.aliyuncs.com/api/v1'}/models"
elif config.llm.provider == "volcengine":
    url = f"{config.llm.base_url}/models"

response = httpx.get(url, headers=headers)
print(response.status_code)
print(response.json())
```

### 问题：LLM 服务超时

**症状**：调用 LLM 服务时出现超时错误。

**原因**：网络问题或 LLM 服务响应慢。

**解决方案**：
```bash
# 检查网络连接
# 尝试访问 LLM 服务的文档或状态页
```

**调整 LLM 参数**：
```bash
# 减少 LLM_MAX_TOKENS
LLM_MAX_TOKENS=1024

# 调整 LLM_TEMPERATURE
LLM_TEMPERATURE=0.5
```

### 问题：LLM 模型不存在

**症状**：调用 LLM 服务时提示模型不存在。

**原因**：LLM_MODEL 配置错误。

**解决方案**：
```bash
# 检查 LLM_MODEL 配置
echo $LLM_MODEL

# 查看 LLM 提供商的文档确认可用的模型
# OpenAI: gpt-4, gpt-3.5-turbo, etc.
# Qwen: qwen-turbo, qwen-plus, etc.
# Volcengine: doubao-seed-1-8-251228, etc.
```

## 嵌入生成问题

### 问题：嵌入生成失败

**症状**：生成嵌入时出现错误。

**原因**：嵌入服务配置错误或服务不可用。

**解决方案**：
```bash
# 检查嵌入配置
echo $EMBEDDING_PROVIDER
echo $EMBEDDING_MODEL
echo $EMBEDDING_API_KEY
echo $EMBEDDING_BASE_URL

# 确保嵌入服务配置正确
```

**验证嵌入服务连接**：
```python
import httpx
from src.config.manager import ConfigManager

config = ConfigManager()

# 测试嵌入 API 连接
headers = {"Authorization": f"Bearer {config.embedding.api_key}"}
if config.embedding.provider == "openai":
    url = f"{config.embedding.base_url or 'https://api.openai.com/v1'}/models"
elif config.embedding.provider == "qwen":
    url = f"{config.embedding.base_url or 'https://dashscope.aliyuncs.com/api/v1'}/models"
elif config.embedding.provider == "volcengine":
    url = f"{config.embedding.base_url}/models"

response = httpx.get(url, headers=headers)
print(response.status_code)
```

### 问题：嵌入生成速度慢

**症状**：生成嵌入需要很长时间。

**原因**：批处理大小不合适或网络问题。

**解决方案**：
```bash
# 调整嵌入批处理大小
EMBEDDING_BATCH_SIZE=20

# 使用本地嵌入模型
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

## 聚类分析问题

### 问题：聚类结果为空

**症状**：聚类分析没有生成任何聚类。

**原因**：最小聚类大小设置过大或数据不足。

**解决方案**：
```bash
# 调整最小聚类大小
CLUSTERING_MIN_CLUSTER_SIZE=3

# 调整最小样本数
CLUSTERING_MIN_SAMPLES=2

# 确保有足够的数据进行聚类
# 建议至少有 10 个以上的任务
```

### 问题：聚类效果不好

**症状**：聚类结果不符合预期，任务分配不准确。

**原因**：嵌入质量不好或聚类算法参数不合适。

**解决方案**：
```bash
# 尝试不同的嵌入模型
EMBEDDING_MODEL=all-MiniLM-L6-v2
# 或
EMBEDDING_MODEL=text-embedding-3-large

# 调整聚类参数
CLUSTERING_METRIC=cosine  # 或 euclidean
CLUSTERING_MIN_CLUSTER_SIZE=5
CLUSTERING_MIN_SAMPLES=3

# 尝试不同的聚类算法
# （如果支持）
CLUSTERING_ALGORITHM=kmeans
```

## 性能问题

### 问题：分析速度慢

**症状**：分析任务需要很长时间。

**原因**：数据量大或处理逻辑复杂。

**解决方案**：
```bash
# 启用缓存
CACHE_ENABLED=true
CACHE_TTL=86400

# 禁用不必要的功能
# 例如：不使用 LLM 进行分析
# 或在命令行中指定
fault-analyzer analyze --task-id 12345 --no-llm
```

**代码优化**：
```python
# 使用异步处理
# 使用批处理
# 使用并行计算
```

### 问题：启动速度慢

**症状**：系统启动需要很长时间。

**原因**：模型加载或初始化慢。

**解决方案**：
```bash
# 使用本地模型缓存
# 预加载模型
```

**使用轻量级模型**：
```bash
# 使用轻量级的嵌入模型
EMBEDDING_MODEL=all-MiniLM-L6-v2

# 使用轻量级的 LLM 模型
LLM_MODEL=gpt-3.5-turbo
```

## 内存问题

### 问题：内存不足

**症状**：系统出现 OutOfMemoryError 或被系统杀死。

**原因**：数据量大或内存使用不当。

**解决方案**：
```bash
# 减少批处理大小
EMBEDDING_BATCH_SIZE=10

# 使用流式处理
# 避免一次性加载所有数据
```

**增加系统内存**：
```bash
# 如果在 Docker 中运行
docker run -m 4g ...

# 如果在 Kubernetes 中运行
# 调整 Pod 的内存限制
```

**使用内存优化**：
```python
# 及时释放不再使用的对象
# 使用生成器而不是列表
# 使用更高效的数据结构
```

## 数据存储问题

### 问题：ChromaDB 无法启动

**症状**：ChromaDB 初始化失败。

**原因**：数据目录不存在或权限问题。

**解决方案**：
```bash
# 确保数据目录存在
mkdir -p data/chroma

# 检查目录权限
ls -la data/chroma

# 确保有读写权限
chmod 755 data/chroma
```

### 问题：SQLite 数据库错误

**症状**：SQLite 数据库操作失败。

**原因**：数据库文件损坏或权限问题。

**解决方案**：
```bash
# 备份数据库文件
cp data/cache.db data/cache.db.backup

# 尝试修复数据库
sqlite3 data/cache.db .recover > data/cache.db.fixed
mv data/cache.db.fixed data/cache.db

# 如果无法修复，删除损坏的数据库
rm data/cache.db
# 系统会自动创建新的数据库
```

### 问题：文件系统权限错误

**症状**：无法写入输出文件或日志文件。

**原因**：目录权限不正确。

**解决方案**：
```bash
# 确保输出目录存在
mkdir -p output
mkdir -p logs

# 检查目录权限
ls -la output
ls -la logs

# 修改目录权限
chmod 755 output
chmod 755 logs

# 如果需要，修改所有者
chown -R user:user output
chown -R user:user logs
```

## 日志问题

### 问题：日志文件未生成

**症状**：logs 目录中没有日志文件。

**原因**：日志配置不正确。

**解决方案**：
```bash
# 检查日志配置
echo $LOG_LEVEL
echo $LOG_FILE

# 确保日志目录存在
mkdir -p logs

# 检查目录权限
ls -la logs
```

### 问题：日志级别不生效

**症状**：日志输出不符合设置的 LOG_LEVEL。

**原因**：日志配置加载顺序问题。

**解决方案**：
```python
# 在代码中手动设置日志级别
from loguru import logger
import sys

logger.remove()
logger.add(sys.stderr, level="DEBUG")
logger.add("logs/app.log", level="DEBUG")
```

## 测试问题

### 问题：测试失败

**症状**：运行 pytest 时测试失败。

**原因**：配置问题或依赖缺失。

**解决方案**：
```bash
# 确保测试环境配置正确
cp .env.example .env.test
# 编辑 .env.test 文件

# 运行特定测试文件
pytest tests/test_clustering.py -v

# 运行特定测试
pytest tests/test_clustering.py::test_cluster_analysis -v

# 查看详细的测试输出
pytest tests/ -v --tb=long
```

### 问题：测试覆盖率低

**症状**：测试覆盖率未达到要求的 79.9%。

**原因**：缺少测试或测试未覆盖某些代码路径。

**解决方案**：
```bash
# 查看覆盖率报告
pytest tests/ -v --cov=src --cov-report=html
# 打开 htmlcov/index.html 查看详细报告

# 为未覆盖的代码添加测试
```

## API 服务问题

### 问题：API 服务无法启动

**症状**：启动 API 服务时失败。

**原因**：端口被占用或配置错误。

**解决方案**：
```bash
# 检查端口是否被占用
lsof -i :8000  # Linux/macOS
# 或
netstat -ano | findstr :8000  # Windows

# 使用不同的端口
API_PORT=8001

# 检查配置是否正确
echo $API_HOST
echo $API_PORT
echo $API_VALID_TOKENS
```

### 问题：API 服务响应 500 错误

**症状**：访问 API 接口时出现 500 Internal Server Error。

**原因**：服务内部错误。

**解决方案**：
```bash
# 查看服务日志
docker logs fault-review-analyzer  # 如果在 Docker 中运行
# 或
journalctl -u fault-review -f  # 如果使用 systemd

# 启用调试日志
LOG_LEVEL=DEBUG
```

### 问题：API 服务速率限制

**症状**：访问 API 接口时出现 429 Too Many Requests 错误。

**原因**：请求频率超过限制。

**解决方案**：
```bash
# 增加速率限制
API_RATE_LIMIT=120

# 或在客户端实现请求重试和退避机制
```

## Docker 部署问题

### 问题：Docker 镜像构建失败

**症状**：构建 Docker 镜像时失败。

**原因**：Dockerfile 错误或依赖问题。

**解决方案**：
```bash
# 查看构建日志
docker build -t fault-review-analyzer:latest . --no-cache

# 确保 Dockerfile 正确
# 检查基础镜像是否可用
# 检查依赖安装是否正确
```

### 问题：Docker 容器无法启动

**症状**：Docker 容器启动后立即退出。

**原因**：配置错误或依赖缺失。

**解决方案**：
```bash
# 查看容器日志
docker logs fault-review-analyzer

# 检查环境变量配置
docker inspect fault-review-analyzer

# 以交互模式运行容器进行调试
docker run -it --rm fault-review-analyzer:latest bash
```

### 问题：Docker 容器网络问题

**症状**：Docker 容器无法访问外部网络。

**原因**：Docker 网络配置错误。

**解决方案**：
```bash
# 检查 Docker 网络
docker network ls

# 使用 host 网络模式
docker run --network=host ...

# 或配置正确的端口映射
docker run -p 8000:8000 ...
```

## Kubernetes 部署问题

### 问题：Pod 无法启动

**症状**：Pod 一直处于 Pending 或 CrashLoopBackOff 状态。

**原因**：配置错误或资源不足。

**解决方案**：
```bash
# 查看 Pod 状态
kubectl get pods -n fault-review

# 查看 Pod 描述
kubectl describe pod <pod-name> -n fault-review

# 查看 Pod 日志
kubectl logs <pod-name> -n fault-review
```

### 问题：服务无法访问

**症状**：无法访问 Kubernetes 服务。

**原因**：Service 或 Ingress 配置错误。

**解决方案**：
```bash
# 查看 Service 状态
kubectl get svc -n fault-review

# 查看 Ingress 状态
kubectl get ingress -n fault-review

# 查看端点
kubectl get endpoints -n fault-review

# 检查网络策略
kubectl get networkpolicy -n fault-review
```

### 问题：PersistentVolumeClaim 无法绑定

**症状**：PVC 一直处于 Pending 状态。

**原因**：存储配置错误。

**解决方案**：
```bash
# 查看 PVC 状态
kubectl get pvc -n fault-review

# 查看 PV 状态
kubectl get pv

# 检查 StorageClass
kubectl get storageclass
```

## 获取帮助

如果以上解决方案无法解决你的问题，请尝试以下方式获取帮助：

1. **查看项目文档**：查看 docs 目录下的其他文档
2. **搜索 Issues**：在 GitHub 上搜索类似的 Issue
3. **提交 Issue**：在 GitHub 上提交新的 Issue，包含：
   - 问题的详细描述
   - 复现步骤
   - 错误日志
   - 系统环境信息（操作系统、Python 版本、依赖版本等）
   - 截图（如果有帮助）

---

**最后更新**: 2026-03-31
