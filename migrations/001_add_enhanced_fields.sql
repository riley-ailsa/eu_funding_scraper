-- Migration: Add enhanced metadata fields
-- Run this after the initial schema.sql

-- Add new fields to grants table
ALTER TABLE grants
    ADD COLUMN IF NOT EXISTS eu_identifier VARCHAR(255),     -- Official EU identifier
    ADD COLUMN IF NOT EXISTS call_title TEXT,                -- Full call title
    ADD COLUMN IF NOT EXISTS duration VARCHAR(200),          -- Project duration
    ADD COLUMN IF NOT EXISTS deadline_model VARCHAR(50),     -- 'single-stage' or 'multiple cut-off'
    ADD COLUMN IF NOT EXISTS further_information TEXT,       -- Additional details
    ADD COLUMN IF NOT EXISTS application_info TEXT;          -- How to apply

-- Create indexes for new searchable fields
CREATE INDEX IF NOT EXISTS idx_grants_eu_identifier ON grants(eu_identifier);
CREATE INDEX IF NOT EXISTS idx_grants_deadline_model ON grants(deadline_model);

-- Add comment for documentation
COMMENT ON COLUMN grants.eu_identifier IS 'Official EU identifier, e.g., HORIZON-CL5-2023-D4-01-01';
COMMENT ON COLUMN grants.deadline_model IS 'single-stage or multiple cut-off';
COMMENT ON COLUMN grants.duration IS 'Project duration as text, e.g., "18 months" or "1-3 years"';
