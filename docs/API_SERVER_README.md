# REST API 服务器使用指南

## 概述

本文档描述了故障复盘分析工具的 REST API 服务器，它提供了通过 HTTP 接口进行故障分析、聚类查询和报告获取的能力。

## 快速开始

### 1. 安装依赖

确保已安装所需依赖：

```bash
pip install -e ".[dev]"
```

### 2. 配置环境变量

可以使用以下环境变量配置服务器：

```bash
# 服务器配置
API_HOST=0.0.0.0          # 监听地址
API_PORT=8000             # 监听端口

# 认证配置（可选）
API_VALID_TOKENS=token1,token2,token3  # 有效的 API Token 列表

# 速率限制配置
API_RATE_LIMIT=60          # 每分钟请求限制
```

### 3. 启动服务器

方式一：使用 Python 模块直接启动

```bash
python -m src.api.server
```

方式二：使用提供的脚本

```bash
python scripts/start_api_server.py
```

### 4. 访问 API 文档

服务器启动后，可以通过以下地址访问 API 文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## API 接口说明

### 健康检查

```http
GET /health
```

无需认证，检查服务状态。

**响应示例**:
```json
{
  "status": "healthy",
  "timestamp": "2026-03-31T01:00:00",
  "version": "0.1.0"
}
```

### 单个任务分析

```http
POST /analyze
Content-Type: application/json
X-API-Token: <your-token>

{
  "task_id": "11745664",
  "options": {
    "include_code": true,
    "include_analysis": true,
    "use_cache": true,
    "use_llm": false,
    "generate_labels": true,
    "analyze_root_cause": true,
    "check_rules": true,
    "generate_report": true
  }
}
```

### 批量分析

```http
POST /analyze/batch
Content-Type: application/json
X-API-Token: <your-token>

{
  "task_ids": ["11745664", "11748712", "11751534"],
  "options": {
    "use_cache": true,
    "use_llm": false
  }
}
```

### 获取聚类列表

```http
GET /clusters
X-API-Token: <your-token>
```

### 获取聚类详情

```http
GET /clusters/{cluster_id}
X-API-Token: <your-token>
```

### 获取报告

```http
GET /reports/{task_id}?format=html
X-API-Token: <your-token>
```

支持的格式: `html` (默认), `markdown`, `json`

## 认证说明

### Token 认证

API 支持通过 HTTP Header 或查询参数传递 Token：

**方式一: Header 传递**
```http
X-API-Token: your-secret-token
```

**方式二: 查询参数传递**
```http
GET /clusters?api_token=your-secret-token
```

### 开发模式

如果没有配置 `API_VALID_TOKENS` 环境变量，服务器将运行在开发模式下，允许所有请求（无需认证）。

## 速率限制

默认情况下，每个 Token（或 IP 地址）每分钟最多允许 60 个请求。超过限制将返回 `429 Too Many Requests` 状态码。

响应头中包含速率限制信息：
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 55
```

## 错误响应

所有错误响应遵循统一格式：

```json
{
  "error": "ErrorType",
  "message": "详细错误描述",
  "detail": {
    "additional": "信息"
  },
  "timestamp": "2026-03-31T01:00:00"
}
```

常见状态码：
- `400 Bad Request` - 请求参数错误
- `401 Unauthorized` - 缺少认证 Token
- `403 Forbidden` - 无效的 Token
- `404 Not Found` - 资源不存在
- `422 Unprocessable Entity` - 请求体验证失败
- `429 Too Many Requests` - 速率限制超限
- `500 Internal Server Error` - 服务器内部错误

## 使用示例

### 使用 Python requests 库

```python
import requests

BASE_URL = "http://localhost:8000"
API_TOKEN = "your-token"

# 设置公共 Headers
headers = {
    "X-API-Token": API_TOKEN,
    "Content-Type": "application/json"
}

# 1. 健康检查
response = requests.get(f"{BASE_URL}/health")
print("Health:", response.json())

# 2. 分析单个任务
analyze_payload = {
    "task_id": "11745664",
    "options": {
        "use_cache": True,
        "use_llm": False
    }
}
response = requests.post(
    f"{BASE_URL}/analyze",
    json=analyze_payload,
    headers=headers
)
print("Analysis result:", response.json())

# 3. 获取聚类列表
response = requests.get(f"{BASE_URL}/clusters", headers=headers)
print("Clusters:", response.json())

# 4. 获取报告
response = requests.get(
    f"{BASE_URL}/reports/11745664?format=html",
    headers=headers
)
with open("report.html", "w", encoding="utf-8") as f:
    f.write(response.json()["content"])
print("Report saved to report.html")
```

### 使用 cURL

```bash
# 健康检查
curl http://localhost:8000/health

# 分析任务
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Token: your-token" \
  -d '{"task_id": "11745664", "options": {"use_cache": true}}'

# 获取聚类列表
curl http://localhost:8000/clusters \
  -H "X-API-Token: your-token"

# 获取报告
curl "http://localhost:8000/reports/11745664?format=html" \
  -H "X-API-Token: your-token"
```

## 开发说明

### 运行测试

```bash
# 运行 API 相关测试
pytest tests/api/test_server.py tests/api/test_middleware.py -v

# 运行所有测试
pytest tests/ -v --cov=src
```

### 代码结构

```
src/api/
├── __init__.py              # 模块初始化
├── server.py                # FastAPI 服务器主文件
├── middleware.py            # 认证和速率限制中间件
├── server_models.py         # API 数据模型
├── dependencies.py          # 依赖注入
├── client.py                # API 客户端（原有）
├── models.py                # API 客户端模型（原有）
├── exceptions.py            # 异常定义（原有）
└── routes/
    ├── __init__.py
    ├── health.py            # 健康检查路由
    ├── analyze.py           # 分析路由
    ├── clusters.py          # 聚类路由
    └── reports.py           # 报告路由

tests/api/
├── test_server.py           # 服务器测试
└── test_middleware.py       # 中间件测试
```
