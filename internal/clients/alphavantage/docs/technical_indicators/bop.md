# BOP (Balance of Power)

Balance of Power technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Balance of Power (BOP) values for a given equity. BOP measures the strength of buying vs selling pressure by comparing the close price to the open price relative to the high-low range.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `BOP` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Balance of Power (BOP)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Zone": "US/Eastern"
    },
    "Technical Analysis: BOP": {
        "2024-01-15": {
            "BOP": "0.25"
        },
        "2024-01-14": {
            "BOP": "-0.15"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=BOP&symbol=IBM&interval=daily&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- BOP values range from -1 to +1
- Positive values indicate buying pressure (close near high)
- Negative values indicate selling pressure (close near low)
- Formula: BOP = (Close - Open) / (High - Low)
- No time period parameter needed
- Useful for identifying buying/selling pressure
