# MACD (Moving Average Convergence Divergence)

Moving Average Convergence Divergence technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Moving Average Convergence Divergence (MACD) values for a given equity. MACD is a trend-following momentum indicator that shows the relationship between two moving averages of prices.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `MACD` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `fastperiod` | integer | No | Number of periods for the fast moving average (default: `12`) |
| `slowperiod` | integer | No | Number of periods for the slow moving average (default: `26`) |
| `signalperiod` | integer | No | Number of periods for the signal line (default: `9`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Moving Average Convergence Divergence (MACD)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Fast Period": 12,
        "6: Slow Period": 26,
        "7: Signal Period": 9,
        "8: Series Type": "close",
        "9: Time Zone": "US/Eastern"
    },
    "Technical Analysis: MACD": {
        "2024-01-15": {
            "MACD": "0.1234",
            "MACD_Signal": "0.1123",
            "MACD_Hist": "0.0111"
        },
        "2024-01-14": {
            "MACD": "0.1200",
            "MACD_Signal": "0.1100",
            "MACD_Hist": "0.0100"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=MACD&symbol=IBM&interval=daily&series_type=close&fastperiod=12&slowperiod=26&signalperiod=9&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- MACD line is the difference between fast and slow EMAs
- Signal line is an EMA of the MACD line
- MACD_Hist is the difference between MACD and Signal lines
- Positive MACD_Hist indicates bullish momentum
- Standard parameters: 12, 26, 9
