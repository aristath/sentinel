// Package work implements the work processor system with event-driven job scheduling.
//
// # Work Type Architecture
//
// The work processor executes background jobs based on:
//   - Event triggers (dependencies between work types)
//   - Market timing (only during open hours, only after close, only when all closed, or anytime)
//   - Intervals (time between executions)
//
// # Interval Design Philosophy
//
// Work type intervals are **operationally optimized** and hardcoded for production reliability:
//
//   - sync:portfolio: 5 minutes - Balance between data freshness and API load during market hours
//   - sync:rates: 1 hour - Exchange rates change slowly, hourly updates sufficient
//   - maintenance:*: 24 hours - Daily maintenance (backups, vacuum, health checks) is standard practice
//   - maintenance:cleanup:recommendations: 1 hour - Frequent GC prevents table bloat
//   - security:sync: 24 hours - Daily history updates match data provider refresh schedule
//   - security:technical: 24 hours - Daily technical indicator calculation captures market changes
//   - security:formula: 30 days - Formula discovery is computationally expensive, monthly is optimal
//   - security:tags: 7 days - Weekly tag updates capture trends without churn
//   - security:metadata: 24 hours - Daily metadata keeps geography/industry current
//   - trading:retry: 1 hour - Hourly retry balances responsiveness vs broker rate limiting
//   - analysis:market-regime: 24 hours - Daily regime analysis captures trends without noise
//
// # Configurable Intervals
//
// Only deployment:check uses a configurable interval (job_auto_deploy_minutes setting) because:
//   - Deployment checks don't impact market operations
//   - Optimal frequency depends on CI/CD pipeline, not market data
//   - Users may want faster checks in development (2 min) or slower in production (30 min)
//
// All other intervals are hardcoded to prevent misconfiguration that could:
//   - Overwhelm broker APIs (too frequent sync)
//   - Miss market opportunities (too infrequent sync)
//   - Waste compute resources (too frequent formula discovery)
//   - Skip critical maintenance (too infrequent backups)
//
// # Market Timing
//
// Work types use MarketTiming to pause/resume based on market hours:
//   - DuringMarketOpen: Runs only when markets are open (sync:portfolio)
//   - AfterMarketClose: Runs after markets close (security:sync, security:technical)
//   - AllMarketsClosed: Runs only when all markets are closed (maintenance tasks)
//   - AnyTime: Runs regardless of market hours (sync:rates, deployment:check)
//
// This reduces API load during off-hours while ensuring critical operations run during active trading.
package work
