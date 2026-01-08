# Database Constraints Documentation

This document describes critical database constraints that enforce data integrity in Sentinel.

## Overview

The Sentinel application uses a 7-database architecture with SQLite. Foreign key constraints are **critical** for maintaining data integrity, especially in the immutable ledger database.

## Critical Foreign Key Constraints

### Ledger Database (ledger.db)

The ledger database contains the **immutable audit trail** for all financial transactions. Data integrity is paramount.

#### 1. dividend_history → cash_flows

**Constraint:**
```sql
FOREIGN KEY (cash_flow_id) REFERENCES cash_flows(id) ON DELETE CASCADE
```

**Purpose:** Ensures every dividend record references a valid cash flow entry.

**Impact:**
- Prevents orphaned dividend records when cash flows are deleted
- Maintains audit trail consistency
- Critical for tax reporting and performance calculations

**Added:** 2026-01-08 (Bug fix session)

**Why it matters:** The dividend history tracks real money received. If a cash flow is deleted but dividend records remain, the ledger becomes inconsistent and financial reports will be inaccurate.

---

### Portfolio Database (portfolio.db)

The portfolio database contains current positions, scores, and optimization data.

#### 2. kelly_sizes → scores

**Constraint:**
```sql
FOREIGN KEY (isin) REFERENCES scores(isin) ON DELETE CASCADE
```

**Purpose:** Ensures Kelly fraction calculations reference securities with valid scores.

**Impact:**
- Prevents stale position sizing data
- Ensures portfolio optimization uses current data
- Prevents calculation errors from missing score data

**Added:** 2026-01-08 (Bug fix session)

**Note:** The original constraint existed but lacked `ON DELETE CASCADE`, which could leave orphaned kelly_sizes when scores were deleted.

**Why it matters:** Kelly sizing determines optimal position sizes for the portfolio. If kelly_sizes references a deleted security, position sizing calculations fail or produce incorrect results.

---

## Cross-Database Relationships (No FK Enforcement)

SQLite does not support foreign keys across different database files. The following relationships are enforced **at the application level only**:

### 1. portfolio.positions → universe.securities

**Relationship:** Every position must reference a valid security in the universe.

**Enforcement:**
- Application validates ISIN exists before creating positions
- Sync jobs check for orphaned positions
- See: `internal/modules/universe/security_repository.go:357-445`

**Known Issue:** Cross-database JOIN in `GetWithScores()` method reads from both databases without atomic guarantee. See CLAUDE.md for documented violation.

### 2. portfolio.kelly_sizes → universe.securities

**Relationship:** Kelly sizes should only exist for securities in the active universe.

**Enforcement:**
- Application ensures ISINs exist before calculating kelly fractions
- Cleanup jobs remove stale kelly_sizes for removed securities

### 3. ledger.trades → universe.securities

**Relationship:** Trades should reference valid securities (by symbol or ISIN).

**Current Status:** Uses **symbol** as primary identifier (not ISIN).

**Known Issue:** Symbol collisions across exchanges could cause data corruption. See plan item #11 for ISIN-based migration (HIGH RISK).

**Enforcement:**
- Application validates symbol exists before recording trades
- No automatic cleanup of trades for removed securities (immutable ledger)

---

## Data Integrity Validation

### Cash Flow Currency Validation

**Location:** `internal/modules/cash_flows/repository.go`

**Validation Rules:**
1. EUR amounts must match exactly (within €0.01 tolerance)
2. Exchange rates must be positive and within reasonable bounds (0.001 to 200)
3. Suspicious rates trigger warning logs

**Purpose:** Prevents currency conversion errors in the immutable ledger.

**Added:** 2026-01-08 (Bug fix session)

---

## Constraint Enforcement Checklist

When modifying database schemas, ensure:

- [ ] All foreign keys have `ON DELETE CASCADE` or `ON DELETE RESTRICT` specified
- [ ] Cross-database relationships are documented in this file
- [ ] Application-level validation exists for relationships without FK constraints
- [ ] Cleanup jobs handle orphaned records for cross-database relationships
- [ ] Migration scripts validate data before applying constraints

---

## Common Pitfalls

### 1. Missing ON DELETE Clause

**Problem:** Foreign keys without `ON DELETE` default to `RESTRICT`, which may block legitimate deletions.

**Solution:** Always specify `ON DELETE CASCADE` for dependent data or `ON DELETE RESTRICT` for critical references.

### 2. Adding Constraints to Existing Data

**Problem:** Adding FK constraints to tables with existing orphaned records will fail.

**Solution:**
1. Backup database
2. Query for orphaned records
3. Clean up or migrate orphaned data
4. Add constraint
5. Validate data integrity

### 3. Cross-Database Operations

**Problem:** SQLite doesn't enforce FKs across database files, and cross-database transactions aren't atomic.

**Solution:**
- Use application-level validation
- Implement two-phase read with version checking
- Document violations in CLAUDE.md
- Add cleanup jobs for orphaned records

---

## Verification Queries

### Check for Orphaned Dividend Records

```sql
-- Run against ledger.db
SELECT dh.*
FROM dividend_history dh
LEFT JOIN cash_flows cf ON dh.cash_flow_id = cf.id
WHERE dh.cash_flow_id IS NOT NULL
  AND cf.id IS NULL;
```

### Check for Orphaned Kelly Sizes

```sql
-- Run against portfolio.db
SELECT ks.*
FROM kelly_sizes ks
LEFT JOIN scores s ON ks.isin = s.isin
WHERE s.isin IS NULL;
```

### Check for Orphaned Positions

```sql
-- Requires cross-database query (attach universe.db)
ATTACH DATABASE '/path/to/universe.db' AS universe;

SELECT p.*
FROM main.positions p
LEFT JOIN universe.securities s ON p.isin = s.isin
WHERE s.isin IS NULL;

DETACH DATABASE universe;
```

---

## Schema Migration Notes

### Applying New Constraints

The schema files in `internal/database/schemas/` are the source of truth. Changes should be:

1. **Updated in schema file first**
2. **Applied to running database** (Arduino device or local)
3. **Tested with verification queries**
4. **Documented in this file**

**Note:** This codebase does NOT use migration files. Schema changes are applied directly.

### Rollback Plan

If a constraint causes issues:

1. **Identify affected records:** Use verification queries
2. **Drop constraint:** `ALTER TABLE table_name DROP CONSTRAINT constraint_name;` (SQLite requires recreating table)
3. **Fix data issues**
4. **Re-apply constraint** or document as known issue

---

## References

- Database schema files: `internal/database/schemas/*.sql`
- Schema verification: `internal/database/schemas/VERIFICATION_SUMMARY.md`
- Architecture violations: `CLAUDE.md` (root)
- Bug fix plan: `/Users/aristath/.claude/plans/frolicking-nibbling-graham.md`

---

**Last Updated:** 2026-01-08
**Maintainer:** See git history for contributors
