-- Migration: Weekly Digest Subscriptions
-- Description: Add email delivery preferences and scheduled digest functionality
-- Author: Claude
-- Date: 2025-10-06

-- ============================================
-- 1. Extend teams_user_preferences with email subscription fields
-- ============================================

-- Add email subscription columns
ALTER TABLE teams_user_preferences
ADD COLUMN IF NOT EXISTS delivery_email VARCHAR(255),
ADD COLUMN IF NOT EXISTS max_candidates_per_digest INTEGER DEFAULT 6,
ADD COLUMN IF NOT EXISTS subscription_active BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS last_digest_sent_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS next_digest_scheduled_at TIMESTAMP;

-- Add index for scheduled digest queries
CREATE INDEX IF NOT EXISTS idx_teams_user_preferences_subscription_active
ON teams_user_preferences(subscription_active)
WHERE subscription_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_teams_user_preferences_next_scheduled
ON teams_user_preferences(next_digest_scheduled_at)
WHERE subscription_active = TRUE;

COMMENT ON COLUMN teams_user_preferences.delivery_email IS 'Email address for digest delivery (can differ from Teams user_email)';
COMMENT ON COLUMN teams_user_preferences.max_candidates_per_digest IS 'Number of candidates to include in weekly digest (default: 6)';
COMMENT ON COLUMN teams_user_preferences.subscription_active IS 'Whether user has active weekly digest subscription';
COMMENT ON COLUMN teams_user_preferences.last_digest_sent_at IS 'Timestamp of last successful digest delivery';
COMMENT ON COLUMN teams_user_preferences.next_digest_scheduled_at IS 'Calculated next delivery time based on frequency';


-- ============================================
-- 2. Create weekly_digest_deliveries tracking table
-- ============================================

CREATE TABLE IF NOT EXISTS weekly_digest_deliveries (
    id SERIAL PRIMARY KEY,
    delivery_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL,
    user_email VARCHAR(255),
    delivery_email VARCHAR(255) NOT NULL,

    -- Digest parameters
    audience VARCHAR(100) NOT NULL,
    from_date DATE,
    to_date DATE,
    max_candidates INTEGER DEFAULT 6,

    -- Execution details
    status VARCHAR(50) DEFAULT 'scheduled', -- 'scheduled', 'processing', 'sent', 'failed'
    cards_generated INTEGER DEFAULT 0,
    total_candidates INTEGER DEFAULT 0,
    execution_time_ms INTEGER,
    error_message TEXT,

    -- Email details
    email_subject VARCHAR(500),
    email_sent_at TIMESTAMP,
    email_message_id VARCHAR(255),

    -- Results
    digest_html TEXT,
    cards_metadata JSONB,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    CONSTRAINT fk_user_preferences
        FOREIGN KEY (user_id)
        REFERENCES teams_user_preferences(user_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_weekly_digest_deliveries_delivery_id ON weekly_digest_deliveries(delivery_id);
CREATE INDEX IF NOT EXISTS idx_weekly_digest_deliveries_user_id ON weekly_digest_deliveries(user_id);
CREATE INDEX IF NOT EXISTS idx_weekly_digest_deliveries_status ON weekly_digest_deliveries(status);
CREATE INDEX IF NOT EXISTS idx_weekly_digest_deliveries_created_at ON weekly_digest_deliveries(created_at DESC);

COMMENT ON TABLE weekly_digest_deliveries IS 'Track automated weekly digest email deliveries';
COMMENT ON COLUMN weekly_digest_deliveries.delivery_email IS 'Email address where digest was sent';
COMMENT ON COLUMN weekly_digest_deliveries.email_message_id IS 'SMTP message ID for tracking bounces';


-- ============================================
-- 3. Create subscription_confirmations table
-- ============================================

CREATE TABLE IF NOT EXISTS subscription_confirmations (
    id SERIAL PRIMARY KEY,
    confirmation_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL,
    user_email VARCHAR(255),
    delivery_email VARCHAR(255) NOT NULL,

    -- Subscription details
    action VARCHAR(50) NOT NULL, -- 'subscribe', 'unsubscribe', 'update'
    previous_settings JSONB,
    new_settings JSONB,

    -- Confirmation details
    confirmation_sent BOOLEAN DEFAULT FALSE,
    confirmation_sent_at TIMESTAMP,
    confirmation_email_subject VARCHAR(500),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_user_preferences_confirm
        FOREIGN KEY (user_id)
        REFERENCES teams_user_preferences(user_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_subscription_confirmations_user_id ON subscription_confirmations(user_id);
CREATE INDEX IF NOT EXISTS idx_subscription_confirmations_confirmation_id ON subscription_confirmations(confirmation_id);
CREATE INDEX IF NOT EXISTS idx_subscription_confirmations_created_at ON subscription_confirmations(created_at DESC);

COMMENT ON TABLE subscription_confirmations IS 'Track subscription change confirmations sent to users';


-- ============================================
-- 4. Function to calculate next digest delivery time
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

COMMENT ON FUNCTION calculate_next_digest_time IS 'Calculate next scheduled digest delivery time based on frequency';


-- ============================================
-- 5. Trigger to auto-update next_digest_scheduled_at
-- ============================================

CREATE OR REPLACE FUNCTION update_next_digest_scheduled()
RETURNS TRIGGER AS $$
BEGIN
    -- Only update if subscription is active
    IF NEW.subscription_active = TRUE THEN
        NEW.next_digest_scheduled_at := calculate_next_digest_time(
            NEW.digest_frequency,
            NEW.timezone
        );
    ELSE
        NEW.next_digest_scheduled_at := NULL;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create separate triggers for INSERT and UPDATE to avoid OLD value reference in INSERT
DROP TRIGGER IF EXISTS teams_user_preferences_schedule_digest_insert ON teams_user_preferences;
CREATE TRIGGER teams_user_preferences_schedule_digest_insert
    BEFORE INSERT ON teams_user_preferences
    FOR EACH ROW
    WHEN (NEW.subscription_active = TRUE)
    EXECUTE FUNCTION update_next_digest_scheduled();

DROP TRIGGER IF EXISTS teams_user_preferences_schedule_digest_update ON teams_user_preferences;
CREATE TRIGGER teams_user_preferences_schedule_digest_update
    BEFORE UPDATE ON teams_user_preferences
    FOR EACH ROW
    WHEN (NEW.subscription_active = TRUE AND (NEW.subscription_active <> OLD.subscription_active OR NEW.digest_frequency IS DISTINCT FROM OLD.digest_frequency))
    EXECUTE FUNCTION update_next_digest_scheduled();

COMMENT ON FUNCTION update_next_digest_scheduled IS 'Auto-calculate next digest delivery when subscription is activated or frequency changes';


-- ============================================
-- 6. View: Active subscriptions ready for delivery
-- ============================================

CREATE OR REPLACE VIEW active_digest_subscriptions AS
SELECT
    u.user_id,
    u.user_email,
    u.user_name,
    u.delivery_email,
    u.default_audience,
    u.digest_frequency,
    u.max_candidates_per_digest,
    u.timezone,
    u.last_digest_sent_at,
    u.next_digest_scheduled_at,
    COUNT(d.id) as total_deliveries_sent,
    MAX(d.email_sent_at) as last_email_sent_at
FROM teams_user_preferences u
LEFT JOIN weekly_digest_deliveries d ON u.user_id = d.user_id AND d.status = 'sent'
WHERE u.subscription_active = TRUE
  AND u.delivery_email IS NOT NULL
GROUP BY u.user_id, u.user_email, u.user_name, u.delivery_email,
         u.default_audience, u.digest_frequency, u.max_candidates_per_digest,
         u.timezone, u.last_digest_sent_at, u.next_digest_scheduled_at;

COMMENT ON VIEW active_digest_subscriptions IS 'Active subscriptions with delivery stats';


-- ============================================
-- 7. View: Subscriptions due for delivery
-- ============================================

CREATE OR REPLACE VIEW subscriptions_due_for_delivery AS
SELECT
    s.*
FROM active_digest_subscriptions s
WHERE s.next_digest_scheduled_at <= NOW()
ORDER BY s.next_digest_scheduled_at ASC;

COMMENT ON VIEW subscriptions_due_for_delivery IS 'Subscriptions that should receive digest delivery now';


-- ============================================
-- Verification Queries
-- ============================================

-- Check new columns
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'teams_user_preferences'
  AND column_name IN ('delivery_email', 'max_candidates_per_digest', 'subscription_active', 'last_digest_sent_at', 'next_digest_scheduled_at')
ORDER BY ordinal_position;

-- Check new tables
SELECT tablename FROM pg_tables
WHERE tablename IN ('weekly_digest_deliveries', 'subscription_confirmations')
ORDER BY tablename;

-- Check new views
SELECT viewname FROM pg_views
WHERE viewname IN ('active_digest_subscriptions', 'subscriptions_due_for_delivery')
ORDER BY viewname;
