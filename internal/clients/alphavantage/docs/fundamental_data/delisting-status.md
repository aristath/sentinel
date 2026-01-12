# DELISTING_STATUS

List of delisted US stocks and ETFs.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns a list of delisted US stocks and ETFs, providing details such as delisting date and reason.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `DELISTING_STATUS` |
| `date` | string | No | Specific date in format `YYYY-MM-DD`. If not provided, returns all delisted securities |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "data": [
        {
            "symbol": "OLDCO",
            "name": "Old Company Inc.",
            "exchange": "NASDAQ",
            "assetType": "Stock",
            "ipoDate": "2000-01-15",
            "delistingDate": "2020-05-20",
            "delistingReason": "Merger",
            "status": "Delisted"
        }
    ]
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `data` | array | Array of delisted securities |
| `data[].symbol` | string | Stock symbol |
| `data[].name` | string | Company name |
| `data[].exchange` | string | Exchange where it was listed |
| `data[].assetType` | string | Asset type (e.g., `Stock`, `ETF`) |
| `data[].ipoDate` | string | IPO date (YYYY-MM-DD) |
| `data[].delistingDate` | string | Delisting date (YYYY-MM-DD) |
| `data[].delistingReason` | string | Reason for delisting (e.g., `Merger`, `Bankruptcy`, `Acquisition`) |
| `data[].status` | string | Status (always `Delisted`) |

## Examples

### cURL

```bash
# Get all delisted securities
curl "https://www.alphavantage.co/query?function=DELISTING_STATUS&apikey=YOUR_API_KEY"

# Get delisted securities as of a specific date
curl "https://www.alphavantage.co/query?function=DELISTING_STATUS&date=2020-05-20&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns only delisted securities
- Includes delisting reason when available
- Can filter by specific date
- Useful for historical research and compliance checks
- May return large datasets
