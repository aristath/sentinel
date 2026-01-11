# Sentinel REST API Reference

Complete reference documentation for the Sentinel REST API.

## Base URL

All API endpoints are prefixed with `/api` unless otherwise noted. The base URL is typically `http://localhost:8001` (configurable via `GO_PORT` environment variable).

## Authentication

Currently, the API does not require authentication for local access. All endpoints are accessible without authentication headers.

## Response Format

All responses are JSON unless otherwise specified.

**Success Response Format:**
- Successful responses return data directly (structure varies by endpoint)
- Status codes: `200 OK`, `201 Created`, `204 No Content`

**Error Response Format:**
```json
{
  "error": "Error message description"
}
```
- Status codes: `400 Bad Request`, `403 Forbidden`, `404 Not Found`, `500 Internal Server Error`

## API Endpoints by Category

- [System](system/) - Health checks, status monitoring, logs, job management
- [Portfolio](portfolio/) - Positions, performance, allocation, analytics
- [Trading](trading/) - Trade execution, validation, recommendations
- [Planning](planning/) - Trade plan generation, configuration management
- [Allocation](allocation/) - Target allocation management, rebalancing
- [Securities](securities/) - Universe management, security data
- [Dividends](dividends/) - Dividend tracking, reinvestment
- [Analytics](analytics/) - Performance metrics, risk analysis
- [Charts](charts/) - Historical data visualization
- [Settings](settings/) - Configuration management
- [Cash Flows](cash-flows/) - Cash flow tracking and management
- [Display](display/) - LED display management
- [Scoring](scoring/) - Security scoring
- [Optimization](optimization/) - Portfolio optimization
- [Historical Data](historical/) - Historical price and rate data
- [Risk Metrics](risk/) - Risk analysis and metrics
- [Market Hours](market-hours/) - Market hours and holidays
- [Adaptation](adaptation/) - Market regime detection
- [Opportunities](opportunities/) - Trading opportunity identification
- [Ledger](ledger/) - Transaction history and audit trail
- [Snapshots](snapshots/) - Portfolio snapshots
- [Sequences](sequences/) - Trade sequence generation
- [Rebalancing](rebalancing/) - Rebalancing calculations
- [Currency](currency/) - Currency conversion and exchange rates
- [Quantum](quantum/) - Quantum probability models
- [Symbolic Regression](symbolic-regression/) - Formula discovery
- [Backups](backups/) - Cloud backup management (R2)
- [Deployment](deployment/) - Deployment and update management
- [Evaluation](evaluation/) - Sequence evaluation and simulation

## Notes

- All endpoints return JSON unless otherwise specified
- Error responses follow the format: `{"error": "message"}`
- Some endpoints support query parameters for filtering/pagination
- SSE (Server-Sent Events) endpoints stream data in real-time
- Job trigger endpoints are idempotent and can be called multiple times
- Timestamps are returned in ISO 8601 format (RFC3339)
- Currency values are typically in EUR unless specified otherwise
- All monetary values use float64 precision

---

*This documentation is automatically generated from handler implementations. For the most up-to-date information, refer to the source code in `internal/modules/*/handlers/`.*
