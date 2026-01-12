# TEMA (Triple Exponential Moving Average)

Triple Exponential Moving Average technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Triple Exponential Moving Average (TEMA) values for a given equity. TEMA applies exponential smoothing three times, further reducing lag compared to DEMA.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `TEMA` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each TEMA value (e.g., `60` for 60-period TEMA) |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Triple Exponential Moving Average (TEMA)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 60,
        "6: Series Type": "close",
        "7: Time Zone": "US/Eastern"
    },
    "Technical Analysis: TEMA": {
        "2024-01-15": {
            "TEMA": "185.6789"
        },
        "2024-01-14": {
            "TEMA": "185.5678"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=TEMA&symbol=IBM&interval=daily&time_period=60&series_type=close&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- TEMA applies exponential smoothing three times, reducing lag even more than DEMA
- Most responsive to price changes among EMA variants
- Common time periods: 20, 50, 100, 200 days
- Use `series_type=close` for most standard TEMA calculations
- Formula: TEMA = 3*EMA - 3*EMA(EMA) + EMA(EMA(EMA))
