-- Initialize PostgreSQL extensions for Mille Bornes
-- This script runs on first database creation

-- Enable UUID extension for primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgcrypto for cryptographic functions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Enable citext for case-insensitive text
CREATE EXTENSION IF NOT EXISTS "citext";

-- Set timezone
SET TIMEZONE = 'UTC';

-- Create indexes for better performance on common queries
-- These will be created by Django migrations, but we can add hints here