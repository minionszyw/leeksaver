# LeekSaver 数据流水线验证报告 (Data Pipeline Test Report)

## 1. 验证目标
确保数据从 **AkShare (源)** -> **Adapter (清洗/转换)** -> **Celery (调度)** -> **TimescaleDB (存储)** -> **Sync Errors (监控)** 的全链路稳定性、准确性和健壮性。

## 2. 测试概览
- **测试时间**: 2025-12-31 08:30 (UTC+8)
- **测试环境**: Docker 生产镜像容器 (leeksaver-celery-worker)
- **总体评价**: **稳健 (Robust)**。全链路闭环正常，自愈机制已生效。

---

## 3. 详细验证结果

### 阶段 A: 存储层物理验证 (Storage Integrity)
验证 TimescaleDB 时序引擎的配置。
- **验证方法**: SQL 查询 `timescaledb_information.hypertables` 视图。
- **结果**: ✅ **通过**
    - `daily_quotes`: 确认为超表，已自动创建 **104 个时间分区 (chunks)**。
    - `minute_quotes`: 确认为超表，已创建 2 个分区。
- **结论**: 存储层已具备海量时序数据的水平扩展与高效查询能力。

### 阶段 B: ETL 清洗逻辑验证 (Cleaning Logic)
验证数据适配器（Adapter）对脏数据的防御能力。
- **验证方法**: 运行 `scripts/test_etl_cleaning.py`，使用 Mock 数据模拟异常。
- **测试点**:
    - 价格倒挂 (High < Low): 成功识别并过滤 1 条脏数据。
    - 极端涨跌幅 (> 30%): 成功拦截 1 条异常记录。
- **结果**: ✅ **通过**
- **结论**: ETL 规则能有效防止异常价格进入数据库，保证了 K 线数据的真实性。

### 阶段 C: 错误追踪系统验证 (Error Tracking)
验证系统在极端故障下的自我记录与自愈能力。
- **验证方法**: 运行 `scripts/test_error_tracking.py`，模拟 AkShare 连接超时。
- **结果**: ✅ **通过** (经代码修正后)
    - **发现问题**: 原 `sync_single` 逻辑吞掉了异常，导致错误无法上报。
    - **修复动作**: 修改 `daily_quote_syncer.py`，确保异常冒泡至 `sync_batch` 层级。
    - **实测表现**: 异常发生时 `sync_errors` 实时产生记录；网络恢复后，成功同步并自动标记该错误为 `resolved`。
- **结论**: 错误监控链路已实现闭环，支持断点续传与故障追踪。

### 阶段 D: 数据健康巡检 (Data Doctor Audit)
使用系统内置的 `Data Doctor` 模块进行全库体检。
- **验证方法**: 运行 `scripts/run_pipeline_audit.py` (内置审计逻辑)。
- **实时指标**:
    - **STOCK 覆盖率**: 53.9% (2948/5469) - ⚠️ *补录中*
    - **ETF 覆盖率**: 12.6% (167/1329) - ⚠️ *补录中*
    - **数据新鲜度**: ✅ **100% (2025-12-31)** - 证明实时快照同步正常。
    - **数据质量**: ✅ **优** (最近3天 0 异常)
    - **自愈能力**: **已自动下发 3683 只标的的补录任务 (共 37 个分片)**。
- **结果**: ✅ **通过 (自愈生效)**
- **结论**: 系统具备出色的自我审计能力，能自动发现并修复数据空洞。

---

## 4. 后续行动建议 (Action Items)
1. **完成全量补录**: 目前 STOCK 覆盖率约 54%，建议保持 Worker 开启 2 小时以完成 Data Doctor 触发的自动修复任务。
2. **补充行业元数据**: 当前行业覆盖率为 0%，需关注 `sync_stock_list` 任务中的 `enrich_metadata` 子任务。
3. **监控错误表**: 定期检查 `sync_errors` 中 `resolved_at` 仍为空的记录，排查接口变动。