# LeekSaver 智能投研 Agent 系统

<div align="center">

**面向中国 A 股市场的本地化智能投研助手**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.0+-blue.svg)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://react.dev/)

</div>

## ✨ 特性

- 🤖 **多 LLM 支持** - 支持 DeepSeek、OpenAI、Ollama 等多个 LLM 提供商
- 💬 **智能对话** - 基于 LangGraph 的工作流引擎，支持流式响应
- 📊 **数据速查** - 快速查询股票价格、估值、历史数据
- 📈 **技术分析** - MA、MACD、RSI 等技术指标分析
- 💼 **基本面分析** - 财务指标、亮点风险识别
- ⭐ **自选股管理** - 便捷的自选股列表管理
- 🔄 **数据同步** - 基于 AkShare 的免费数据源
- 🎨 **现代化 UI** - React + TypeScript + Tailwind CSS

## 🏗️ 技术架构

### 后端技术栈
- **框架**: FastAPI (异步 Python Web 框架)
- **数据库**: PostgreSQL + TimescaleDB (时序数据)
- **缓存**: Redis (会话管理 + 消息队列)
- **任务队列**: Celery (后台数据同步)
- **AI**: LangGraph + 多 LLM 支持
- **数据源**: AkShare (免费 A 股数据)

### 前端技术栈
- **框架**: React 18 + TypeScript
- **构建**: Vite
- **样式**: Tailwind CSS
- **状态管理**: Zustand
- **HTTP 客户端**: Axios
- **实时通信**: Server-Sent Events (SSE)

### 核心组件

```
┌─────────────────────────────────────────────────┐
│              前端 (React + TS)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  聊天界面  │  │  自选股   │  │  数据展示  │      │
│  └──────────┘  └──────────┘  └──────────┘      │
└────────────────────┬────────────────────────────┘
                     │ SSE / REST API
                     ▼
┌─────────────────────────────────────────────────┐
│           后端 (FastAPI)                         │
│  ┌──────────────────────────────────────────┐  │
│  │      LangGraph 工作流引擎                 │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  │  │
│  │  │意图识别  │→│工具执行  │→│结果解释  │  │  │
│  │  └─────────┘  └─────────┘  └─────────┘  │  │
│  └──────────────────────────────────────────┘  │
│                                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │  LLM层  │  │  工具系统 │  │ 数据源  │        │
│  └─────────┘  └─────────┘  └─────────┘        │
└─────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│         数据层 (PostgreSQL + Redis)              │
└─────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+

### 1. 克隆项目

```bash
git clone https://github.com/minionszyw/leeksaver.git
cd leeksaver
```

### 2. 配置环境

```bash
cp .env.example .env
# 编辑 .env 文件，至少需要配置：
# - DEEPSEEK_API_KEY (或其他 LLM API Key)
# - POSTGRES_PASSWORD
```

### 3. 启动服务

```bash
docker compose up -d
```

### 4. 初始化数据

```bash
# 运行数据库迁移
docker compose exec backend alembic upgrade head

# 同步股票列表（可选，首次启动）
docker compose exec backend python -c "
from app.tasks.sync_tasks import sync_stock_list
sync_stock_list.delay()
"
```

### 5. 访问应用

- **前端**: http://localhost:3000
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/api/v1/health

## 📦 项目结构

```
LeekSaver/
├── backend/              # 后端代码
│   ├── app/
│   │   ├── agent/       # Agent 核心
│   │   ├── api/         # API 端点
│   │   ├── core/        # 核心模块
│   │   ├── datasources/ # 数据源
│   │   ├── models/      # 数据模型
│   │   └── tasks/       # Celery 任务
│   ├── alembic/         # 数据库迁移
│   └── tests/           # 测试
├── frontend/            # 前端代码
│   └── src/
│       ├── components/  # React 组件
│       ├── pages/       # 页面
│       ├── services/    # API 服务
│       └── stores/      # 状态管理
├── .env.example         # 文档
└── docker-compose.yml   # Docker 配置
```

## 🎯 核心功能

### 智能对话

- 支持自然语言查询股票信息
- 智能识别用户意图（价格查询、技术分析、基本面分析等）
- 流式响应，实时展示思考过程

### 数据分析

- **数据速查**: 实时股票价格、涨跌幅、成交量
- **技术分析**: 均线、MACD、RSI 等技术指标
- **基本面分析**: 财务指标、行业地位、风险提示

### 自选股管理

- 添加/移除自选股
- 一键分析自选股
- 实时行情展示

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🙏 致谢

- [AkShare](https://github.com/akfamily/akshare) - 免费的 A 股数据源
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent 工作流框架
- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的 Python Web 框架
- [React](https://react.dev/) - 用户界面库

---

**注意**: 本系统仅供学习研究使用，不构成任何投资建议。投资有风险，入市需谨慎。
