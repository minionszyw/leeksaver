# 数据层文档

## 1. 概览

本项目数据层采用 **PostgreSQL** 作为核心数据库，并集成了以下扩展以支持特定场景：
- **TimescaleDB**: 用于高效存储和查询金融时间序列数据（如行情、分钟线）。
- **pgvector**: 用于存储文本向量（如新闻 Embedding），支持 RAG（检索增强生成）场景。

ORM 框架使用 **SQLAlchemy 2.0**，支持异步操作。数据处理与清洗主要使用 **Polars**，以确保高性能。

## 2. 数据模型

### 2.1 核心基础数据
| 表名 | 描述 | 关键字段 |
| :--- | :--- | :--- |
| `stocks` | 股票/ETF 基础信息 | `code` (主键), `name`, `market`, `industry`, `list_date` |
| `sectors` | 板块/概念信息 | `code`, `name`, `sector_type` (industry/concept/region) |
| `watchlist` | 用户自选股 | `id`, `code`, `sort_order`, `note` |

### 2.2 行情数据 (TimescaleDB Hypertable)
这些表启用了 TimescaleDB 超表功能，按时间自动分区。

| 表名 | 描述 | 频率 | 关键字段 |
| :--- | :--- | :--- | :--- |
| `daily_quotes` | 日线行情 | 日频 | `code`, `trade_date`, `open`, `high`, `low`, `close`, `volume`, `amount` |
| `minute_quotes` | 分钟线行情 | 分钟频 | `code`, `timestamp`, `open`, `high`, `low`, `close`, `volume` |
| `sector_quotes` | 板块日线行情 | 日频 | `sector_code`, `trade_date`, `index_value`, `change_pct` |

### 2.3 财务与经营数据
| 表名 | 描述 | 关键字段 |
| :--- | :--- | :--- |
| `financial_statements` | 季度财务报表 | `code`, `end_date` (截止日), `report_type` (季报/年报), `total_revenue`, `net_profit`, `roe_weighted` |
| `operation_data` | 经营数据 (KV) | `code`, `period`, `metric_name`, `metric_value`, `unit` (用于存储非标准化的运营数据，如销量、产能) |

### 2.4 资金流向数据
| 表名 | 描述 | 关键字段 |
| :--- | :--- | :--- |
| `northbound_flows` | 北向资金 | `trade_date`, `sh_net_inflow`, `sz_net_inflow` |
| `stock_fund_flows` | 个股资金流向 | `code`, `trade_date`, `main_net_inflow` (主力净流入), `super_large_net` (超大单) |
| `dragon_tiger` | 龙虎榜 | `code`, `trade_date`, `reason`, `buy_amount`, `sell_amount` |
| `margin_trades` | 融资融券 | `code`, `trade_date`, `rzye` (融资余额), `rqyl` (融券余量) |

### 2.5 市场情绪与宏观
| 表名 | 描述 | 关键字段 |
| :--- | :--- | :--- |
| `market_sentiments` | 每日市场情绪 | `trade_date`, `rising_count` (上涨家数), `limit_up_count` (涨停家数), `highest_board_stock` (最高板) |
| `limit_up_stocks` | 涨停股详情 | `code`, `trade_date`, `limit_up_time`, `continuous_days` (连板天数), `concept` (涨停概念), `industry` |
| `macro_indicators` | 宏观经济指标 | `indicator_name` (GDP/CPI等), `period`, `value`, `yoy_rate` |

### 2.6 新闻与 AI (pgvector)
| 表名 | 描述 | 关键字段 |
| :--- | :--- | :--- |
| `news_articles` | 财经新闻 | `id`, `title`, `content`, `publish_time`, `embedding` (1536维向量) |

> **注**: `embedding` 字段默认使用 OpenAI `text-embedding-3-small` 模型生成（可通过环境变量 `EMBEDDING_OPENAI_MODEL` 配置），配合 HNSW 索引实现高效相似度搜索。

### 2.7 衍生指标
| 表名 | 描述 | 关键字段 |
| :--- | :--- | :--- |
| `daily_valuations` | 每日估值 | `code`, `trade_date`, `pe_ttm`, `pb`, `total_mv` (总市值), `dv_ttm` (股息率) |
| `tech_indicators` | 技术指标预计算 | `code`, `trade_date`, `ma5/10/20`, `macd_dif`, `rsi_14`, `kdj_k` |

### 2.8 系统管理
| 表名 | 描述 | 关键字段 |
| :--- | :--- | :--- |
| `sync_errors` | 同步错误日志 | `task_name`, `target_code`, `error_type`, `retry_count` |

## 3. 数据源 (Adapters)

项目统一使用 **AkShare** 作为主要数据源，通过 `Adapter` 模式进行封装。

- **AkShareAdapter** (`backend/app/datasources/akshare_adapter.py`)
    - 封装 AkShare 的同步 API 为异步方法（`run_in_executor`）。
    - 返回 **Polars DataFrame**，进行统一的数据清洗和格式转换。
    - **增强型元数据同步**：针对 A 股列表及行业分类，集成了**东方财富（EastMoney）**接口（如 `stock_board_industry_name_em`），提供更精确的行业归属及上市日期信息。
    - **自适应限频与重试**：内置基于令牌桶的限流控制（默认 5 QPS），并集成了**指数退避重试机制**（Exponential Backoff）。

主要接口：
- `get_stock_list()`: 获取 A 股列表（含 EM 行业信息）
- `get_daily_quotes(code, start, end)`: 获取日线行情（自动复权）
- `get_financial_statements(code)`: 获取财务报表
- `get_realtime_quote(code)`: 获取实时快照

## 4. 数据同步与分层调度 (Tiered Scheduling)
...
### 4.4 特殊任务
- **财务报表**: 每周六 20:00 同步全市场季报/年报。
- **数据清洗**: 每周一 02:00 清理过期新闻 (保留90天，自选股新闻受保护)。
- **健康巡检**: 每日 09:00 检查数据完整性并自动修复（通过 `DataDoctor`）。

同步流程由 Celery Beat 调度，`backend/app/tasks/schedules.py` 定义具体的时间策略，支持通过 `OffsetSchedule` 实现任务错峰执行。

## 5. 数据库交互与性能优化

- **查询**: 使用 SQLAlchemy 的 `select` 语法。`MarketDataRepository` 统一封装了日线与分钟线行情数据的访问。
- **批量写入**: `BaseRepository` 统一封装了批量插入/更新逻辑。为确保性能，数据库层默认按 **3000** 条记录进行分批写入。
- **配置化设计**: 系统提供了一组平衡性能与稳定性的技术参数。例如，`sync_batch_size`（默认 50）用于控制同步器单次从 API 获取数据的标的数量；`embedding_batch_size` 用于向量化处理。这些参数均支持通过环境变量或 `.env` 进行覆盖。
- **分析**: 对于复杂的时序分析（如计算 MA、收益率），建议利用 TimescaleDB 的 `time_bucket` 等函数在数据库层完成聚合，或加载到 Polars 进行内存计算。
- **向量检索**: 使用 `session.scalars(select(NewsArticle).order_by(NewsArticle.embedding.cosine_distance(query_vec)).limit(k))`.
