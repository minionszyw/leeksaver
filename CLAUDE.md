# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

LeekSaver 是一个面向中国 A 股市场的本地化智能投研 Agent 系统，核心特点：
- 基于 LangGraph 的多轮对话 Agent 工作流
- 支持多个 LLM 提供商（DeepSeek、OpenAI、Ollama）
- 使用 AkShare 免费数据源
- PostgreSQL + TimescaleDB 时序数据存储
- React + TypeScript 前端，SSE 流式响应

## 常用命令

### 环境启动与停止
```bash
# 启动所有服务（Docker Compose）
docker compose up -d

# 停止所有服务
docker compose down

# 查看服务状态
docker compose ps

# 查看服务日志
docker compose logs -f backend        # 查看后端日志
docker compose logs -f celery-worker   # 查看 Celery Worker 日志
docker compose logs -f frontend        # 查看前端日志
```

### 数据库管理
```bash
# 创建新的数据库迁移
docker compose exec backend alembic revision --autogenerate -m "描述"

# 应用数据库迁移
docker compose exec backend alembic upgrade head

# 回滚上一个迁移
docker compose exec backend alembic downgrade -1

# 查看迁移历史
docker compose exec backend alembic history

# 直接访问数据库
docker compose exec db psql -U leeksaver -d leeksaver
```

### 数据同步
```bash
# 手动触发股票列表同步
docker compose exec backend python -c "
from app.tasks.sync_tasks import sync_stock_list
sync_stock_list.delay()
"

# 手动触发日线数据同步（指定日期）
docker compose exec backend python -c "
from app.tasks.sync_tasks import sync_daily_quotes
sync_daily_quotes.delay('2024-01-15')
"

# 查看同步状态
docker compose exec backend python -c "
from app.sync.status_manager import SyncStatusManager
from app.core.database import get_db
async def show_status():
    async for db in get_db():
        manager = SyncStatusManager(db)
        status = await manager.get_sync_status('stock_list')
        print(status)
import asyncio
asyncio.run(show_status())
"
```

### 后端开发
```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 运行测试
pytest                           # 运行所有测试
pytest tests/unit -v             # 运行单元测试
pytest tests/integration -v      # 运行集成测试
pytest --cov=app --cov-report=html  # 生成覆盖率报告

# 代码格式化和检查
black app tests                  # 格式化代码
ruff check app tests             # Linting 检查
mypy app                         # 类型检查

# 本地运行（开发模式，需要先启动 db 和 redis）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 运行 Celery Worker（本地调试）
celery -A app.tasks.celery_app worker --loglevel=info

# 运行 Celery Beat（本地调试）
celery -A app.tasks.celery_app beat --loglevel=info
```

### 前端开发
```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview

# Linting
npm run lint

# 运行测试
npm test
```

## 核心架构

### Agent 工作流（LangGraph）

工作流节点处理顺序：
1. **intent_router_node** - 意图识别（快速规则匹配 + LLM 分类）
2. **clarification_node** - 澄清不明确的查询（可选）
3. **fact_query_node** / **deep_analysis_node** - 根据意图分支
4. **tool_executor_node** - 执行工具调用
5. **interpreter_node** - LLM 生成自然语言解释
6. **error_handler** / **out_of_scope** / **chitchat** - 特殊处理

关键文件：
- `backend/app/agent/graph/workflow.py` - 工作流编排和 SSE 流式响应
- `backend/app/agent/graph/nodes.py` - 9 个处理节点实现
- `backend/app/agent/graph/state.py` - 工作流状态定义

### 意图识别系统

两阶段识别：
1. **快速规则匹配** - 基于关键词和模式快速分类（如价格查询、历史数据）
2. **LLM 分类** - 复杂意图使用 LLM 分类器

意图类型（IntentType）：
- `fact_query` - 数据速查（价格、估值、历史数据）
- `deep_analysis` - 深度分析（技术分析、基本面、新闻）
- `chitchat` - 闲聊
- `out_of_scope` - 超出范围

关键文件：
- `backend/app/agent/intent/router.py` - IntentRouter 核心逻辑（324 行）
- `backend/app/agent/intent/types.py` - 意图枚举和数据结构

### 工具系统

所有工具继承自 `BaseTool`，使用 `ToolRegistry` 统一管理。

工具调用流程：
1. 工具通过 `@ToolRegistry.register()` 装饰器注册
2. Agent 根据意图选择工具
3. 工具执行前进行 JSON Schema 验证（`app/agent/schema/validator.py`）
4. 工具返回结构化结果（遵循 `ToolResult` 格式）

关键工具：
- `FactQueryTool` - 数据速查（价格、估值、历史数据）
- `TechAnalysisTool` - 技术分析（MA、MACD、RSI）
- `FundamentalTool` - 基本面分析（财务指标、风险识别）
- `NewsSearchTool` - 新闻语义搜索（基于 pgvector）

关键文件：
- `backend/app/agent/tools/base.py` - BaseTool 和 ToolRegistry
- `backend/app/agent/tools/fact_query.py` - 数据速查工具
- `backend/app/agent/schema/tool_schemas.py` - 工具输入输出 Schema

### 数据层架构

**三层架构**：
```
API 层 (FastAPI)
  ↓
Repository 层（数据访问层，DAL）
  ↓
DataSource 层（数据源适配器）
  ↓
外部数据源（AkShare、数据库）
```

**Repository 模式**：
- 每个数据类型有对应的 Repository（如 `StockRepository`、`MarketDataRepository`）
- 所有数据库查询通过 Repository 进行，业务逻辑不直接操作 ORM
- 支持异步操作（SQLAlchemy 2.0 异步 API）

**DataSource 适配器**：
- `AkShareAdapter` - A 股行情数据（免费）
- `NewsAdapter` - 新闻数据抓取
- `SectorAdapter` - 板块数据
- `MacroAdapter` - 宏观经济指标
- 所有适配器继承自 `DataSourceBase`，统一接口

关键文件：
- `backend/app/repositories/stock_repository.py` - 股票基础数据访问
- `backend/app/repositories/market_data_repository.py` - 行情数据访问（TimescaleDB）
- `backend/app/datasources/akshare_adapter.py` - AkShare 数据源适配
- `backend/app/datasources/rate_limiter.py` - 频率限制和抖动防抖

### 数据模型

**核心表**：
- `Stock` - 股票基础信息（代码、名称、市场）
- `MarketData` - 日线行情（使用 TimescaleDB，按 `trade_date` 分区）
- `Financial` - 财务数据（PE、PB、ROE、负债率等）
- `News` - 新闻表（支持向量搜索，`embedding` 字段使用 pgvector）
- `Macro` - 宏观经济指标
- `Sector` - 板块数据
- `Watchlist` - 自选股

**时序数据优化**：
- `MarketData` 表使用 TimescaleDB 的 Hypertable 特性
- 按 `trade_date` 自动分区，提升查询性能
- 支持时间范围查询的高效索引

关键文件：
- `backend/app/models/` - 所有 SQLAlchemy ORM 模型
- `backend/alembic/versions/` - 数据库迁移文件

### 数据同步策略

**分级同步**：
- **L1 定期同步** - 收盘后全市场日线更新（Celery Beat 定时任务）
- **L2 重点同步** - 针对自选股的高频更新
- **L3 按需同步** - 用户请求时触发，提供可见反馈

**Celery 任务**：
- `sync_stock_list` - 每日同步股票列表
- `sync_daily_quotes` - 收盘后同步日线数据（16:00）
- `sync_watchlist_quotes` - 自选股行情更新（每小时）
- `sync_financial_statements` - 定期同步财务数据（每周六 20:00）
- `sync_market_news` - 全市场新闻同步（每天 8:00 和 18:00）
- `sync_watchlist_news` - 自选股新闻同步（每天 8:05 和 18:05，无自选股时降级为全市场新闻）
- `generate_news_embeddings` - 新闻向量生成（每小时第 30 分钟）
- `sync_sector_quotes` - 板块行情同步（16:30）
- `cleanup_old_news` - 过期新闻清理（每周一凌晨 2:00，保留 90 天，保护自选股新闻）

**自选股驱动同步**：
- 优先同步自选股相关的新闻数据
- 无自选股时自动降级为全市场新闻同步
- 数据清理时保护自选股相关的新闻不被删除

关键文件：
- `backend/app/tasks/sync_tasks.py` - Celery 任务定义
- `backend/app/sync/` - 同步逻辑实现
- `backend/app/sync/news_cleaner.py` - 新闻数据清理器

### LLM 抽象层

**工厂模式**：
- `LLMFactory` 根据配置动态创建 LLM 实例
- 支持三种提供商：DeepSeek、OpenAI、Ollama
- 所有 LLM 实现统一的 `BaseLLM` 接口

**配置**：
```python
# 通过环境变量配置
LLM_PROVIDER=deepseek  # 或 openai、ollama
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_MODEL=deepseek-chat
```

关键文件：
- `backend/app/agent/llm/factory.py` - LLM 工厂（84 行）
- `backend/app/agent/llm/base.py` - BaseLLM 接口
- `backend/app/agent/llm/providers/` - 各个 LLM 提供商实现

### 向量服务架构

**工厂模式**：
- `EmbeddingFactory` 根据配置动态创建向量服务提供商实例
- 支持三种提供商：OpenAI、SiliconFlow、Ollama
- 所有提供商实现统一的 `BaseEmbeddingProvider` 接口
- 向量服务与 LLM 服务完全解耦，可独立配置

**提供商特性**：
- **OpenAI** - `text-embedding-3-small`，1536 维，批次大小 20
- **SiliconFlow** - `BAAI/bge-large-zh-v1.5`（中文优化），1024 维，批次大小 50
- **Ollama** - `nomic-embed-text`（本地部署），768 维，批次大小 1

**配置**：
```python
# 通过环境变量配置
EMBEDDING_PROVIDER=openai  # 或 siliconflow、ollama
EMBEDDING_OPENAI_API_KEY=sk-xxx
EMBEDDING_OPENAI_MODEL=text-embedding-3-small
EMBEDDING_OPENAI_DIMENSION=1536
```

**使用方式**：
```python
# 自动从配置获取默认提供商
from app.services.embedding_service import embedding_service
embeddings = await embedding_service.generate_embeddings_batch(texts)

# 或手动指定提供商
from app.services.embedding.factory import EmbeddingFactory
provider = EmbeddingFactory.create("siliconflow")
embedding = await provider.generate_embedding(text)
```

关键文件：
- `backend/app/services/embedding/base.py` - 向量服务抽象基类
- `backend/app/services/embedding/factory.py` - 向量服务工厂
- `backend/app/services/embedding/providers/openai.py` - OpenAI 提供商
- `backend/app/services/embedding/providers/siliconflow.py` - SiliconFlow 提供商
- `backend/app/services/embedding/providers/ollama.py` - Ollama 提供商
- `backend/app/services/embedding_service.py` - 统一入口（维持向后兼容）

### 前端架构

**技术栈**：
- React 18 + TypeScript
- Vite（构建工具）
- Zustand（状态管理）
- Tailwind CSS（样式）
- Axios + React Query（数据获取）
- Server-Sent Events（SSE 流式响应）

**状态管理**：
- `chatStore.ts` - 对话历史和会话状态
- `watchlistStore.ts` - 自选股状态
- `toastStore.ts` - 提示信息状态

**SSE 流式响应**：
- 使用 `useSSE` Hook 处理 SSE 连接
- 支持实时展示 Agent 思考过程（thinking、tool_call、tool_result、response）

关键文件：
- `frontend/src/stores/chatStore.ts` - 核心对话状态（201 行）
- `frontend/src/hooks/useSSE.ts` - SSE 连接管理（116 行）
- `frontend/src/components/chat/ChatContainer.tsx` - 对话容器组件

## 职责分离原则

**LLM 职责**（不滥用 LLM）：
- ✅ 意图识别
- ✅ 自然语言结果解释
- ✅ 闲聊和对话管理
- ❌ 数值计算（应使用 SQL 或 Polars）
- ❌ 技术指标推导（应使用专门的计算库）
- ❌ 数据查询（应使用 Repository）

**计算层职责**：
- ✅ SQL 聚合和统计
- ✅ Polars 数据处理
- ✅ 技术指标计算
- ❌ 自然语言理解

## 开发注意事项

### 后端开发
1. **异步编程**：所有数据库操作使用 `async/await`
2. **类型安全**：使用 Pydantic 进行数据验证
3. **错误处理**：工具执行失败时，返回 `ToolResult` 的 `error` 字段
4. **Schema 验证**：新增工具时，必须在 `tool_schemas.py` 中定义输入输出 Schema
5. **数据库迁移**：修改模型后，创建 Alembic 迁移文件

### 前端开发
1. **TypeScript 严格模式**：所有组件使用 TypeScript，避免 `any`
2. **状态管理**：使用 Zustand，避免 prop drilling
3. **SSE 处理**：对话组件需要正确处理 SSE 的各种事件类型
4. **错误边界**：关键组件添加错误边界处理

### 数据同步
1. **频率限制**：AkShare 有频率限制，使用 `rate_limiter.py` 防止触发限制
2. **增量同步**：优先使用增量同步，避免全量同步浪费资源
3. **错误重试**：使用 `tenacity` 库进行重试（指数退避）
4. **同步状态**：使用 `SyncStatusManager` 记录同步状态

### 工具开发
1. **继承 BaseTool**：所有工具必须继承 `BaseTool`
2. **注册工具**：使用 `@ToolRegistry.register()` 装饰器注册
3. **Schema 定义**：在 `tool_schemas.py` 中定义输入输出 Schema
4. **返回格式**：返回 `ToolResult` 对象，包含 `success`、`data`、`error` 字段
5. **幂等性**：工具应该是幂等的，多次执行相同参数应得到相同结果

## 配置文件

### 后端配置（环境变量）
- `POSTGRES_*` - 数据库配置
- `REDIS_*` - Redis 配置
- `CELERY_*` - Celery 配置
- `LLM_PROVIDER` - LLM 提供商选择（deepseek/openai/ollama）
- `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` - LLM API 密钥
- `EMBEDDING_PROVIDER` - 向量服务提供商（openai/siliconflow/ollama）
- `EMBEDDING_*_API_KEY` - 各提供商的向量服务 API 密钥
- `NEWS_SYNC_MARKET_LIMIT` - 全市场新闻每次同步数量（默认 50）
- `NEWS_SYNC_WATCHLIST_LIMIT_PER_STOCK` - 自选股新闻每只股票获取数量（默认 5）
- `NEWS_SYNC_BATCH_INTERVAL` - 批量获取新闻时的批次间隔秒数（默认 0.5）
- `EMBEDDING_BATCH_SIZE` - 向量生成批次大小（默认 100）
- `NEWS_RETENTION_DAYS` - 新闻保留天数（默认 90）
- `NEWS_CLEANUP_PROTECT_WATCHLIST` - 是否保护自选股新闻不被清理（默认 true）

完整配置参考：`backend/app/config.py`（Pydantic Settings）

### 前端配置
- `VITE_API_URL` - 后端 API 地址（默认：http://localhost:8000）

配置文件：`frontend/.env`

## 访问端点

- **前端**：http://localhost:3000
- **API 文档**：http://localhost:8000/docs（Swagger UI）
- **ReDoc 文档**：http://localhost:8000/redoc
- **健康检查**：http://localhost:8000/api/v1/health

## 依赖说明

### 关键后端依赖
- `fastapi` - Web 框架
- `sqlalchemy` - 异步 ORM
- `langgraph` - Agent 工作流编排
- `polars` - 高性能数据处理
- `akshare` - A 股免费数据源
- `pgvector` - 向量搜索扩展
- `celery` - 异步任务队列
- `redis` - 缓存和消息队列

### 关键前端依赖
- `react` + `react-dom` - UI 框架
- `zustand` - 状态管理
- `axios` - HTTP 客户端
- `@tanstack/react-query` - 数据获取和缓存
- `tailwindcss` - 原子化 CSS

## 常见问题

### 数据同步失败
- 检查 AkShare 是否可用：`docker compose exec backend python -c "import akshare as ak; print(ak.__version__)"`
- 查看 Celery Worker 日志：`docker compose logs -f celery-worker`
- 检查 Redis 连接：`docker compose exec redis redis-cli ping`

### LLM 调用失败
- 检查 API Key 配置：`docker compose exec backend env | grep API_KEY`
- 查看后端日志：`docker compose logs -f backend`
- 测试 LLM 连接：访问 http://localhost:8000/docs 并测试聊天接口

### 数据库迁移问题
- 查看当前版本：`docker compose exec backend alembic current`
- 重置数据库（危险！）：`docker compose down -v && docker compose up -d`
- 手动应用迁移：`docker compose exec backend alembic upgrade head`

## 项目文档

- **系统设计文档**：`docs/系统设计说明书.md`
- **部署指南**：`docs/DEPLOYMENT.md`
- **开发指南**：`docs/DEVELOPMENT.md`
