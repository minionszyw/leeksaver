# 分层调度策略迁移指南

## 概述

本次重构将 LeekSaver 的数据同步配置从 **38 个碎片化变量** 简化为 **4 个策略级配置**，采用分层调度策略（L1/L2/L3）。

**重构效果**：
- 配置简化率：**85%**（从 38 个减少到 10 个）
- 运维复杂度：大幅降低
- 代码质量：从硬编码转为声明式注册表
- 可扩展性：新增数据源仅需添加一行元数据

---

## 配置迁移步骤

### 步骤 1: 更新 `.env` 文件

**删除以下旧配置**（可选，保留不会影响系统运行）：

```bash
# 这些配置已废弃，可以删除
SYNC_DAILY_QUOTES_HOUR
SYNC_DAILY_QUOTES_MINUTE
SYNC_WATCHLIST_QUOTES_MINUTE
SYNC_MARKET_NEWS_MORNING_HOUR
SYNC_MARKET_NEWS_MORNING_MINUTE
SYNC_MARKET_NEWS_EVENING_HOUR
SYNC_MARKET_NEWS_EVENING_MINUTE
SYNC_WATCHLIST_NEWS_MORNING_HOUR
SYNC_WATCHLIST_NEWS_MORNING_MINUTE
SYNC_WATCHLIST_NEWS_EVENING_HOUR
SYNC_WATCHLIST_NEWS_EVENING_MINUTE
GENERATE_EMBEDDINGS_MINUTE
SYNC_SECTOR_QUOTES_HOUR
SYNC_SECTOR_QUOTES_MINUTE
SYNC_WATCHLIST_INTERVAL_SECONDS
SYNC_WATCHLIST_OFF_HOURS_INTERVAL
SYNC_NORTHBOUND_FLOW_HOUR
SYNC_NORTHBOUND_FLOW_MINUTE
SYNC_FUND_FLOW_HOUR
SYNC_FUND_FLOW_MINUTE
SYNC_DRAGON_TIGER_HOUR
SYNC_DRAGON_TIGER_MINUTE
SYNC_MARGIN_TRADE_HOUR
SYNC_MARGIN_TRADE_MINUTE
SYNC_MARKET_SENTIMENT_HOUR
SYNC_MARKET_SENTIMENT_MINUTE
SYNC_VALUATION_HOUR
SYNC_VALUATION_MINUTE
CALC_TECH_INDICATORS_HOUR
CALC_TECH_INDICATORS_MINUTE
```

**新增以下 4 个策略配置**：

```bash
# ==================== 分层调度策略配置 ====================

# L1 - 日更组：收盘后统一同步时间（格式：HH:MM，24小时制）
# 适用于：龙虎榜、估值、财报、宏观数据、技术指标、资金面数据
SYNC_L1_DAILY_TIME=17:30

# L2 - 日内组：高频更新间隔（单位：秒）
# 适用于：新闻资讯、自选股行情、板块异动、向量生成
# 推荐值：300（5分钟）
SYNC_L2_INTERVAL_SECONDS=300

# L2 任务错开间隔（单位：秒）
# 避免任务同时执行造成资源竞争
# 推荐值：120（2分钟）
SYNC_L2_TASK_OFFSET_SECONDS=120

# L3 - 按需组：实时数据缓存失效时间（单位：秒）
# 适用于：单股详情页查询
REALTIME_CACHE_TTL=10
```

**保留以下特殊任务配置**（如需自定义）：

```bash
# 财务报表同步（默认：每周六 20:00）
SYNC_FINANCIAL_DAY_OF_WEEK=6
SYNC_FINANCIAL_HOUR=20
SYNC_FINANCIAL_MINUTE=0

# 新闻清理（默认：每周一凌晨 2:00）
CLEANUP_NEWS_DAY_OF_WEEK=0
CLEANUP_NEWS_HOUR=2
CLEANUP_NEWS_MINUTE=0
```

### 步骤 2: 重启服务

```bash
docker compose down
docker compose up -d
```

### 步骤 3: 验证配置

```bash
# 查看配置加载情况
docker compose exec backend python -c "
from app.config import settings
print(f'L1 时间: {settings.sync_l1_daily_time}')
print(f'L2 间隔: {settings.sync_l2_interval_seconds}秒')
print(f'L2 偏移: {settings.sync_l2_task_offset_seconds}秒')
print(f'L3 缓存: {settings.realtime_cache_ttl}秒')
"

# 查看生成的调度配置
docker compose exec backend python -c "
from app.tasks.celery_app import generate_beat_schedule
schedule = generate_beat_schedule()
print(f'总任务数: {len(schedule)}')
for name in sorted(schedule.keys()):
    print(f'  - {name}')
"
```

### 步骤 4: 查看 Celery Beat 日志

```bash
docker compose logs -f celery-beat
```

---

## 任务分层说明

### L1 - 低频/日更组（17:30 统一执行）

收盘后执行一次，数据更新频率低：

- `daily-market-sync` - 日线数据
- `daily-dragon-tiger-sync` - 龙虎榜
- `daily-valuation-sync` - 估值数据
- `daily-northbound-flow-sync` - 北向资金
- `daily-fund-flow-sync` - 个股资金流向
- `daily-margin-trade-sync` - 两融数据
- `daily-market-sentiment-sync` - 市场情绪
- `daily-tech-indicator-calc` - 技术指标（依赖日线数据）

### L2 - 高频/日内组（每 300 秒，错开执行）

盘中持续更新，需定时轮询：

- `intraday-market-news-sync` - 市场新闻（偏移: 0秒）
- `intraday-watchlist-news-sync` - 自选股新闻（偏移: 120秒）
- `intraday-watchlist-quotes-sync` - 自选股行情（偏移: 240秒）
- `intraday-sector-quotes-sync` - 板块行情（偏移: 360秒）
- `intraday-news-embeddings-gen` - 新闻向量生成（偏移: 480秒）

### 特殊任务（独立配置）

- `weekly-financial-sync` - 财报（每周六 20:00）
- `weekly-news-cleanup` - 新闻清理（每周一 02:00）

---

## 配置参数说明

### SYNC_L1_DAILY_TIME

- **格式**：HH:MM（24小时制）
- **默认值**：17:30
- **说明**：所有 L1 任务统一执行的时间点
- **示例**：
  - `18:00` - 收盘后 1.5 小时执行
  - `16:30` - 收盘后 0.5 小时执行

### SYNC_L2_INTERVAL_SECONDS

- **格式**：整数（秒）
- **范围**：60-3600（1分钟-1小时）
- **默认值**：300（5分钟）
- **说明**：L2 任务的轮询间隔
- **示例**：
  - `300` - 每 5 分钟执行一次
  - `600` - 每 10 分钟执行一次

### SYNC_L2_TASK_OFFSET_SECONDS

- **格式**：整数（秒）
- **范围**：0-300
- **默认值**：120（2分钟）
- **说明**：L2 任务之间的错开间隔，避免资源竞争
- **计算方式**：
  - 任务 1：偏移 0 * 120 = 0秒
  - 任务 2：偏移 1 * 120 = 120秒
  - 任务 3：偏移 2 * 120 = 240秒
  - ...

### REALTIME_CACHE_TTL

- **格式**：整数（秒）
- **范围**：1-300
- **默认值**：10
- **说明**：L3 按需查询的缓存时间

---

## 常见问题

### Q1: 旧配置不删除会有影响吗？

**A**: 不会。新配置系统会忽略旧配置变量，保留不会影响系统运行。

### Q2: 如何调整某个 L1 任务的执行时间？

**A**: 目前所有 L1 任务统一在 `SYNC_L1_DAILY_TIME` 时间执行。如需单独调整某个任务：

1. 在 `backend/app/tasks/task_registry.py` 中将该任务从 `L1_TASKS` 移到 `SPECIAL_TASKS`
2. 在 `backend/app/config.py` 中添加该任务的独立配置
3. 在 `backend/app/tasks/celery_app.py` 的 `generate_beat_schedule()` 函数中处理该任务

### Q3: 如何新增一个数据源？

**A**: 只需在 `backend/app/tasks/task_registry.py` 中添加一行元数据：

```python
TaskMetadata(
    name="daily-new-data-sync",
    task_path="app.tasks.sync_tasks.sync_new_data",
    tier=TaskTier.L1,  # 或 L2/SPECIAL
    schedule_type=ScheduleType.CRONTAB,
    offset_multiplier=0,  # 仅 L2 任务需要
    description="新数据源同步",
)
```

### Q4: L2 任务的 offset 是如何工作的？

**A**:
- 假设 `SYNC_L2_INTERVAL_SECONDS=300`，`SYNC_L2_TASK_OFFSET_SECONDS=120`
- 任务 1（offset_multiplier=0）：立即执行，然后每 300 秒执行
- 任务 2（offset_multiplier=1）：延迟 120 秒执行，然后每 300 秒执行
- 任务 3（offset_multiplier=2）：延迟 240 秒执行，然后每 300 秒执行

这样可以避免所有任务在同一时间点执行，分散资源压力。

### Q5: 如何查看 Celery Beat 的实际调度情况？

**A**:

```bash
# 查看调度状态
docker compose exec backend celery -A app.tasks.celery_app inspect scheduled

# 查看 Beat 日志
docker compose logs -f celery-beat | grep -E "(daily-market-sync|intraday-market-news-sync)"
```

---

## 回滚方案

如果遇到问题需要回滚到旧版本：

```bash
# 1. 切换到重构前的 commit
git checkout <重构前的 commit hash>

# 2. 重启服务
docker compose down
docker compose up -d --build

# 3. 验证
docker compose logs -f celery-beat
```

---

## 技术支持

如遇到问题，请提供以下信息：

1. `.env` 文件中的调度配置
2. Celery Beat 日志：`docker compose logs celery-beat`
3. Celery Worker 日志：`docker compose logs celery-worker`
4. 错误截图或报错信息

---

## 总结

本次重构通过引入 **任务注册表** 和 **动态调度生成**，将配置从"任务级"提升至"策略级"，实现了：

✅ 配置简化：从 38 个减少到 4 个（简化 85%）
✅ 运维简单：只需配置"收盘时间"和"日内间隔"
✅ 代码清晰：声明式注册表，一目了然
✅ 易于扩展：新增数据源仅需一行代码
✅ 类型安全：Pydantic 验证，减少配置错误

用户只需关心 **L1 何时执行**、**L2 多久轮询**、**L2 如何错开**、**L3 缓存多久** 4 个核心问题，大幅降低运维复杂度。
