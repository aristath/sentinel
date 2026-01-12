# DEMA (Double Exponential Moving Average)

Double Exponential Moving Average technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Double Exponential Moving Average (DEMA) values for a given equity. DEMA reduces lag by applying EMA twice, making it more responsive to price changes than EMA.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `DEMA` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each DEMA value (e.g., `60` for 60-period DEMA) |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Double Exponential Moving Average (DEMA)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 60,
        "6: Series Type": "close",
        "7: Time Zone": "US/Eastern"
    },
    "Technical Analysis: DEMA": {
        "2024-01-15": {
            "DEMA": "185.5678"
        },
        "2024-01-14": {
            "DEMA": "185.4567"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=DEMA&symbol=IBM&interval=daily&time_period=60&series_type=close&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- DEMA reduces lag compared to EMA by applying exponential smoothing twice
- More responsive to price changes than EMA or SMA
- Common time periods: 20, 50, 100, 200 days
- Use `series_type=close` for most standard DEMA calculations
- Formula: DEMA = 2*EMA - EMA(EMA)
