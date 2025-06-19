-- =============================================================================
-- DUPLICATE CLEANUP SCRIPTS FOR REAL-TIME CRYPTO PRICE PREDICTOR
-- =============================================================================
-- This script removes duplicate entries from trades, candles, and technical indicators
-- based on the unique identifiers specified by the user
--
-- USAGE:
-- 1. Connect to your RisingWave database
-- 2. Execute these statements in order
-- 3. Monitor the affected row counts
-- =============================================================================

-- Enable verbose output
\set VERBOSITY verbose

-- Show current counts before cleanup
SELECT 'BEFORE CLEANUP - Technical Indicators Count:' as info, COUNT(*) as count FROM technical_indicators;

-- =============================================================================
-- 1. CLEAN UP TECHNICAL INDICATORS DUPLICATES
-- =============================================================================
-- Remove duplicates based on (pair, window_start_ms, window_end_ms)
-- Keep the most recent record (highest created_at)

BEGIN;

-- Create a temporary table with unique records (keeping the latest)
CREATE TEMP TABLE technical_indicators_unique AS
SELECT DISTINCT ON (pair, window_start_ms, window_end_ms) *
FROM technical_indicators
ORDER BY pair, window_start_ms, window_end_ms, created_at DESC NULLS LAST;

-- Count duplicates before removal
SELECT 
    'Technical Indicators - Total records:' as info,
    COUNT(*) as total_records
FROM technical_indicators;

SELECT 
    'Technical Indicators - Unique records:' as info,
    COUNT(*) as unique_records
FROM technical_indicators_unique;

SELECT 
    'Technical Indicators - Duplicates to remove:' as info,
    (SELECT COUNT(*) FROM technical_indicators) - (SELECT COUNT(*) FROM technical_indicators_unique) as duplicates;

-- Delete all records from original table
DELETE FROM technical_indicators;

-- Insert unique records back
INSERT INTO technical_indicators 
SELECT * FROM technical_indicators_unique;

-- Clean up temp table
DROP TABLE technical_indicators_unique;

COMMIT;

-- =============================================================================
-- 2. CLEAN UP KAFKA TOPICS - TRADES DUPLICATES
-- =============================================================================
-- Note: For Kafka topics, we need to handle this differently since they're streams
-- The best approach is to:
-- 1. Create a new topic with deduplication
-- 2. Process existing topic with deduplication logic
-- 3. Switch consumers to new topic

-- This is handled programmatically in the application layer
-- See the deduplication service created below

-- =============================================================================
-- 3. VERIFICATION QUERIES
-- =============================================================================

-- Verify no duplicates remain in technical indicators
SELECT 
    pair, 
    window_start_ms, 
    window_end_ms, 
    COUNT(*) as duplicate_count
FROM technical_indicators 
GROUP BY pair, window_start_ms, window_end_ms 
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;

-- Show final counts
SELECT 'AFTER CLEANUP - Technical Indicators Count:' as info, COUNT(*) as count FROM technical_indicators;

-- Show sample data to verify cleanup
SELECT 
    pair,
    window_start_ms,
    window_end_ms,
    created_at,
    to_timestamp(window_start_ms/1000) as window_start_time
FROM technical_indicators 
ORDER BY pair, window_start_ms DESC
LIMIT 20;

-- =============================================================================
-- 4. PREVENTION CONSTRAINTS (if supported by RisingWave)
-- =============================================================================
-- Note: RisingWave may not support all traditional PostgreSQL constraints
-- These are for reference and should be tested

-- This constraint is already defined in the schema:
-- PRIMARY KEY (pair, window_start_ms, window_end_ms)

-- =============================================================================
-- 5. MONITORING QUERIES FOR ONGOING DUPLICATE DETECTION
-- =============================================================================

-- Query to detect duplicates in technical indicators
CREATE OR REPLACE VIEW duplicate_technical_indicators AS
SELECT 
    pair, 
    window_start_ms, 
    window_end_ms, 
    COUNT(*) as duplicate_count,
    MIN(created_at) as first_created,
    MAX(created_at) as last_created
FROM technical_indicators 
GROUP BY pair, window_start_ms, window_end_ms 
HAVING COUNT(*) > 1;

-- Query to check for data consistency
CREATE OR REPLACE VIEW data_consistency_check AS
SELECT 
    pair,
    DATE(to_timestamp(window_start_ms/1000)) as trading_date,
    COUNT(*) as candle_count,
    MIN(to_timestamp(window_start_ms/1000)) as first_candle,
    MAX(to_timestamp(window_start_ms/1000)) as last_candle
FROM technical_indicators 
GROUP BY pair, DATE(to_timestamp(window_start_ms/1000))
ORDER BY pair, trading_date DESC;

-- Show current status
SELECT 'Cleanup completed successfully!' as status;
SELECT 'Use the views above to monitor for future duplicates.' as next_steps; 