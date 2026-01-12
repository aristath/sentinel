# LISTING_STATUS

List of active or delisted US stocks and ETFs.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns a list of active or delisted US stocks and ETFs, either as of the latest trading day or a specific date in history.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `LISTING_STATUS` |
| `date` | string | No | Specific date in format `YYYY-MM-DD` (e.g., `2014-07-10`). If not provided, returns latest trading day data |
| `state` | string | No | Set to `active` (default) or `delisted` |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "data": [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "exchange": "NASDAQ",
            "assetType": "Stock",
            "ipoDate": "1980-12-12",
            "delistingDate": null,
            "status": "Active"
        },
        {
            "symbol": "MSFT",
            "name": "Microsoft Corporation",
            "exchange": "NASDAQ",
            "assetType": "Stock",
            "ipoDate": "1986-03-13",
            "delistingDate": null,
            "status": "Active"
        }
    ]
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `data` | array | Array of listing records |
| `data[].symbol` | string | Stock symbol |
| `data[].name` | string | Company name |
| `data[].exchange` | string | Exchange (e.g., `NASDAQ`, `NYSE`) |
| `data[].assetType` | string | Asset type (e.g., `Stock`, `ETF`) |
| `data[].ipoDate` | string | IPO date (YYYY-MM-DD) |
| `data[].delistingDate` | string | Delisting date (YYYY-MM-DD) or null |
| `data[].status` | string | Status (`Active` or `Delisted`) |

## Examples

### cURL

```bash
# Get active listings as of latest trading day
curl "https://www.alphavantage.co/query?function=LISTING_STATUS&state=active&apikey=YOUR_API_KEY"

# Get delisted stocks as of a specific date
curl "https://www.alphavantage.co/query?function=LISTING_STATUS&date=2014-07-10&state=delisted&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Can filter by `active` or `delisted` status
- Can specify a historical date to see listings as of that date
- Returns both stocks and ETFs
- Includes IPO dates and delisting dates
- Large dataset - may return thousands of symbols
