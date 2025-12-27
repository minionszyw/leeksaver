# 数据存储与调度策略文档

本文档详细描述了 LeekSaver 项目的数据库表结构、字段定义以及各数据的分层调度策略。

## 1. 数据库概览

本项目主要使用 PostgreSQL (配合 TimescaleDB 插件) 存储结构化数据和时序数据。

**核心数据表清单：**

| 表名 | 描述 | 存储类型 |
| :--- | :--- | :--- |
| `stocks` | 股票/ETF 基础信息 | 关系型 |
| `watchlist` | 用户自选股 | 关系型 |
| `daily_quotes` | 日线行情 (L1) | **时序数据 (Hypertable)** |
| `minute_quotes` | 分钟行情 (L3) | **时序数据 (Hypertable)** |
| `financial_statements` | 财务报表 | 关系型 |
| `operation_data` | 经营数据 (KV) | 关系型 |
| `news_articles` | 财经新闻 (含向量) | 关系型 + pgvector |
| `northbound_flows` | 北向资金 | 时序数据 |
| `stock_fund_flows` | 个股资金流向 | 时序数据 |
| `dragon_tiger` | 龙虎榜数据 | 关系型 |
| `margin_trades` | 融资融券 | 时序数据 |
| `market_sentiments` | 市场情绪指标 | 时序数据 |
| `limit_up_stocks` | 涨停股详情 | 关系型 |
| `daily_valuations` | 每日估值 (PE/PB) | 时序数据 |
| `tech_indicators` | 技术指标预计算 | 时序数据 |
| `sectors` | 板块基础信息 | 关系型 |
| `sector_quotes` | 板块行情 | 时序数据 |
| `macro_indicators` | 宏观经济数据 | 时序数据 |

---

## 2. 数据表详情

### 2.1 基础信息

#### `stocks` (股票/ETF 基础信息)
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `code` | String(10) | **主键**。股票代码 (如 000001) |
| `name` | String(50) | 股票名称 |
| `market` | String(10) | 市场 (SH/SZ/BJ) |
| `asset_type` | String(10) | 类型 (stock/etf) |
| `industry` | String(50) | 所属行业 |
| `list_date` | Date | 上市日期 |
| `is_active` | Boolean | 是否正常交易 |

#### `watchlist` (自选股)
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `id` | Integer | **主键** |
| `code` | String(10) | 股票代码 |
| `sort_order` | Integer | 排序顺序 |
| `note` | String(200) | 备注 |

#### `sectors` (板块信息)
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `code` | String(20) | **主键**。板块代码 |
| `name` | String(100) | 板块名称 |
| `sector_type` | String(20) | 类型 (industry/concept/region) |
| `level` | Integer | 级别 (1/2/3) |
| `parent_code` | String(20) | 父板块代码 |

### 2.2 行情数据

#### `daily_quotes` (日线行情)
*TimescaleDB Hypertable*
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `code` | String(10) | **主键**。股票代码 |
| `trade_date` | Date | **主键**。交易日期 |
| `open` | Numeric | 开盘价 |
| `high` | Numeric | 最高价 |
| `low` | Numeric | 最低价 |
| `close` | Numeric | 收盘价 |
| `volume` | BigInteger | 成交量 (股) |
| `amount` | Numeric | 成交额 (元) |
| `change` | Numeric | 涨跌额 |
| `change_pct` | Numeric | 涨跌幅 (%) |
| `turnover_rate` | Numeric | 换手率 (%) |

#### `minute_quotes` (分钟行情)
*TimescaleDB Hypertable*
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `code` | String(10) | **主键**。股票代码 |
| `timestamp` | DateTime | **主键**。时间戳 |
| `open/high/low/close` | Numeric | OHLC |
| `volume` | BigInteger | 成交量 |

#### `sector_quotes` (板块行情)
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `sector_code` | String(20) | 板块代码 |
| `trade_date` | Date | 交易日期 |
| `index_value` | Numeric | 板块指数 |
| `change_pct` | Numeric | 涨跌幅 |
| `leading_stock` | String(10) | 领涨股代码 |

### 2.3 财务与基本面

#### `financial_statements` (财务报表)
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `code` | String(10) | **主键** |
| `end_date` | Date | **主键**。报告期截止日 |
| `report_type` | String(20) | 报告类型 (一季报/年报等) |
| `pub_date` | Date | 公告日期 |
| `total_revenue` | Numeric | 营业总收入 |
| `net_profit` | Numeric | 归母净利润 |
| `roe_weighted` | Numeric | ROE |
| `gross/net_profit_margin` | Numeric | 毛利率/净利率 |
| `revenue/net_profit_yoy` | Numeric | 同比增长率 |

#### `daily_valuations` (每日估值)
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `code` | String(10) | **主键** |
| `trade_date` | Date | **主键** |
| `pe_ttm` | Numeric | 市盈率 (TTM) |
| `pb` | Numeric | 市净率 |
| `total_mv` | Numeric | 总市值 |
| `dv_ttm` | Numeric | 股息率 |

### 2.4 资金面

#### `northbound_flows` (北向资金)
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `trade_date` | Date | **主键** |
| `sh/sz_net_inflow` | Numeric | 沪/深股通净流入 |
| `total_net_inflow` | Numeric | 合计净流入 |

#### `stock_fund_flows` (个股资金流向)
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `code` | String(10) | **主键** |
| `trade_date` | Date | **主键** |
| `main_net_inflow` | Numeric | 主力净流入 |
| `super/large/medium/small_net` | Numeric | 超大/大/中/小单净流入 |

#### `dragon_tiger` (龙虎榜)
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `code` | String(10) | 股票代码 |
| `trade_date` | Date | 交易日期 |
| `reason` | String | 上榜原因 |
| `net_amount` | Numeric | 净买入额 |

### 2.5 情绪与资讯

#### `news_articles` (新闻)
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `id` | Integer | **主键** |
| `title` | String | 标题 |
| `content` | Text | 正文 |
| `publish_time` | DateTime | 发布时间 |
| `related_stocks` | String | 关联股票 (JSON) |
| `embedding` | Vector(1536) | 文本向量 (OpenAI) |

#### `market_sentiments` (市场情绪)
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `trade_date` | Date | **主键** |
| `limit_up/down_count` | Integer | 涨跌停家数 |
| `rising/falling_count` | Integer | 涨跌家数 |
| `continuous_limit_up_count` | Integer | 连板家数 |

---

## 3. 分层调度策略

系统采用分层异步调度策略，根据数据的重要性和更新频率进行区分。

### 3.1 核心行情 (L1 & L2)
*   **日线行情 (Full Market)**:
    *   **策略**: 每日全量同步。
    *   **时机**: 交易日收盘后 (约 16:00)。
*   **自选股行情 (Watchlist)**:
    *   **策略**: 优先高频同步。
    *   **时机**: 交易日 08:00 - 18:00 之间可能有多次触发，或用户访问时按需同步。
*   **分钟行情 (On-Demand)**:
    *   **策略**: 仅按需获取，保留短期数据。

### 3.2 盘后数据 (Post-Close Analysis)
以下数据在每日收盘后（通常 17:00 - 19:00）依次执行：
1.  **北向资金**: 获取当日沪深股通流向。
2.  **个股资金流向**: 获取主力/散户资金分布。
3.  **龙虎榜**: 获取当日上榜数据 (通常 18:00 后数据完整)。
4.  **融资融券**: 获取前一交易日两融余额 (交易所延时发布)。
5.  **市场情绪**: 统计当日涨跌停、连板高度等。
6.  **每日估值**: 基于收盘价更新 PE/PB/市值。
7.  **技术指标**: 重新计算全市场 MA/MACD/RSI 等。
8.  **板块行情**: 更新行业/概念板块指数。

### 3.3 资讯与非结构化数据
*   **财经新闻**:
    *   **频率**: 每日两次 (早 08:00 晨报，晚 18:00 收盘总结)。
    *   **范围**: 全市场热点 + 自选股相关。
    *   **处理**: 每小时批量生成 Embedding 向量。
*   **财务报表**:
    *   **频率**: 每周一次 (通常周末)。
    *   **逻辑**: 扫描全市场是否有新发布的季度/年度报告。

### 3.4 基础数据
*   **股票列表**: 定期同步 (如每周或每月)，处理新股上市/退市。
*   **宏观数据**: 低频更新 (月度/季度)，通常在每月固定日期发布后同步。
