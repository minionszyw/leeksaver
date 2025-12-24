# LeekSaver 开发指南

## 项目结构

```
LeekSaver/
├── backend/                    # 后端代码
│   ├── app/
│   │   ├── agent/             # Agent 核心
│   │   │   ├── graph/         # LangGraph 工作流
│   │   │   ├── intent/        # 意图识别
│   │   │   ├── interpreter/   # 结果解释
│   │   │   ├── llm/           # LLM 适配层
│   │   │   ├── schema/        # Schema 验证
│   │   │   ├── session/       # 会话管理
│   │   │   └── tools/         # 工具系统
│   │   ├── api/               # API 端点
│   │   ├── core/              # 核心模块
│   │   ├── datasources/       # 数据源
│   │   ├── models/            # 数据模型
│   │   ├── repositories/      # 数据访问层
│   │   ├── sync/              # 同步管理
│   │   └── tasks/             # Celery 任务
│   ├── alembic/               # 数据库迁移
│   └── tests/                 # 测试
├── frontend/                   # 前端代码
│   ├── src/
│   │   ├── components/        # React 组件
│   │   ├── hooks/             # 自定义 Hooks
│   │   ├── pages/             # 页面组件
│   │   ├── services/          # API 服务
│   │   ├── stores/            # 状态管理
│   │   └── styles/            # 样式
│   └── ...
├── docs/                       # 文档
└── docker-compose.yml          # Docker 配置
```

## 开发环境搭建

### 后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 配置环境变量
cp ../.env.example ../.env
# 编辑 .env 文件

# 启动依赖服务
docker compose up -d postgres redis

# 运行迁移
alembic upgrade head

# 启动开发服务器
uvicorn app.main:app --reload

# 启动 Celery Worker（另一个终端）
celery -A app.tasks.celery_app worker --loglevel=info
```

### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 核心概念

### Agent 工作流

```
用户输入
    │
    ▼
┌─────────────┐
│ 意图路由器   │ ─── 快速规则 / LLM 分类
└──────┬──────┘
       │
       ├──► fact_query ──► 数据速查工具
       ├──► deep_analysis ──► 技术/基本面分析
       ├──► chitchat ──► 闲聊响应
       └──► out_of_scope ──► 超范围提示
       │
       ▼
┌─────────────┐
│ 工具执行器   │ ─── 调用注册的工具
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 结果解释器   │ ─── 转换为自然语言
└──────┬──────┘
       │
       ▼
   最终响应
```

### LLM 抽象层

支持多个 LLM 提供商：

```python
from app.agent.llm.factory import get_llm

# 根据配置自动选择
llm = get_llm()

# 或指定提供商
llm = get_llm(provider="deepseek")
```

### 工具系统

创建新工具：

```python
from app.agent.tools.base import ToolBase, ToolResult, ToolRegistry

class MyTool(ToolBase):
    name = "my_tool"
    description = "工具描述"

    async def execute(self, param1: str) -> ToolResult:
        # 执行逻辑
        return ToolResult(success=True, data={"result": "..."})

# 注册工具
ToolRegistry.register(MyTool)
```

## 测试

### 运行测试

```bash
cd backend

# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit -v

# 运行集成测试
pytest tests/integration -v

# 带覆盖率
pytest --cov=app --cov-report=html
```

### 测试结构

```
tests/
├── conftest.py          # 共享 fixtures
├── unit/                # 单元测试
│   ├── test_intent_router.py
│   ├── test_tools.py
│   └── test_schema_validator.py
└── integration/         # 集成测试
    ├── test_api.py
    └── test_workflow.py
```

## 代码规范

### Python

- 使用 Black 格式化
- 使用 isort 排序导入
- 使用 mypy 类型检查
- 遵循 PEP 8

```bash
# 格式化
black app/
isort app/

# 类型检查
mypy app/
```

### TypeScript/React

- 使用 ESLint + Prettier
- 使用函数组件和 Hooks
- 使用 TypeScript 严格模式

```bash
# 格式化和检查
npm run lint
npm run format
```

## 数据库迁移

```bash
# 创建新迁移
alembic revision --autogenerate -m "描述"

# 应用迁移
alembic upgrade head

# 回滚
alembic downgrade -1

# 查看历史
alembic history
```

## 添加新功能

### 1. 添加新的意图类型

编辑 `app/agent/intent/types.py`:

```python
class IntentCategory(str, Enum):
    # 添加新类型
    NEW_CATEGORY = "new_category"
```

### 2. 添加新的工作流节点

编辑 `app/agent/graph/nodes.py`:

```python
async def new_node(state: AgentState) -> AgentState:
    # 节点逻辑
    return state
```

在 `workflow.py` 中注册节点。

### 3. 添加新的 API 端点

在 `app/api/v1/endpoints/` 下创建新文件，然后在 `router.py` 中注册。

### 4. 添加新的前端页面

1. 在 `frontend/src/pages/` 创建页面组件
2. 在 `App.tsx` 添加路由
3. 更新导航组件

## 调试技巧

### 后端日志

```python
from app.core.logging import get_logger

logger = get_logger(__name__)
logger.info("消息", key="value")
```

### 前端调试

```typescript
// React DevTools
// Redux DevTools（如使用）

// 控制台日志
console.log('调试信息', data)
```

### API 调试

- 使用 `/docs` 的 Swagger UI
- 使用 Postman/Insomnia
- 查看 Network 面板

## 常见问题

**Q: 如何切换 LLM 提供商？**

修改 `.env` 中的 `LLM_PROVIDER` 和对应的 API Key。

**Q: 如何添加新的数据源？**

在 `app/datasources/` 下创建新的适配器，实现统一接口。

**Q: 如何自定义提示词？**

编辑对应模块中的 `*_PROMPT` 常量。
