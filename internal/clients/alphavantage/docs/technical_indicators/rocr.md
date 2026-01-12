# ROCR (Rate of Change Ratio)

Rate of Change Ratio technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Rate of Change Ratio (ROCR) values for a given equity. ROCR measures the ratio of the current price to a price from a specified number of periods ago.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `ROCR` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each ROCR value (default: `10`) |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Rate of Change Ratio (ROCR)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 10,
        "6: Series Type": "close",
        "7: Time Zone": "US/Eastern"
    },
    "Technical Analysis: ROCR": {
        "2024-01-15": {
            "ROCR": "1.0250"
        },
        "2024-01-14": {
            "ROCR": "1.0225"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=ROCR&symbol=IBM&interval=daily&time_period=10&series_type=close&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- ROCR is expressed as a ratio (e.g., 1.025 = 2.5% increase)
- Values above 1.0 indicate price increase over the period
- Values below 1.0 indicate price decrease over the period
- Standard time period is 10 periods
- Use `series_type=close` for most standard ROCR calculations
- ROCR = Current Price / Price N periods ago
- Similar to ROC but expressed as a ratio rather than percentage
