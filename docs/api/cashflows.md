# Cash Flows

Base path: `/api/cashflows`

---

## `GET /api/cashflows`

Returns an aggregated cash flow summary converted to EUR.

**Response**
```json
{
  "deposits": 40000.00,
  "withdrawals": 0.00,
  "dividends": 320.50,
  "taxes": 48.10,
  "fees": 86.00,
  "net_deposits": 40000.00,
  "total_profit": 4413.90
}
```

| Field | Description |
|---|---|
| `deposits` | Total card deposits in EUR |
| `withdrawals` | Total withdrawals in EUR (positive number) |
| `dividends` | Total dividends received in EUR |
| `taxes` | Total taxes paid in EUR (positive number) |
| `fees` | Total trading fees paid in EUR (positive number) |
| `net_deposits` | `deposits - withdrawals` |
| `total_profit` | Current portfolio value minus net deposits. Dividends and fees are already reflected in the portfolio value/cash balance. |

---

## `POST /api/cashflows/sync`

Triggers a manual sync of cash flows from the broker (`sync:cashflows` job).

**Response**
```json
{ "status": "ok", "job_type": "sync:cashflows" }
```
