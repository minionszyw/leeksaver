## 数据库表状态

| 表名 | 中文名 | 类 | 源 | 同步任务 (Celery) | 层 | 数据量 | 备注 |
| :--- | :--- | :-: | :-: | :--- | :-: | --: | :--- |
| `daily_quotes` | 日线行情 | 超 | AKS | `daily_quotes` | L1 | 3,092,054 | |
| `financial_statements` | 财务报表 | 普 | AKS | `financial_statements` | L3 | 42,893 | |
| `stocks` | 股票列表 | 普 | AKS | `stock_list` | L1 | 6,795 | |
| `daily_valuations` | 每日估值 | 普 | AKS | `daily_valuation` | L1 | 5,471 | |
| `macro_indicators` | 宏观指标 | 普 | AKS | `macro_economic_data` | L3 | 4,739 | |
| `margin_trades` | 融资融券 | 普 | AKS | `margin_trade` | L1 | 3,992 | 手动验证通过 |
| `stock_news_articles` | 股票新闻 | 普 | 计算 | `stock_news_rotation` | L2 | 2,021 | |
| `minute_quotes` | 分时行情 | 超 | AKS | `minute_quotes` | L2 | 1,666 | |
| `sectors` | 板块信息 | 普 | AKS | `sector_quotes` | L1 | 527 | |
| `sector_quotes` | 板块行情 | 普 | AKS | `sector_quotes` | L1 | 527 | |
| `stock_fund_flows` | 资金流向 | 普 | AKS | `stock_fund_flow` | L1 | 299 | |
| `news_articles` | 全市快讯 | 普 | AKS | `global_news` | L2 | 179 | |
| `limit_up_stocks` | 涨停股 | 普 | AKS | `market_sentiment` | L1 | 155 | |
| `dragon_tiger` | 龙虎榜 | 普 | AKS | `dragon_tiger` | L1 | 82 | |
| `operation_data` | 经营数据 | 普 | AKS | `operation_data` | L3 | 45 | 手动验证通过(KV) |
| `northbound_flows` | 北向资金 | 普 | AKS | `northbound_flow` | L1 | 2 | |
| `watchlist` | 自选股 | 普 | 用户 | - | 特 | 1 | |
| `market_sentiments` | 市场情绪 | 普 | AKS | `market_sentiment` | L1 | 1 | |
| `alembic_version` | 数据库版本 | 普 | 系统 | - | 特 | 1 | |
| `tech_indicators` | 技术指标 | 普 | 计算 | `calculate_tech_indicators` | L1 | 0 | |
| `sync_errors` | 同步错误 | 普 | 系统 | - | 特 | 0 | |

## 常用查询命令

### Celery 任务操作
- **手动触发同步 (以经营数据为例)**:
  ```bash
  docker exec leeksaver-celery-worker celery -A app.tasks.celery_app call app.tasks.sync_tasks.sync_operation_data
  ```
- **查看 Celery Worker 日志**:
  ```bash
  docker logs --tail 100 leeksaver-celery-worker
  ```

### 数据库查询
- **查询总量**:
  ```sql
  docker exec leeksaver-db psql -U leeksaver -d leeksaver -c "SELECT count(*) FROM xxx ;"
  ```
- **查看最近同步记录**:
  ```sql
  docker exec leeksaver-db psql -U leeksaver -d leeksaver -c "SELECT * FROM xxx ORDER BY created_at DESC LIMIT 10;"
  ```
