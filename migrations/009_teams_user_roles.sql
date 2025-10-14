-- Migration: Teams User Roles for Access Control
-- Description: Add role-based access control for Teams bot queries
-- Author: Claude
-- Date: 2025-10-11

-- ============================================
-- 1. Teams User Roles Table
-- ============================================
CREATE TABLE IF NOT EXISTS teams_user_roles (
    user_email VARCHAR(255) PRIMARY KEY,
    role VARCHAR(50) NOT NULL CHECK (role IN ('executive', 'recruiter', 'admin')),
    scoped_modules JSONB DEFAULT '{}',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_teams_user_roles_role ON teams_user_roles(role);

COMMENT ON TABLE teams_user_roles IS 'Role-based access control for Teams bot natural language queries';
COMMENT ON COLUMN teams_user_roles.role IS 'User role: executive (unscoped), recruiter (owner-filtered), admin (full access)';
COMMENT ON COLUMN teams_user_roles.scoped_modules IS 'Per-module access rules (future): {"deals": "owner_only", "vault_candidates": "all"}';
COMMENT ON COLUMN teams_user_roles.notes IS 'Optional notes about user permissions or special access requirements';

-- ============================================
-- 2. Pre-populate Executive Users
-- ============================================
INSERT INTO teams_user_roles (user_email, role, notes) VALUES
    ('steve@emailthewell.com', 'executive', 'Unscoped access to all CRM data'),
    ('brandon@emailthewell.com', 'executive', 'Unscoped access to all CRM data'),
    ('daniel.romitelli@emailthewell.com', 'executive', 'Unscoped access to all CRM data')
ON CONFLICT (user_email) DO NOTHING;

-- ============================================
-- 3. Trigger for updated_at
-- ============================================
DROP TRIGGER IF EXISTS teams_user_roles_updated_at ON teams_user_roles;
CREATE TRIGGER teams_user_roles_updated_at
    BEFORE UPDATE ON teams_user_roles
    FOR EACH ROW
    EXECUTE FUNCTION update_teams_updated_at();

-- ============================================
-- 4. Helper Function for Role Lookup
-- ============================================
CREATE OR REPLACE FUNCTION get_user_role(p_user_email VARCHAR)
RETURNS VARCHAR AS $$
DECLARE
    v_role VARCHAR;
BEGIN
    SELECT role INTO v_role
    FROM teams_user_roles
    WHERE LOWER(user_email) = LOWER(p_user_email);

    -- Default to 'recruiter' if no role found (most restrictive)
    RETURN COALESCE(v_role, 'recruiter');
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_user_role(VARCHAR) IS 'Lookup user role with fallback to recruiter (most restrictive)';

-- ============================================
-- 5. Verification Queries
-- ============================================
SELECT
    user_email,
    role,
    notes,
    created_at
FROM teams_user_roles
ORDER BY role, user_email;
