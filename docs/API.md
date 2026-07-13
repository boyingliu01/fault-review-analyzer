# API 文档

## 概述

故障复盘分析工具提供了完整的 RESTful API 接口，允许用户通过 HTTP 请求与系统交互。API 支持任务分析、聚类查询、报告生成等功能，并提供了健康检查和状态监控接口。

## 基础信息

- **基础 URL**: `http://localhost:8000`（本地开发环境）
- **API 版本**: 0.1.0
- **认证方式**: API Token 认证
- **内容类型**: `application/json`

## 认证

### Token 认证

API 支持通过 HTTP Header 或查询参数传递 Token 进行认证。

#### 方式一：Header 传递
```http
X-API-Token: <your-token>
```

#### 方式二：查询参数传递
```http
GET /clusters?api_token=<your-token>
```

#### 开发模式

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

## API 接口

### 1. 健康检查

**接口名称**: 健康检查
**HTTP 方法**: GET
**接口路径**: `/health`
**认证**: 否
**标签**: Health

检查 API 服务器的健康状态。

**请求示例**:
```http
GET /health HTTP/1.1
Host: localhost:8000
Content-Type: application/json
```

**响应示例**:
```json
{
  "status": "healthy",
  "timestamp": "2026-03-31T01:00:00",
  "version": "0.1.0"
}
```

### 2. 单个任务分析

**接口名称**: 单个任务分析
**HTTP 方法**: POST
**接口路径**: `/analyze`
**认证**: 是
**标签**: Analysis

分析指定任务的故障信息，包括代码变更、根因分析等。

**请求示例**:
```http
POST /analyze HTTP/1.1
Host: localhost:8000
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

**请求参数**:
- `task_id`: 任务编号（必填）
- `options`: 分析选项（可选）
  - `include_code`: 是否包含代码变更分析（默认：true）
  - `include_analysis`: 是否包含故障分析（默认：true）
  - `use_cache`: 是否使用缓存数据（默认：true）
  - `use_llm`: 是否使用 LLM 进行分析（默认：false）
  - `generate_labels`: 是否生成标签（默认：true）
  - `analyze_root_cause`: 是否进行根因分析（默认：true）
  - `check_rules`: 是否检查规范冲突（默认：true）
  - `generate_report`: 是否生成报告（默认：true）

**响应示例**:
```json
{
  "task_id": "11745664",
  "status": "completed",
  "result": {
    "title": "任务标题",
    "description": "任务描述",
    "analysis": "分析结果",
    "root_causes": [...],
    "labels": [...],
    "violations": [...]
  },
  "timestamp": "2026-03-31T01:00:00"
}
```

### 3. 批量分析

**接口名称**: 批量分析
**HTTP 方法**: POST
**接口路径**: `/analyze/batch`
**认证**: 是
**标签**: Analysis

批量分析多个任务的故障信息。

**请求示例**:
```http
POST /analyze/batch HTTP/1.1
Host: localhost:8000
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

**请求参数**:
- `task_ids`: 任务编号列表（必填）
- `options`: 分析选项（可选）
  - `use_cache`: 是否使用缓存数据（默认：true）
  - `use_llm`: 是否使用 LLM 进行分析（默认：false）

**响应示例**:
```json
{
  "status": "completed",
  "results": [
    {
      "task_id": "11745664",
      "status": "success",
      "result": {...}
    },
    {
      "task_id": "11748712",
      "status": "failed",
      "error": "错误信息"
    }
  ],
  "timestamp": "2026-03-31T01:00:00"
}
```

### 4. 获取聚类列表

**接口名称**: 获取聚类列表
**HTTP 方法**: GET
**接口路径**: `/clusters`
**认证**: 是
**标签**: Clusters

获取所有故障聚类信息。

**请求示例**:
```http
GET /clusters HTTP/1.1
Host: localhost:8000
X-API-Token: <your-token>
```

**响应示例**:
```json
{
  "clusters": [
    {
      "cluster_id": 0,
      "label": "数据库连接问题",
      "size": 5,
      "samples": ["11745664", "11748712"]
    },
    {
      "cluster_id": 1,
      "label": "代码质量问题",
      "size": 3,
      "samples": ["11751534"]
    }
  ],
  "total_clusters": 2,
  "total_tasks": 8,
  "timestamp": "2026-03-31T01:00:00"
}
```

### 5. 获取聚类详情

**接口名称**: 获取聚类详情
**HTTP 方法**: GET
**接口路径**: `/clusters/{cluster_id}`
**认证**: 是
**标签**: Clusters

获取指定聚类的详细信息，包括该聚类下的所有任务。

**请求示例**:
```http
GET /clusters/0 HTTP/1.1
Host: localhost:8000
X-API-Token: <your-token>
```

**路径参数**:
- `cluster_id`: 聚类编号（必填）

**响应示例**:
```json
{
  "cluster_id": 0,
  "label": "数据库连接问题",
  "size": 5,
  "tasks": [
    {
      "task_id": "11745664",
      "title": "任务标题",
      "description": "任务描述"
    },
    {
      "task_id": "11748712",
      "title": "任务标题",
      "description": "任务描述"
    }
  ],
  "similarity_score": 0.85,
  "timestamp": "2026-03-31T01:00:00"
}
```

### 6. 获取报告

**接口名称**: 获取报告
**HTTP 方法**: GET
**接口路径**: `/reports/{task_id}`
**认证**: 是
**标签**: Reports

获取指定任务的分析报告，支持多种格式。

**请求示例**:
```http
GET /reports/11745664?format=html HTTP/1.1
Host: localhost:8000
X-API-Token: <your-token>
```

**路径参数**:
- `task_id`: 任务编号（必填）

**查询参数**:
- `format`: 报告格式（可选，默认：html）
  - `html`: HTML 格式
  - `markdown`: Markdown 格式
  - `json`: JSON 格式

**响应示例**:
```json
{
  "task_id": "11745664",
  "format": "html",
  "content": "<html>报告内容...</html>",
  "timestamp": "2026-03-31T01:00:00"
}
```

### 7. 反馈管理

**接口名称**: 提交反馈
**HTTP 方法**: POST
**接口路径**: `/feedback`
**认证**: 是
**标签**: Feedback

提交对分析结果的反馈。

**请求示例**:
```http
POST /feedback HTTP/1.1
Host: localhost:8000
Content-Type: application/json
X-API-Token: <your-token>

{
  "task_id": "11745664",
  "feedback_type": "label",
  "content": "标签不准确，应该是数据库连接问题",
  "metadata": {
    "current_label": "代码质量问题",
    "suggested_label": "数据库连接问题"
  }
}
```

**请求参数**:
- `task_id`: 任务编号（必填）
- `feedback_type`: 反馈类型（必填）
  - `label`: 标签反馈
  - `root_cause`: 根因分析反馈
  - `violation`: 规范冲突反馈
  - `general`: 一般反馈
- `content`: 反馈内容（必填）
- `metadata`: 反馈元数据（可选）

**响应示例**:
```json
{
  "feedback_id": "fb-12345",
  "task_id": "11745664",
  "status": "received",
  "timestamp": "2026-03-31T01:00:00"
}
```

## 错误码

| 状态码 | 错误类型 | 描述 |
|-------|---------|------|
| 400 | BadRequest | 请求参数错误 |
| 401 | Unauthorized | 缺少认证 Token |
| 403 | Forbidden | 无效的 Token |
| 404 | NotFound | 资源不存在 |
| 422 | UnprocessableEntity | 请求体验证失败 |
| 429 | TooManyRequests | 速率限制超限 |
| 500 | InternalServerError | 服务器内部错误 |

## 使用示例

### Python requests 库

```python
import requests

BASE_URL = "http://localhost:8000"
API_TOKEN = "your-token"

headers = {
    "X-API-Token": API_TOKEN,
    "Content-Type": "application/json"
}

# 健康检查
response = requests.get(f"{BASE_URL}/health")
print("Health:", response.json())

# 分析单个任务
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

# 获取聚类列表
response = requests.get(f"{BASE_URL}/clusters", headers=headers)
print("Clusters:", response.json())

# 获取报告
response = requests.get(
    f"{BASE_URL}/reports/11745664?format=html",
    headers=headers
)
with open("report.html", "w", encoding="utf-8") as f:
    f.write(response.json()["content"])
print("Report saved to report.html")
```

### cURL

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

## 部署和配置

### 环境变量

| 变量名 | 描述 | 默认值 |
|-------|------|-------|
| API_HOST | 服务器监听地址 | 0.0.0.0 |
| API_PORT | 服务器监听端口 | 8000 |
| API_VALID_TOKENS | 有效的 API Token 列表（逗号分隔） | 无 |
| API_RATE_LIMIT | 每分钟请求限制 | 60 |

### 启动命令

```bash
# 使用 Python 模块直接启动
python -m src.api.server

# 或使用脚本
python scripts/start_api_server.py
```

## 开发和测试

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
    ├── reports.py           # 报告路由
    └── feedback.py          # 反馈路由

tests/api/
├── test_server.py           # 服务器测试
└── test_middleware.py       # 中间件测试
```
