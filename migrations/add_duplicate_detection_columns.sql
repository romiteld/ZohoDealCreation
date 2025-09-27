-- Add columns for enhanced duplicate detection
ALTER TABLE deals ADD COLUMN IF NOT EXISTS candidate_name VARCHAR(255);
ALTER TABLE deals ADD COLUMN IF NOT EXISTS company_name VARCHAR(255);
ALTER TABLE deals ADD COLUMN IF NOT EXISTS email VARCHAR(255);
ALTER TABLE deals ADD COLUMN IF NOT EXISTS job_title VARCHAR(255);
ALTER TABLE deals ADD COLUMN IF NOT EXISTS zoho_deal_id VARCHAR(255);
ALTER TABLE deals ADD COLUMN IF NOT EXISTS zoho_contact_id VARCHAR(255);
ALTER TABLE deals ADD COLUMN IF NOT EXISTS zoho_account_id VARCHAR(255);

-- Create indexes for faster duplicate detection
CREATE INDEX IF NOT EXISTS idx_deals_candidate_name ON deals(candidate_name);
CREATE INDEX IF NOT EXISTS idx_deals_company_name ON deals(company_name);
CREATE INDEX IF NOT EXISTS idx_deals_email ON deals(email);
CREATE INDEX IF NOT EXISTS idx_deals_created_at ON deals(created_at);

-- Create composite index for duplicate checks
CREATE INDEX IF NOT EXISTS idx_deals_duplicate_check ON deals(candidate_name, company_name, created_at DESC);