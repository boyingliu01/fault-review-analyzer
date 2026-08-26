# 部署指南

本指南介绍如何部署故障复盘分析工具到不同的环境中。

## 目录

- [部署方式](#部署方式)
- [环境要求](#环境要求)
- [配置说明](#配置说明)
- [本地部署](#本地部署)
- [Docker 部署](#docker-部署)
- [Kubernetes 部署](#kubernetes-部署)
- [API 服务部署](#api-服务部署)
- [数据备份与恢复](#数据备份与恢复)
- [监控与日志](#监控与日志)
- [常见问题](#常见问题)

## 部署方式

故障复盘分析工具支持多种部署方式：

1. **本地部署**: 适合开发和测试环境
2. **Docker 部署**: 适合容器化部署
3. **Kubernetes 部署**: 适合生产环境和高可用场景
4. **API 服务部署**: 适合作为独立服务提供 API

## 环境要求

### 系统要求

- **操作系统**: Linux、macOS 或 Windows
- **Python 版本**: 3.10 或更高
- **内存**: 至少 4GB（推荐 8GB 或更多）
- **磁盘空间**: 至少 10GB 可用空间

### 依赖软件

- **Git**: 用于代码版本管理
- **Docker**: 用于容器化部署（可选）
- **Kubernetes**: 用于 Kubernetes 部署（可选）
- **Nginx**: 用于反向代理（可选）

## 配置说明

### 环境变量

故障复盘分析工具使用环境变量进行配置。可以通过 `.env` 文件或直接设置环境变量来配置。

#### API 配置

| 变量名 | 描述 | 默认值 | 必填 |
|-------|------|-------|------|
| `API_BASE_URL` | 研发管理系统 API 地址 | - | 是 |
| `DEVCLOUD_TOKEN` | 研发云访问令牌 | - | 是 |
| `API_TIMEOUT` | API 请求超时时间（秒） | 30 | 否 |
| `API_RETRY` | API 请求重试次数 | 3 | 否 |

#### LLM 配置

| 变量名 | 描述 | 默认值 | 必填 |
|-------|------|-------|------|
| `LLM_PROVIDER` | LLM 服务提供商 | openai | 是 |
| `LLM_MODEL` | LLM 模型名称 | gpt-4 | 是 |
| `LLM_API_KEY` | LLM API 密钥 | - | 是 |
| `LLM_TEMPERATURE` | LLM 温度参数 | 0.7 | 否 |
| `LLM_MAX_TOKENS` | LLM 最大生成 Token 数 | 4096 | 否 |
| `LLM_BASE_URL` | LLM 基础 URL | - | 否 |

#### Embedding 配置

| 变量名 | 描述 | 默认值 | 必填 |
|-------|------|-------|------|
| `EMBEDDING_PROVIDER` | Embedding 服务提供商 | openai | 是 |
| `EMBEDDING_MODEL` | Embedding 模型名称 | text-embedding-3-small | 是 |
| `EMBEDDING_API_KEY` | Embedding API 密钥 | - | 是 |
| `EMBEDDING_BASE_URL` | Embedding 基础 URL | - | 否 |
| `EMBEDDING_BATCH_SIZE` | Embedding 批量大小 | 100 | 否 |

#### 聚类配置

| 变量名 | 描述 | 默认值 | 必填 |
|-------|------|-------|------|
| `CLUSTERING_ALGORITHM` | 聚类算法 | hdbscan | 否 |
| `CLUSTERING_MIN_CLUSTER_SIZE` | 最小聚类大小 | 5 | 否 |
| `CLUSTERING_MIN_SAMPLES` | 最小样本数 | 3 | 否 |
| `CLUSTERING_METRIC` | 距离度量 | cosine | 否 |

#### 缓存配置

| 变量名 | 描述 | 默认值 | 必填 |
|-------|------|-------|------|
| `CACHE_ENABLED` | 是否启用缓存 | true | 否 |
| `CACHE_TTL` | 缓存 TTL（秒） | 86400 | 否 |
| `CACHE_STORAGE` | 缓存存储方式 | sqlite | 否 |

#### 规范配置

| 变量名 | 描述 | 默认值 | 必填 |
|-------|------|-------|------|
| `RULES_BUILTIN_ENABLED` | 是否启用内置规范 | true | 否 |
| `RULES_CUSTOM_PATH` | 自定义规范路径 | ./data/rules/custom/ | 否 |

#### 输出配置

| 变量名 | 描述 | 默认值 | 必填 |
|-------|------|-------|------|
| `OUTPUT_FORMAT` | 输出格式 | markdown | 否 |
| `OUTPUT_DIRECTORY` | 输出目录 | ./output/ | 否 |

#### 日志配置

| 变量名 | 描述 | 默认值 | 必填 |
|-------|------|-------|------|
| `LOG_LEVEL` | 日志级别 | INFO | 否 |
| `LOG_FILE` | 日志文件路径 | ./logs/app.log | 否 |

#### API 服务配置

| 变量名 | 描述 | 默认值 | 必填 |
|-------|------|-------|------|
| `API_HOST` | API 服务监听地址 | 0.0.0.0 | 否 |
| `API_PORT` | API 服务监听端口 | 8000 | 否 |
| `API_VALID_TOKENS` | 有效的 API Token 列表，受保护路由通过 `X-API-Token` 请求头认证 | - | 否 |
| `API_ALLOW_UNAUTHENTICATED` | 是否允许免认证访问，仅用于本地开发 | false | 否 |
| `API_RATE_LIMIT` | 每分钟请求限制 | 60 | 否 |
| `API_CORS_ORIGINS` | 允许跨域访问的来源列表，逗号分隔 | - | 否 |
| `API_CORS_METHODS` | 允许跨域访问的 HTTP 方法列表，逗号分隔 | GET, POST, OPTIONS | 否 |
| `API_CORS_HEADERS` | 允许跨域访问的请求头列表，逗号分隔 | Content-Type, X-API-Token | 否 |
| `API_DOCS_ENABLED` | 启用 /docs /redoc 文档端点 | false | 否 |
| `API_ACCESS_LOG` | 启用 Uvicorn access_log | false | 否 |

### 配置文件

除了环境变量外，还可以使用 YAML 配置文件进行配置。配置文件路径为 `config/config.yaml`。

## 本地部署

### 步骤 1: 克隆仓库

```bash
git clone https://github.com/your-org/fault-review-analyzer.git
cd fault-review-analyzer
```

### 步骤 2: 创建虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows
```

### 步骤 3: 安装依赖

```bash
pip install -e ".[dev]"
```

### 步骤 4: 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入必要的配置
```

### 步骤 5: 创建必要的目录

```bash
mkdir -p data/cache
mkdir -p data/rules/custom
mkdir -p data/standards
mkdir -p output
mkdir -p logs
```

### 步骤 6: 运行测试

```bash
pytest tests/ -v --cov=src
```

### 步骤 7: 使用 CLI

```bash
# 查看帮助
fault-analyzer --help

# 获取任务数据
fault-analyzer fetch --task-id 12345

# 分析任务
fault-analyzer analyze --task-id 12345

# 生成报告
fault-analyzer report --task-id 12345 --output ./output
```

### 步骤 8: 启动 API 服务（可选）

```bash
python -m src.api.server
# 或
fault-analyzer-api
```

## Docker 部署

### 步骤 1: 准备 Dockerfile

在项目根目录创建 `Dockerfile`：

```dockerfile
# 使用官方 Python 镜像作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY . .

# 安装 Python 依赖
RUN pip install --no-cache-dir -e ".[dev]"

# 创建必要的目录
RUN mkdir -p data/cache \
    data/rules/custom \
    data/standards \
    output \
    logs

# 暴露端口
EXPOSE 8000

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 启动命令
CMD ["python", "-m", "src.api.server"]
```

### 步骤 2: 构建 Docker 镜像

```bash
docker build -t fault-review-analyzer:latest .
```

### 步骤 3: 创建 docker-compose.yml（可选）

在项目根目录创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  fault-review-analyzer:
    image: fault-review-analyzer:latest
    container_name: fault-review-analyzer
    ports:
      - "8000:8000"
    environment:
      - API_BASE_URL=https://dev.iwhalecloud.com
      - DEVCLOUD_TOKEN=${DEVCLOUD_TOKEN}
      - LLM_PROVIDER=${LLM_PROVIDER}
      - LLM_MODEL=${LLM_MODEL}
      - LLM_API_KEY=${LLM_API_KEY}
      - EMBEDDING_PROVIDER=${EMBEDDING_PROVIDER}
      - EMBEDDING_MODEL=${EMBEDDING_MODEL}
      - EMBEDDING_API_KEY=${EMBEDDING_API_KEY}
      - API_VALID_TOKENS=${API_VALID_TOKENS}
      - API_ALLOW_UNAUTHENTICATED=false
      - API_DOCS_ENABLED=false
      - API_CORS_ORIGINS=${API_CORS_ORIGINS}
      - API_RATE_LIMIT=60
    volumes:
      - ./data:/app/data
      - ./output:/app/output
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### 步骤 4: 运行 Docker 容器

```bash
# 使用 Docker 直接运行
docker run -d \
  --name fault-review-analyzer \
  -p 8000:8000 \
  -e API_BASE_URL=https://dev.iwhalecloud.com \
  -e DEVCLOUD_TOKEN=<your-devcloud-token> \
  -e LLM_PROVIDER=openai \
  -e LLM_MODEL=gpt-4 \
  -e LLM_API_KEY=<your-llm-api-key> \
  -e EMBEDDING_PROVIDER=openai \
  -e EMBEDDING_MODEL=text-embedding-3-small \
  -e EMBEDDING_API_KEY=<your-embedding-api-key> \
  -e API_VALID_TOKENS=<token-a>,<token-b> \
  -e API_CORS_ORIGINS=https://app.example.com \
  -e API_DOCS_ENABLED=false \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/logs:/app/logs \
  fault-review-analyzer:latest

# 或使用 Docker Compose
docker-compose up -d
```

### 步骤 5: 验证部署

```bash
# 检查容器状态
docker ps

# 查看日志
docker logs fault-review-analyzer

# 测试 API
curl http://localhost:8000/health
```

## Kubernetes 部署

### 步骤 1: 准备 Kubernetes 配置文件

创建 `k8s/namespace.yaml`：

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: fault-review
```

创建 `k8s/configmap.yaml`：

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fault-review-config
  namespace: fault-review
data:
  API_BASE_URL: "https://dev.iwhalecloud.com"
  LLM_PROVIDER: "openai"
  LLM_MODEL: "gpt-4"
  EMBEDDING_PROVIDER: "openai"
  EMBEDDING_MODEL: "text-embedding-3-small"
  LOG_LEVEL: "INFO"
  API_DOCS_ENABLED: "false"
  API_ALLOW_UNAUTHENTICATED: "false"
  API_CORS_ORIGINS: "https://app.example.com"
  API_RATE_LIMIT: "60"
```

创建 `k8s/secret.yaml`：

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: fault-review-secret
  namespace: fault-review
type: Opaque
stringData:
  DEVCLOUD_TOKEN: "<your-devcloud-token>"
  LLM_API_KEY: "<your-llm-api-key>"
  EMBEDDING_API_KEY: "<your-embedding-api-key>"
  API_VALID_TOKENS: "<token-a>,<token-b>"
```

创建 `k8s/deployment.yaml`：

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fault-review-analyzer
  namespace: fault-review
  labels:
    app: fault-review-analyzer
spec:
  replicas: 3
  selector:
    matchLabels:
      app: fault-review-analyzer
  template:
    metadata:
      labels:
        app: fault-review-analyzer
    spec:
      containers:
      - name: fault-review-analyzer
        image: fault-review-analyzer:latest
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: API_BASE_URL
          valueFrom:
            configMapKeyRef:
              name: fault-review-config
              key: API_BASE_URL
        - name: DEVCLOUD_TOKEN
          valueFrom:
            secretKeyRef:
              name: fault-review-secret
              key: DEVCLOUD_TOKEN
        - name: LLM_PROVIDER
          valueFrom:
            configMapKeyRef:
              name: fault-review-config
              key: LLM_PROVIDER
        - name: LLM_MODEL
          valueFrom:
            configMapKeyRef:
              name: fault-review-config
              key: LLM_MODEL
        - name: LLM_API_KEY
          valueFrom:
            secretKeyRef:
              name: fault-review-secret
              key: LLM_API_KEY
        - name: EMBEDDING_PROVIDER
          valueFrom:
            configMapKeyRef:
              name: fault-review-config
              key: EMBEDDING_PROVIDER
        - name: EMBEDDING_MODEL
          valueFrom:
            configMapKeyRef:
              name: fault-review-config
              key: EMBEDDING_MODEL
        - name: EMBEDDING_API_KEY
          valueFrom:
            secretKeyRef:
              name: fault-review-secret
              key: EMBEDDING_API_KEY
        - name: API_VALID_TOKENS
          valueFrom:
            secretKeyRef:
              name: fault-review-secret
              key: API_VALID_TOKENS
        - name: API_DOCS_ENABLED
          valueFrom:
            configMapKeyRef:
              name: fault-review-config
              key: API_DOCS_ENABLED
        - name: API_ALLOW_UNAUTHENTICATED
          valueFrom:
            configMapKeyRef:
              name: fault-review-config
              key: API_ALLOW_UNAUTHENTICATED
        - name: API_CORS_ORIGINS
          valueFrom:
            configMapKeyRef:
              name: fault-review-config
              key: API_CORS_ORIGINS
        - name: API_RATE_LIMIT
          valueFrom:
            configMapKeyRef:
              name: fault-review-config
              key: API_RATE_LIMIT
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
        volumeMounts:
        - name: data
          mountPath: /app/data
        - name: output
          mountPath: /app/output
        - name: logs
          mountPath: /app/logs
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: fault-review-data
      - name: output
        persistentVolumeClaim:
          claimName: fault-review-output
      - name: logs
        persistentVolumeClaim:
          claimName: fault-review-logs
```

创建 `k8s/service.yaml`：

```yaml
apiVersion: v1
kind: Service
metadata:
  name: fault-review-service
  namespace: fault-review
spec:
  selector:
    app: fault-review-analyzer
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
    name: http
  type: ClusterIP
```

创建 `k8s/ingress.yaml`：

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: fault-review-ingress
  namespace: fault-review
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  tls:
  - hosts:
    - fault-review.example.com
    secretName: fault-review-tls
  rules:
  - host: fault-review.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: fault-review-service
            port:
              number: 80
```

创建 `k8s/pvc.yaml`：

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: fault-review-data
  namespace: fault-review
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: fault-review-output
  namespace: fault-review
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: fault-review-logs
  namespace: fault-review
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
```

创建 `k8s/hpa.yaml`：

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fault-review-hpa
  namespace: fault-review
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fault-review-analyzer
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### 步骤 2: 部署到 Kubernetes

```bash
# 创建命名空间
kubectl apply -f k8s/namespace.yaml

# 创建配置和密钥
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml

# 创建 PVC
kubectl apply -f k8s/pvc.yaml

# 部署应用
kubectl apply -f k8s/deployment.yaml

# 创建服务
kubectl apply -f k8s/service.yaml

# 创建 Ingress（可选）
kubectl apply -f k8s/ingress.yaml

# 创建 HPA（可选）
kubectl apply -f k8s/hpa.yaml
```

### 步骤 3: 验证部署

```bash
# 查看 Pod 状态
kubectl get pods -n fault-review

# 查看服务状态
kubectl get svc -n fault-review

# 查看部署状态
kubectl get deployment -n fault-review

# 查看日志
kubectl logs -f deployment/fault-review-analyzer -n fault-review

# 测试服务
kubectl port-forward svc/fault-review-service 8080:80 -n fault-review
curl http://localhost:8080/health
```

## API 服务部署

### 使用 Gunicorn 部署

对于生产环境，建议使用 Gunicorn 部署 API 服务。

```bash
# 安装 Gunicorn
pip install gunicorn

# 启动服务
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 src.api.server:app
```

### 使用 Nginx 作为反向代理

创建 Nginx 配置文件 `/etc/nginx/sites-available/fault-review`：

```nginx
server {
    listen 80;
    server_name fault-review.example.com;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持（如果需要）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # 静态文件（如果有）
    location /static/ {
        alias /path/to/static/files/;
        expires 30d;
    }
}
```

启用配置：

```bash
# 创建符号链接
sudo ln -s /etc/nginx/sites-available/fault-review /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx
```

### 使用 systemd 管理服务

创建 systemd 服务文件 `/etc/systemd/system/fault-review.service`：

```ini
[Unit]
Description=Fault Review Analyzer API Service
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/path/to/fault-review-analyzer
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000 src.api.server:app
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
# 重新加载 systemd 配置
sudo systemctl daemon-reload

# 启用服务
sudo systemctl enable fault-review

# 启动服务
sudo systemctl start fault-review

# 查看服务状态
sudo systemctl status fault-review

# 查看日志
sudo journalctl -u fault-review -f
```

## 数据备份与恢复

### 数据目录结构

```
data/
├── cache/           # SQLite 缓存
├── cache.db         # SQLite 缓存数据库
├── rules/           # 规则文件
│   ├── builtin/     # 内置规则
│   └── custom/      # 自定义规则
└── standards/       # 开发规范文档

output/              # 输出报告
logs/                # 日志文件
```

### 备份数据

```bash
# 创建备份目录
BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# 备份数据目录
cp -r data $BACKUP_DIR/

# 备份输出目录（可选）
cp -r output $BACKUP_DIR/

# 备份配置文件（可选）
cp .env $BACKUP_DIR/
cp config/config.yaml $BACKUP_DIR/ 2>/dev/null || true

echo "Backup completed: $BACKUP_DIR"
```

### 恢复数据

```bash
# 指定备份目录
BACKUP_DIR="./backups/20260331_010000"

# 停止服务（如果正在运行）
# systemctl stop fault-review  # 或其他停止命令

# 恢复数据目录
cp -r $BACKUP_DIR/data .

# 恢复输出目录（可选）
cp -r $BACKUP_DIR/output . 2>/dev/null || true

# 恢复配置文件（可选）
cp $BACKUP_DIR/.env . 2>/dev/null || true
cp $BACKUP_DIR/config.yaml config/ 2>/dev/null || true

# 重新启动服务
# systemctl start fault-review

echo "Restore completed from: $BACKUP_DIR"
```

### 定时备份

创建 cron 任务进行定时备份：

```bash
# 编辑 crontab
crontab -e

# 添加每日备份任务（每天凌晨 2 点）
0 2 * * * /path/to/backup_script.sh >> /var/log/fault-review-backup.log 2>&1
```

## 监控与日志

### 日志管理

故障复盘分析工具使用 `loguru` 进行日志记录。日志默认输出到控制台和文件。

#### 日志级别

- `DEBUG`: 详细的调试信息
- `INFO`: 一般信息
- `WARNING`: 警告信息
- `ERROR`: 错误信息
- `CRITICAL`: 严重错误信息

#### 日志文件轮转

使用 `loguru` 的日志轮转功能：

```python
from loguru import logger
import sys

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="00:00",  # 每天午夜轮转
    retention="30 days",  # 保留 30 天
    compression="zip",  # 压缩旧日志
    level="INFO"
)
```

### 健康检查

API 服务提供健康检查接口：

```bash
GET /health
```

响应示例：

```json
{
  "status": "healthy",
  "timestamp": "2026-03-31T01:00:00",
  "version": "0.1.0"
}
```

### Prometheus 监控

可以集成 Prometheus 进行指标监控：

```python
from prometheus_fastapi_instrumentator import Instrumentator

# 在 FastAPI 应用中启用
Instrumentator().instrument(app).expose(app)
```

### Grafana 可视化

使用 Grafana 创建监控仪表板，监控以下指标：

- API 请求速率
- API 响应时间
- 错误率
- 内存使用情况
- CPU 使用情况

## 常见问题

### Q: 如何更新部署的版本？

A:
```bash
# Docker 部署
docker pull fault-review-analyzer:latest
docker-compose up -d

# Kubernetes 部署
kubectl set image deployment/fault-review-analyzer fault-review-analyzer=fault-review-analyzer:new-version -n fault-review
```

### Q: 如何迁移数据到新的部署环境？

A:
1. 在旧环境中备份数据
2. 将备份文件复制到新环境
3. 在新环境中恢复数据
4. 验证数据完整性

### Q: 如何处理 API 服务的高并发？

A:
1. 使用 Kubernetes 的 HPA 进行自动扩缩容
2. 使用缓存减少重复计算
3. 使用异步处理提高吞吐量
4. 使用负载均衡分发请求

### Q: 如何保证数据安全？

A:
1. 使用 HTTPS 加密传输
2. 定期备份数据
3. 使用访问控制限制数据访问
4. 加密敏感配置信息
5. 定期更新依赖库修复安全漏洞

### Q: 如何排查部署问题？

A:
1. 查看应用日志
2. 检查服务状态
3. 验证配置文件
4. 测试网络连接
5. 检查资源使用情况

---

**最后更新**: 2026-03-31
