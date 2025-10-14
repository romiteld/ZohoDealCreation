-- Migration: PowerBI Analytics Views
-- Purpose: Create optimized views for PowerBI monitoring dashboard
-- Date: 2025-10-13

-- =====================================================================
-- VIEW 1: Daily Delivery Summary
-- =====================================================================
CREATE OR REPLACE VIEW vault_alerts_daily_summary AS
SELECT
    DATE(created_at) as delivery_date,
    audience,
    COUNT(*) as total_deliveries,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count,
    COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_count,
    COUNT(CASE WHEN status = 'scheduled' THEN 1 END) as scheduled_count,
    ROUND(
        COUNT(CASE WHEN status = 'completed' THEN 1 END)::numeric /
        NULLIF(COUNT(*), 0) * 100,
        2
    ) as success_rate_pct,
    AVG(execution_time_ms) / 1000.0 as avg_execution_sec,
    MAX(execution_time_ms) / 1000.0 as max_execution_sec,
    MIN(execution_time_ms) / 1000.0 as min_execution_sec,
    SUM(total_candidates) as total_candidates,
    SUM(advisor_cards_count) as total_advisor_cards,
    SUM(executive_cards_count) as total_executive_cards,
    AVG(total_candidates)::numeric as avg_candidates_per_delivery,
    COUNT(DISTINCT user_email) as unique_users
FROM vault_alert_deliveries
GROUP BY DATE(created_at), audience
ORDER BY delivery_date DESC, audience;

COMMENT ON VIEW vault_alerts_daily_summary IS
'Daily aggregated metrics for PowerBI dashboard - optimized for time series visualizations';

-- =====================================================================
-- VIEW 2: User Activity Summary
-- =====================================================================
CREATE OR REPLACE VIEW vault_alerts_user_summary AS
SELECT
    user_email,
    user_id,
    COUNT(*) as total_deliveries,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count,
    ROUND(
        COUNT(CASE WHEN status = 'completed' THEN 1 END)::numeric /
        NULLIF(COUNT(*), 0) * 100,
        2
    ) as success_rate_pct,
    MAX(created_at) as last_delivery_date,
    MIN(created_at) as first_delivery_date,
    SUM(total_candidates) as total_candidates_received,
    -- Audience preferences (counts)
    COUNT(CASE WHEN audience = 'advisors' THEN 1 END) as advisors_count,
    COUNT(CASE WHEN audience = 'c_suite' THEN 1 END) as c_suite_count,
    COUNT(CASE WHEN audience = 'global' THEN 1 END) as global_count,
    -- Most common audience
    MODE() WITHIN GROUP (ORDER BY audience) as preferred_audience,
    -- Average execution time
    AVG(execution_time_ms) / 1000.0 as avg_execution_sec
FROM vault_alert_deliveries
GROUP BY user_email, user_id
ORDER BY total_deliveries DESC;

COMMENT ON VIEW vault_alerts_user_summary IS
'Per-user aggregated metrics for PowerBI dashboard - shows user engagement and preferences';

-- =====================================================================
-- VIEW 3: Recent Failures (Last 100)
-- =====================================================================
CREATE OR REPLACE VIEW vault_alerts_recent_failures AS
SELECT
    delivery_id,
    created_at,
    started_at,
    completed_at,
    user_email,
    audience,
    total_candidates,
    execution_time_ms / 1000.0 as execution_sec,
    error_message,
    -- Truncate error for readability
    LEFT(error_message, 200) as error_summary,
    -- Calculate duration
    EXTRACT(EPOCH FROM (completed_at - started_at)) as duration_sec,
    -- Add custom filters for debugging
    custom_filters
FROM vault_alert_deliveries
WHERE status = 'failed'
ORDER BY created_at DESC
LIMIT 100;

COMMENT ON VIEW vault_alerts_recent_failures IS
'Last 100 failed deliveries for PowerBI troubleshooting dashboard';

-- =====================================================================
-- VIEW 4: Hourly Performance Metrics
-- =====================================================================
CREATE OR REPLACE VIEW vault_alerts_hourly_performance AS
SELECT
    DATE_TRUNC('hour', created_at) as hour_timestamp,
    audience,
    COUNT(*) as delivery_count,
    AVG(execution_time_ms) / 1000.0 as avg_execution_sec,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY execution_time_ms) / 1000.0 as median_execution_sec,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY execution_time_ms) / 1000.0 as p95_execution_sec,
    MAX(execution_time_ms) / 1000.0 as max_execution_sec,
    AVG(total_candidates) as avg_candidates,
    SUM(advisor_cards_count) as total_advisor_cards,
    SUM(executive_cards_count) as total_executive_cards
FROM vault_alert_deliveries
WHERE status IN ('completed', 'failed')  -- Exclude in_progress for accurate metrics
GROUP BY DATE_TRUNC('hour', created_at), audience
ORDER BY hour_timestamp DESC;

COMMENT ON VIEW vault_alerts_hourly_performance IS
'Hourly performance metrics including percentiles - for performance degradation monitoring';

-- =====================================================================
-- VIEW 5: Audience Comparison
-- =====================================================================
CREATE OR REPLACE VIEW vault_alerts_audience_comparison AS
SELECT
    audience,
    COUNT(*) as total_deliveries,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count,
    ROUND(
        COUNT(CASE WHEN status = 'completed' THEN 1 END)::numeric /
        NULLIF(COUNT(*), 0) * 100,
        2
    ) as success_rate_pct,
    AVG(execution_time_ms) / 1000.0 as avg_execution_sec,
    AVG(total_candidates) as avg_candidates,
    AVG(advisor_cards_count) as avg_advisor_cards,
    AVG(executive_cards_count) as avg_executive_cards,
    -- Total cards generated
    SUM(advisor_cards_count + executive_cards_count) as total_cards,
    -- Avg cards per candidate (anonymization efficiency)
    ROUND(
        SUM(advisor_cards_count + executive_cards_count)::numeric /
        NULLIF(SUM(total_candidates), 0),
        2
    ) as avg_cards_per_candidate
FROM vault_alert_deliveries
GROUP BY audience
ORDER BY total_deliveries DESC;

COMMENT ON VIEW vault_alerts_audience_comparison IS
'Audience-level aggregated metrics - shows performance and usage differences by audience type';

-- =====================================================================
-- Grant SELECT permissions to PowerBI
-- =====================================================================
-- Note: In production, create a dedicated powerbi_reader role with read-only access

-- Example (uncomment and customize for production):
-- CREATE ROLE powerbi_reader WITH LOGIN PASSWORD 'secure_password';
-- GRANT CONNECT ON DATABASE wellintake TO powerbi_reader;
-- GRANT USAGE ON SCHEMA public TO powerbi_reader;
-- GRANT SELECT ON vault_alerts_daily_summary TO powerbi_reader;
-- GRANT SELECT ON vault_alerts_user_summary TO powerbi_reader;
-- GRANT SELECT ON vault_alerts_recent_failures TO powerbi_reader;
-- GRANT SELECT ON vault_alerts_hourly_performance TO powerbi_reader;
-- GRANT SELECT ON vault_alerts_audience_comparison TO powerbi_reader;
-- GRANT SELECT ON vault_alert_deliveries TO powerbi_reader;

-- =====================================================================
-- Indexes for View Performance (if not already present)
-- =====================================================================

-- Check if indexes exist before creating (idempotent)
DO $$
BEGIN
    -- Index for date range queries
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_vault_alert_deliveries_created_at') THEN
        CREATE INDEX idx_vault_alert_deliveries_created_at
        ON vault_alert_deliveries(created_at DESC);
    END IF;

    -- Index for status filtering
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_vault_alert_deliveries_status') THEN
        CREATE INDEX idx_vault_alert_deliveries_status
        ON vault_alert_deliveries(status);
    END IF;

    -- Composite index for date + audience queries
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_vault_alert_deliveries_created_audience') THEN
        CREATE INDEX idx_vault_alert_deliveries_created_audience
        ON vault_alert_deliveries(created_at DESC, audience);
    END IF;

    -- Index for user activity queries
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_vault_alert_deliveries_user_email') THEN
        CREATE INDEX idx_vault_alert_deliveries_user_email
        ON vault_alert_deliveries(user_email);
    END IF;
END
$$;

-- =====================================================================
-- Test Queries
-- =====================================================================

-- Verify views work correctly
SELECT 'Daily Summary - Last 7 days' as test_name, COUNT(*) as row_count
FROM vault_alerts_daily_summary
WHERE delivery_date >= CURRENT_DATE - INTERVAL '7 days'
UNION ALL
SELECT 'User Summary - Total users', COUNT(*)
FROM vault_alerts_user_summary
UNION ALL
SELECT 'Recent Failures - Last 100', COUNT(*)
FROM vault_alerts_recent_failures
UNION ALL
SELECT 'Hourly Performance - Last 24 hours', COUNT(*)
FROM vault_alerts_hourly_performance
WHERE hour_timestamp >= NOW() - INTERVAL '24 hours'
UNION ALL
SELECT 'Audience Comparison', COUNT(*)
FROM vault_alerts_audience_comparison;

-- Performance test: Check view execution time
EXPLAIN ANALYZE
SELECT * FROM vault_alerts_daily_summary
WHERE delivery_date >= CURRENT_DATE - INTERVAL '30 days';
