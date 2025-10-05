-- Migration: Add Apollo location cache table
-- Description: Store Apollo.io location and website extraction results for caching
-- Date: 2025-01-16

-- Create table for Apollo location cache
CREATE TABLE IF NOT EXISTS apollo_location_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(255) UNIQUE NOT NULL,
    location_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Indexes for performance
    INDEX idx_apollo_location_cache_key (cache_key),
    INDEX idx_apollo_location_created (created_at)
);

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_apollo_location_cache_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_apollo_location_cache_timestamp
    BEFORE UPDATE ON apollo_location_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_apollo_location_cache_updated_at();

-- Add comment on table
COMMENT ON TABLE apollo_location_cache IS 'Cache for Apollo.io location and website extraction results';
COMMENT ON COLUMN apollo_location_cache.cache_key IS 'Unique key for caching (format: apollo_location_{type}_{identifier})';
COMMENT ON COLUMN apollo_location_cache.location_data IS 'Complete location and website data in JSON format';

-- Grant permissions (adjust as needed)
GRANT SELECT, INSERT, UPDATE, DELETE ON apollo_location_cache TO PUBLIC;