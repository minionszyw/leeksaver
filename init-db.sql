-- LeekSaver 数据库初始化脚本
-- 启用必要的扩展

-- 启用 TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 启用 pgvector (向量检索)
CREATE EXTENSION IF NOT EXISTS vector;

-- 启用 pg_trgm (模糊搜索)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 输出确认信息
DO $$
BEGIN
    RAISE NOTICE 'LeekSaver 数据库初始化完成';
    RAISE NOTICE 'TimescaleDB 版本: %', (SELECT extversion FROM pg_extension WHERE extname = 'timescaledb');
END $$;
