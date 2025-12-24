# LeekSaver 部署指南

## 目录

- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [Docker 部署](#docker-部署)
- [手动部署](#手动部署)
- [生产环境配置](#生产环境配置)
- [监控与运维](#监控与运维)

## 环境要求

### 最低配置
- CPU: 2 核
- 内存: 4GB
- 磁盘: 20GB

### 推荐配置
- CPU: 4 核
- 内存: 8GB
- 磁盘: 50GB SSD

### 软件依赖
- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+ (手动部署)
- Node.js 18+ (手动部署)
- PostgreSQL 15+ with TimescaleDB
- Redis 7+

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-org/leeksaver.git
cd leeksaver
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入必要的配置
```

**必填配置项：**
- `DEEPSEEK_API_KEY` 或其他 LLM API Key
- `POSTGRES_PASSWORD` - 数据库密码

### 3. 启动服务

```bash
docker compose up -d
```

### 4. 初始化数据库

```bash
# 运行数据库迁移
docker compose exec backend alembic upgrade head

# 同步股票列表（首次）
docker compose exec backend python -c "
from app.tasks.sync_tasks import sync_stock_list
sync_stock_list.delay()
"
```

### 5. 访问应用

- 前端: http://localhost:3000
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/api/v1/health

## Docker 部署

### 服务架构

```
┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   Backend   │
│   (React)   │     │  (FastAPI)  │
└─────────────┘     └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────┐     ┌─────────────┐   ┌─────────────┐
│  PostgreSQL │     │    Redis    │   │   Celery    │
│ +TimescaleDB│     │             │   │   Worker    │
└─────────────┘     └─────────────┘   └─────────────┘
```

### Docker Compose 配置

完整的 `docker-compose.yml` 已包含在项目中。主要服务：

| 服务 | 端口 | 说明 |
|------|------|------|
| frontend | 3000 | React 前端 |
| backend | 8000 | FastAPI 后端 |
| postgres | 5432 | PostgreSQL + TimescaleDB |
| redis | 6379 | Redis 缓存/消息队列 |
| celery | - | 后台任务处理 |

### 常用命令

```bash
# 启动所有服务
docker compose up -d

# 查看日志
docker compose logs -f backend

# 重启服务
docker compose restart backend

# 停止服务
docker compose down

# 清理所有数据（慎用）
docker compose down -v
```

## 手动部署

### 后端部署

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 运行迁移
alembic upgrade head

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 启动 Celery Worker
celery -A app.tasks.celery_app worker --loglevel=info

# 启动 Celery Beat（定时任务）
celery -A app.tasks.celery_app beat --loglevel=info
```

### 前端部署

```bash
cd frontend

# 安装依赖
npm install

# 开发模式
npm run dev

# 生产构建
npm run build

# 预览构建结果
npm run preview
```

## 生产环境配置

### 环境变量

```bash
# .env.production
APP_ENV=production
DEBUG=false

# 使用强密码
POSTGRES_PASSWORD=your_strong_password_here

# 限制 CORS
CORS_ORIGINS=https://your-domain.com

# 日志配置
LOG_LEVEL=WARNING
LOG_FORMAT=json
```

### Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 重定向到 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # 前端
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 支持
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
```

### 数据库优化

```sql
-- PostgreSQL 配置建议 (postgresql.conf)
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
work_mem = 64MB
max_connections = 100

-- TimescaleDB 配置
timescaledb.max_background_workers = 4
```

## 监控与运维

### 健康检查端点

| 端点 | 说明 |
|------|------|
| `/api/v1/health` | 完整健康检查 |
| `/api/v1/health/liveness` | 存活检查 |
| `/api/v1/health/readiness` | 就绪检查 |

### 日志查看

```bash
# 查看后端日志
docker compose logs -f backend

# 查看 Celery 日志
docker compose logs -f celery

# 查看所有日志
docker compose logs -f
```

### 数据备份

```bash
# 备份数据库
docker compose exec postgres pg_dump -U leeksaver leeksaver > backup.sql

# 恢复数据库
docker compose exec -T postgres psql -U leeksaver leeksaver < backup.sql
```

### 常见问题

**Q: LLM API 调用失败**
- 检查 API Key 是否正确
- 检查网络连接
- 查看 `/api/v1/health` 中 LLM 组件状态

**Q: 数据同步失败**
- 检查 Celery Worker 是否运行
- 查看 `/api/v1/sync/status` 获取详细状态
- 检查 AkShare 速率限制配置

**Q: 前端无法连接后端**
- 检查 CORS 配置
- 确认后端服务正常运行
- 检查 Nginx 代理配置

## 更新升级

```bash
# 拉取最新代码
git pull origin main

# 重新构建并启动
docker compose build
docker compose up -d

# 运行数据库迁移
docker compose exec backend alembic upgrade head
```
