-- Migration: Executive Vault Alerts
-- Description: Add vault candidate alerts subscription system for executives only
-- Author: Claude
-- Date: 2025-10-11
--
-- Purpose: Enable Steve, Brandon, and Daniel to subscribe to customized vault alerts
--          with unlimited filter options (locations, designations, compensation, etc.)

-- ============================================
-- 1. Extend teams_user_preferences with vault alerts fields
-- ============================================

-- Add vault alerts subscription columns
ALTER TABLE teams_user_preferences
ADD COLUMN IF NOT EXISTS vault_alerts_enabled BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS vault_alerts_settings JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS last_vault_alert_sent_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS next_vault_alert_scheduled_at TIMESTAMP;

-- Add index for vault alerts queries
CREATE INDEX IF NOT EXISTS idx_teams_user_preferences_vault_alerts_enabled
ON teams_user_preferences(vault_alerts_enabled)
WHERE vault_alerts_enabled = TRUE;

CREATE INDEX IF NOT EXISTS idx_teams_user_preferences_vault_next_scheduled
ON teams_user_preferences(next_vault_alert_scheduled_at)
WHERE vault_alerts_enabled = TRUE;

-- Create GIN index for JSONB queries on custom filters
CREATE INDEX IF NOT EXISTS idx_teams_user_preferences_vault_settings
ON teams_user_preferences USING GIN (vault_alerts_settings);

COMMENT ON COLUMN teams_user_preferences.vault_alerts_enabled IS 'Whether user has active vault candidate alerts subscription (executives only)';
COMMENT ON COLUMN teams_user_preferences.vault_alerts_settings IS 'JSONB configuration: audience, frequency, delivery_email, max_candidates, custom_filters';
COMMENT ON COLUMN teams_user_preferences.last_vault_alert_sent_at IS 'Timestamp of last successful vault alert delivery';
COMMENT ON COLUMN teams_user_preferences.next_vault_alert_scheduled_at IS 'Calculated next vault alert delivery time based on frequency';


-- ============================================
-- 2. Create vault_alert_deliveries tracking table
-- ============================================

CREATE TABLE IF NOT EXISTS vault_alert_deliveries (
    id SERIAL PRIMARY KEY,
    delivery_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL,
    user_email VARCHAR(255),
    delivery_email VARCHAR(255) NOT NULL,

    -- Alert parameters
    audience VARCHAR(100) NOT NULL, -- 'advisors', 'executives', 'both'
    frequency VARCHAR(50), -- 'weekly', 'biweekly', 'monthly'
    max_candidates INTEGER,
    custom_filters JSONB, -- Locations, designations, availability, compensation range

    -- Execution details
    status VARCHAR(50) DEFAULT 'scheduled', -- 'scheduled', 'processing', 'sent', 'failed'
    advisor_cards_count INTEGER DEFAULT 0,
    executive_cards_count INTEGER DEFAULT 0,
    total_candidates INTEGER DEFAULT 0,
    execution_time_ms INTEGER,
    error_message TEXT,

    -- Email details
    email_subject VARCHAR(500),
    email_sent_at TIMESTAMP,
    email_message_id VARCHAR(255),

    -- Results
    advisor_html TEXT,
    executive_html TEXT,
    generation_metadata JSONB, -- Cache hit rate, quality metrics, filters applied

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    CONSTRAINT fk_vault_user_preferences
        FOREIGN KEY (user_id)
        REFERENCES teams_user_preferences(user_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vault_alert_deliveries_delivery_id ON vault_alert_deliveries(delivery_id);
CREATE INDEX IF NOT EXISTS idx_vault_alert_deliveries_user_id ON vault_alert_deliveries(user_id);
CREATE INDEX IF NOT EXISTS idx_vault_alert_deliveries_status ON vault_alert_deliveries(status);
CREATE INDEX IF NOT EXISTS idx_vault_alert_deliveries_created_at ON vault_alert_deliveries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_vault_alert_deliveries_custom_filters ON vault_alert_deliveries USING GIN (custom_filters);

COMMENT ON TABLE vault_alert_deliveries IS 'Track automated vault candidate alert email deliveries (executive-only feature)';
COMMENT ON COLUMN vault_alert_deliveries.custom_filters IS 'JSONB filters applied: locations, designations, availability, compensation range, date range';
COMMENT ON COLUMN vault_alert_deliveries.generation_metadata IS 'Quality metrics, cache performance, and generation statistics';


-- ============================================
-- 3. Update calculate_next_digest_time to support biweekly
-- ============================================

CREATE OR REPLACE FUNCTION calculate_next_digest_time(
    frequency VARCHAR(50),
    timezone VARCHAR(50) DEFAULT 'America/New_York'
)
RETURNS TIMESTAMP AS $$
DECLARE
    next_time TIMESTAMP;
    current_time_tz TIMESTAMPTZ;
BEGIN
    -- Get current time in user's timezone
    current_time_tz := NOW() AT TIME ZONE timezone;

    CASE frequency
        WHEN 'daily' THEN
            -- Next day at 9 AM
            next_time := (DATE_TRUNC('day', current_time_tz) + INTERVAL '1 day' + INTERVAL '9 hours') AT TIME ZONE timezone;

        WHEN 'weekly' THEN
            -- Next Monday at 9 AM
            next_time := (DATE_TRUNC('week', current_time_tz) + INTERVAL '1 week' + INTERVAL '9 hours') AT TIME ZONE timezone;

        WHEN 'biweekly' THEN
            -- Two weeks from now, Monday at 9 AM
            next_time := (DATE_TRUNC('week', current_time_tz) + INTERVAL '2 weeks' + INTERVAL '9 hours') AT TIME ZONE timezone;

        WHEN 'monthly' THEN
            -- First day of next month at 9 AM
            next_time := (DATE_TRUNC('month', current_time_tz) + INTERVAL '1 month' + INTERVAL '9 hours') AT TIME ZONE timezone;

        ELSE
            -- Default to weekly
            next_time := (DATE_TRUNC('week', current_time_tz) + INTERVAL '1 week' + INTERVAL '9 hours') AT TIME ZONE timezone;
    END CASE;

    RETURN next_time;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_next_digest_time IS 'Calculate next scheduled delivery time (supports daily, weekly, biweekly, monthly)';


-- ============================================
-- 4. Create trigger to auto-update next_vault_alert_scheduled_at
-- ============================================

CREATE OR REPLACE FUNCTION update_next_vault_alert_scheduled()
RETURNS TRIGGER AS $$
DECLARE
    frequency_value VARCHAR(50);
BEGIN
    -- Only update if vault alerts are enabled
    IF NEW.vault_alerts_enabled = TRUE THEN
        -- Extract frequency from JSONB settings
        frequency_value := NEW.vault_alerts_settings->>'frequency';

        -- Default to weekly if frequency not set
        IF frequency_value IS NULL THEN
            frequency_value := 'weekly';
        END IF;

        NEW.next_vault_alert_scheduled_at := calculate_next_digest_time(
            frequency_value,
            NEW.timezone
        );
    ELSE
        NEW.next_vault_alert_scheduled_at := NULL;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create separate triggers for INSERT and UPDATE
DROP TRIGGER IF EXISTS teams_user_preferences_vault_alert_insert ON teams_user_preferences;
CREATE TRIGGER teams_user_preferences_vault_alert_insert
    BEFORE INSERT ON teams_user_preferences
    FOR EACH ROW
    WHEN (NEW.vault_alerts_enabled = TRUE)
    EXECUTE FUNCTION update_next_vault_alert_scheduled();

DROP TRIGGER IF EXISTS teams_user_preferences_vault_alert_update ON teams_user_preferences;
CREATE TRIGGER teams_user_preferences_vault_alert_update
    BEFORE UPDATE ON teams_user_preferences
    FOR EACH ROW
    WHEN (
        NEW.vault_alerts_enabled = TRUE AND (
            NEW.vault_alerts_enabled <> OLD.vault_alerts_enabled
            OR NEW.vault_alerts_settings IS DISTINCT FROM OLD.vault_alerts_settings
        )
    )
    EXECUTE FUNCTION update_next_vault_alert_scheduled();

COMMENT ON FUNCTION update_next_vault_alert_scheduled IS 'Auto-calculate next vault alert delivery when subscription is activated or settings change';


-- ============================================
-- 5. Views: Active vault alert subscriptions
-- ============================================

CREATE OR REPLACE VIEW active_vault_alert_subscriptions AS
SELECT
    u.user_id,
    u.user_email,
    u.user_name,
    u.vault_alerts_settings->>'delivery_email' as delivery_email,
    u.vault_alerts_settings->>'audience' as audience,
    u.vault_alerts_settings->>'frequency' as frequency,
    (u.vault_alerts_settings->>'max_candidates')::INTEGER as max_candidates,
    u.vault_alerts_settings->'custom_filters' as custom_filters,
    u.timezone,
    u.last_vault_alert_sent_at,
    u.next_vault_alert_scheduled_at,
    COUNT(v.id) as total_alerts_sent,
    MAX(v.email_sent_at) as last_email_sent_at
FROM teams_user_preferences u
LEFT JOIN vault_alert_deliveries v ON u.user_id = v.user_id AND v.status = 'sent'
WHERE u.vault_alerts_enabled = TRUE
  AND u.vault_alerts_settings->>'delivery_email' IS NOT NULL
GROUP BY u.user_id, u.user_email, u.user_name, u.vault_alerts_settings,
         u.timezone, u.last_vault_alert_sent_at, u.next_vault_alert_scheduled_at;

COMMENT ON VIEW active_vault_alert_subscriptions IS 'Active vault alert subscriptions with delivery stats (executive-only feature)';


-- ============================================
-- 6. View: Vault alert subscriptions due for delivery
-- ============================================

CREATE OR REPLACE VIEW vault_alerts_due_for_delivery AS
SELECT
    s.*
FROM active_vault_alert_subscriptions s
WHERE s.next_vault_alert_scheduled_at <= NOW()
ORDER BY s.next_vault_alert_scheduled_at ASC;

COMMENT ON VIEW vault_alerts_due_for_delivery IS 'Vault alert subscriptions that should receive delivery now';


-- ============================================
-- 7. Initialize executive users with vault alerts access
-- ============================================

-- Grant vault alerts access to executives (they'll still need to opt-in)
-- Default settings template for executives
DO $$
DECLARE
    default_vault_settings JSONB := '{
        "audience": "advisors",
        "frequency": "weekly",
        "delivery_email": null,
        "max_candidates": 50,
        "custom_filters": {
            "locations": [],
            "designations": [],
            "availability": null,
            "compensation_min": null,
            "compensation_max": null,
            "date_range_days": null,
            "search_terms": []
        }
    }';
BEGIN
    -- Update existing executive users to have vault alerts access
    -- (but not enabled by default - they need to explicitly subscribe)
    UPDATE teams_user_preferences
    SET vault_alerts_settings = default_vault_settings
    WHERE user_email IN (
        'steve@emailthewell.com',
        'brandon@emailthewell.com',
        'daniel.romitelli@emailthewell.com'
    )
    AND vault_alerts_settings = '{}';

    RAISE NOTICE 'Initialized vault alerts settings for executive users';
END $$;


-- ============================================
-- 8. Helper function: Check if user has vault alerts access
-- ============================================

CREATE OR REPLACE FUNCTION has_vault_alerts_access(check_email VARCHAR(255))
RETURNS BOOLEAN AS $$
DECLARE
    user_role VARCHAR(50);
BEGIN
    -- Check user role from teams_user_roles table
    SELECT role INTO user_role
    FROM teams_user_roles
    WHERE LOWER(user_email) = LOWER(check_email);

    -- Only executives have vault alerts access
    RETURN user_role = 'executive';
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION has_vault_alerts_access IS 'Check if user has permission to access vault alerts feature (executives only)';


-- ============================================
-- 9. Row-level security policy for vault alerts (optional)
-- ============================================

-- Add check constraint to ensure only executives can enable vault alerts
-- This is enforced at the application layer, but adding DB constraint for extra safety
ALTER TABLE teams_user_preferences
DROP CONSTRAINT IF EXISTS check_vault_alerts_executive_only;

ALTER TABLE teams_user_preferences
ADD CONSTRAINT check_vault_alerts_executive_only
CHECK (
    vault_alerts_enabled = FALSE
    OR has_vault_alerts_access(user_email) = TRUE
);

COMMENT ON CONSTRAINT check_vault_alerts_executive_only ON teams_user_preferences
IS 'Ensure only executive users can enable vault alerts subscriptions';


-- ============================================
-- Verification Queries
-- ============================================

-- Check new columns
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'teams_user_preferences'
  AND column_name IN ('vault_alerts_enabled', 'vault_alerts_settings', 'last_vault_alert_sent_at', 'next_vault_alert_scheduled_at')
ORDER BY ordinal_position;

-- Check vault_alert_deliveries table
SELECT tablename FROM pg_tables
WHERE tablename = 'vault_alert_deliveries';

-- Check new views
SELECT viewname FROM pg_views
WHERE viewname IN ('active_vault_alert_subscriptions', 'vault_alerts_due_for_delivery')
ORDER BY viewname;

-- Verify executive users have vault alerts settings initialized
SELECT
    user_email,
    vault_alerts_enabled,
    vault_alerts_settings->>'audience' as default_audience,
    vault_alerts_settings->>'frequency' as default_frequency,
    has_vault_alerts_access(user_email) as has_access
FROM teams_user_preferences
WHERE user_email IN (
    'steve@emailthewell.com',
    'brandon@emailthewell.com',
    'daniel.romitelli@emailthewell.com'
);

-- Test vault alerts access function
SELECT
    'steve@emailthewell.com' as email,
    has_vault_alerts_access('steve@emailthewell.com') as has_access
UNION ALL
SELECT
    'test.recruiter@emailthewell.com',
    has_vault_alerts_access('test.recruiter@emailthewell.com')
UNION ALL
SELECT
    'brandon@emailthewell.com',
    has_vault_alerts_access('brandon@emailthewell.com');
