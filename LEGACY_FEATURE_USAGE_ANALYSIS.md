# Legacy Feature Usage Analysis (Commit 96e48793)

**Date:** 2026-01-03
**Commit:** 96e48793dbfa6b59909ce636aeb9bd3cdb81585e

## Summary

This document analyzes how non-migrated features were actually used in the legacy Python application at the specified commit.

## 1. Portfolio Reconstruction Functions

### Usage: **ACTIVELY USED** ✅

**Files:**
- `app/modules/analytics/domain/reconstruction/values.py` - Main function
- `app/modules/analytics/domain/reconstruction/positions.py` - Position reconstruction
- `app/modules/analytics/domain/reconstruction/cash.py` - Cash reconstruction

**Where Used:**
- **`app/modules/portfolio/api/portfolio.py`** - `get_portfolio_analytics()` function
  - Called `reconstruct_portfolio_values()` to rebuild historical portfolio values from trades
  - Used for calculating portfolio analytics over time periods (default 365 days)
  - Reconstructed daily portfolio values from:
    1. Historical positions (from trades)
    2. Historical prices (from history databases)
    3. Historical cash balances (from cash flows)

**Code Flow:**
```python
async def get_portfolio_analytics(days: int = 365):
    # Reconstruct portfolio history
    portfolio_values = await reconstruct_portfolio_values(
        start_date_str, end_date_str
    )

    # Calculate returns from reconstructed values
    returns = calculate_portfolio_returns(portfolio_values)

    # Get metrics and attribution
    metrics = await get_portfolio_metrics(returns)
    attribution = await get_performance_attribution(...)
```

**Purpose:**
- Rebuild historical portfolio snapshots from raw trade data
- Used for performance analytics over arbitrary time periods
- Calculates daily portfolio values by:
  - Reconstructing position quantities from trades
  - Looking up historical prices
  - Tracking cash balance changes

**Go Implementation Status:**
- **Migration Strategy:** Uses `portfolio_snapshots` table instead
- The Go implementation uses pre-calculated portfolio snapshots stored in `snapshots.db`
- In `trader/internal/modules/portfolio/service.go` - `GetAnalytics()`:
  - Uses `portfolioRepo.GetRange()` to get pre-stored snapshots
  - Does NOT reconstruct from trades (relies on snapshots being created elsewhere)

**Impact:**
- ✅ **Functional replacement exists** - Portfolio snapshots serve the same purpose
- ⚠️ **Different approach** - Pre-calculated snapshots vs. on-demand reconstruction
- ⚠️ **Snapshot dependency** - Requires snapshots to be maintained/created

**Recommendation:**
- Portfolio snapshots in Go are equivalent functionality
- Reconstruction functions were a "rebuild from source" approach
- Current Go approach is more efficient (pre-calculated) but requires snapshot maintenance
- **Status:** ✅ No migration needed - functionality replaced by snapshots

## 2. Factor Attribution

### Usage: **EXPORTED BUT NOT USED** ❌

**Files:**
- `app/modules/analytics/domain/attribution/factors.py`

**Where Exported:**
- Exported in `app/modules/analytics/domain/__init__.py`
- Exported in `app/modules/analytics/domain/portfolio_analytics.py`
- **BUT:** Never actually imported or called in any API endpoint or service

**Search Results:**
- Found only in test files (`test_attribution_factors.py`)
- NOT found in:
  - `app/modules/portfolio/api/portfolio.py` (portfolio analytics endpoint)
  - `app/jobs/event_based_trading.py` (trading loop)
  - `app/main.py` (main application)
  - Any other API endpoints or services

**Purpose:**
- Would calculate weighted factor contributions (country/industry averages)
- Wrapper around `get_performance_attribution()` with additional averaging logic

**Go Implementation Status:**
- **Missing** - Not found in Go codebase
- Performance attribution exists, but factor attribution (averaging) does not

**Impact:**
- ❌ **Unused feature** - Was exported but never actually used in production
- ⚠️ **Low priority** - May have been planned but never implemented in UI
- The performance attribution it depends on IS migrated

**Recommendation:**
- **Status:** ❌ **Safe to delete** - Was never actually used
- Can be re-implemented later if needed (simple averaging of performance attribution results)

## 3. Deployment Automation

### Usage: **ACTIVELY USED** ✅

**Files:**
- `app/infrastructure/deployment/deployment_manager.py`
- `app/infrastructure/deployment/file_deployer.py`
- `app/infrastructure/deployment/git_checker.py`
- `app/infrastructure/deployment/service_manager.py`
- `app/infrastructure/deployment/sketch_deployer.py`

**Where Used:**

1. **`app/jobs/auto_deploy.py`** - Scheduled deployment job
   - Called `DeploymentManager.deploy()` to:
     - Check for Git updates
     - Pull changes if available
     - Deploy files to staging
     - Swap staging to production (atomic)
     - Restart systemd service
     - Compile and upload Arduino sketch if changed
   - Used file locking to prevent concurrent deployments

2. **`app/modules/system/api/status.py`** - Status endpoint
   - Called `DeploymentManager.get_deployment_status()` to show:
     - Current deployment status
     - Git commit info
     - Pending changes
     - Service status

**Code Flow:**
```python
# In auto_deploy.py
manager = DeploymentManager(
    repo_dir=REPO_DIR,
    deploy_dir=DEPLOY_DIR,
    staging_dir=STAGING_DIR,
    venv_dir=VENV_DIR,
    service_name=SERVICE_NAME,
)
result = await manager.deploy()
```

**Purpose:**
- Automatic deployment from Git repository
- Atomic deployment with staging directory
- Service restart and health checks
- Arduino sketch compilation and upload

**Go Implementation Status:**
- **Intentionally NOT implemented** - For safety reasons
- Go version (`trader/internal/deployment/manager.go`) only tracks status
- Code explicitly states: "For safety, do not implement automatic deployment in production"

**Impact:**
- ✅ **Intentional design decision** - Deployment automation omitted for safety
- ✅ **External CI/CD** - Should use external systems (GitHub Actions, etc.)
- ⚠️ **Manual deployment** - Requires manual deployment process

**Recommendation:**
- **Status:** ✅ **Intentionally different** - Keep Python files as reference
- Document the design decision
- Use external CI/CD pipelines for automated deployment

## Summary Table

| Feature | Usage | Migration Status | Recommendation |
|---------|-------|------------------|----------------|
| **Portfolio Reconstruction** | ✅ Used in portfolio analytics API | ✅ Replaced by snapshots | No action needed |
| **Factor Attribution** | ❌ Exported but never used | ❌ Missing (not needed) | Safe to delete |
| **Deployment Automation** | ✅ Used in auto_deploy job | ✅ Intentionally omitted | Keep as reference |

## Conclusion

1. **Portfolio Reconstruction**: ✅ Fully replaced by portfolio snapshots approach
2. **Factor Attribution**: ❌ Was never actually used - safe to delete
3. **Deployment Automation**: ✅ Intentionally different - documented design decision

## Action Items

1. ✅ **Portfolio Reconstruction** - No action needed (functionality replaced)
2. ✅ **Factor Attribution** - Safe to delete (unused feature)
3. ✅ **Deployment Automation** - Keep for reference (intentional design)
