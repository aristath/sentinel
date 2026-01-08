-- Data Integrity Verification Script for Sentinel
-- Run this script periodically to verify database integrity
-- Usage: sqlite3 <database_file> < verify_data_integrity.sql

-- ==============================================================================
-- LEDGER DATABASE VERIFICATION (ledger.db)
-- ==============================================================================

.print "=========================================="
.print "LEDGER DATABASE INTEGRITY VERIFICATION"
.print "=========================================="
.print ""

-- Check for orphaned dividend records (should be 0 after FK constraint is added)
.print "1. Checking for orphaned dividend records..."
SELECT
    COUNT(*) as orphaned_dividends,
    CASE
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'FAIL - ' || COUNT(*) || ' orphaned records found'
    END as status
FROM dividend_history dh
LEFT JOIN cash_flows cf ON dh.cash_flow_id = cf.id
WHERE dh.cash_flow_id IS NOT NULL
  AND cf.id IS NULL;

.print ""

-- Check for negative cash flow amounts (should be investigated)
.print "2. Checking for suspicious cash flow amounts..."
SELECT
    COUNT(*) as negative_deposits,
    CASE
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'WARNING - ' || COUNT(*) || ' deposits with negative amounts'
    END as status
FROM cash_flows
WHERE LOWER(transaction_type) LIKE '%deposit%'
  AND amount_eur < 0;

.print ""

-- Check EUR currency conversion consistency
.print "3. Checking EUR currency conversion consistency..."
SELECT
    COUNT(*) as mismatched_eur_conversions,
    CASE
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'FAIL - ' || COUNT(*) || ' EUR flows with amount != amount_eur'
    END as status
FROM cash_flows
WHERE currency = 'EUR'
  AND ABS(amount - amount_eur) > 0.01;

.print ""

-- Check for trades without corresponding cash flows (informational)
.print "4. Summary of trades by type..."
SELECT
    side,
    COUNT(*) as trade_count,
    ROUND(SUM(price * quantity), 2) as total_value_original_currency
FROM trades
GROUP BY side;

.print ""

-- ==============================================================================
-- PORTFOLIO DATABASE VERIFICATION (portfolio.db)
-- ==============================================================================

.print "=========================================="
.print "PORTFOLIO DATABASE INTEGRITY VERIFICATION"
.print "=========================================="
.print ""

-- Check for orphaned kelly_sizes (should be 0 after FK constraint is added)
.print "5. Checking for orphaned kelly_sizes records..."
SELECT
    COUNT(*) as orphaned_kelly_sizes,
    CASE
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'FAIL - ' || COUNT(*) || ' orphaned kelly_sizes found'
    END as status
FROM kelly_sizes ks
LEFT JOIN scores s ON ks.isin = s.isin
WHERE s.isin IS NULL;

.print ""

-- Check for positions with invalid quantities
.print "6. Checking for invalid positions..."
SELECT
    COUNT(*) as invalid_positions,
    CASE
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'FAIL - ' || COUNT(*) || ' positions with quantity <= 0'
    END as status
FROM positions
WHERE quantity <= 0;

.print ""

-- Check for negative position values
.print "7. Checking for negative position values..."
SELECT
    COUNT(*) as negative_values,
    CASE
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'WARNING - ' || COUNT(*) || ' positions with negative market value'
    END as status
FROM positions
WHERE market_value_eur < 0;

.print ""

-- Check for positions without scores (informational)
.print "8. Positions without scores (may be normal)..."
SELECT
    COUNT(p.isin) as positions_without_scores
FROM positions p
LEFT JOIN scores s ON p.isin = s.isin
WHERE s.isin IS NULL;

.print ""

-- Verify cash balances are reasonable
.print "9. Checking cash balances..."
SELECT
    currency,
    balance,
    CASE
        WHEN balance < -1000 THEN 'FAIL - Large negative balance'
        WHEN balance < 0 THEN 'WARNING - Negative balance'
        ELSE 'PASS'
    END as status
FROM cash_balances
ORDER BY balance ASC;

.print ""

-- ==============================================================================
-- UNIVERSE DATABASE VERIFICATION (universe.db)
-- ==============================================================================

.print "=========================================="
.print "UNIVERSE DATABASE INTEGRITY VERIFICATION"
.print "=========================================="
.print ""

-- Check for securities without ISIN
.print "10. Checking for securities without ISIN..."
SELECT
    COUNT(*) as securities_without_isin,
    CASE
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'FAIL - ' || COUNT(*) || ' securities missing ISIN'
    END as status
FROM securities
WHERE isin IS NULL OR isin = '';

.print ""

-- Check for duplicate ISINs (should be impossible with PK, but verify)
.print "11. Checking for duplicate ISINs..."
SELECT
    isin,
    COUNT(*) as count
FROM securities
GROUP BY isin
HAVING COUNT(*) > 1;

SELECT
    CASE
        WHEN COUNT(*) = 0 THEN 'PASS - No duplicates'
        ELSE 'FAIL - ' || COUNT(*) || ' duplicate ISINs found'
    END as status
FROM (
    SELECT isin
    FROM securities
    GROUP BY isin
    HAVING COUNT(*) > 1
);

.print ""

-- Check for stale price data (prices older than 7 days)
.print "12. Checking for stale price data..."
SELECT
    COUNT(*) as securities_with_stale_prices,
    CASE
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'WARNING - ' || COUNT(*) || ' securities with prices older than 7 days'
    END as status
FROM securities
WHERE price IS NOT NULL
  AND price_updated_at < strftime('%s', 'now', '-7 days');

.print ""

-- ==============================================================================
-- CROSS-DATABASE VERIFICATION
-- ==============================================================================

.print "=========================================="
.print "CROSS-DATABASE INTEGRITY CHECKS"
.print "=========================================="
.print ""

.print "NOTE: Cross-database checks require ATTACH DATABASE statements."
.print "Run the following manually with appropriate paths:"
.print ""
.print "-- Check for positions referencing non-existent securities:"
.print "ATTACH DATABASE '/path/to/universe.db' AS universe;"
.print "SELECT COUNT(*) as orphaned_positions"
.print "FROM main.positions p"
.print "LEFT JOIN universe.securities s ON p.isin = s.isin"
.print "WHERE s.isin IS NULL;"
.print "DETACH DATABASE universe;"
.print ""
.print "-- Check for scores referencing non-existent securities:"
.print "ATTACH DATABASE '/path/to/universe.db' AS universe;"
.print "SELECT COUNT(*) as orphaned_scores"
.print "FROM main.scores sc"
.print "LEFT JOIN universe.securities s ON sc.isin = s.isin"
.print "WHERE s.isin IS NULL;"
.print "DETACH DATABASE universe;"
.print ""

-- ==============================================================================
-- SUMMARY
-- ==============================================================================

.print "=========================================="
.print "VERIFICATION COMPLETE"
.print "=========================================="
.print ""
.print "Review all checks above. Any FAIL status indicates data integrity issues."
.print "WARNING status indicates potential issues that should be investigated."
.print ""
.print "For detailed investigation of any failures, query the specific tables"
.print "to identify problematic records."
.print ""
