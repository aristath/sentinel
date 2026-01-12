# STOCHRSI (Stochastic Relative Strength Index)

Stochastic Relative Strength Index technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Stochastic RSI (STOCHRSI) values for a given equity. STOCHRSI applies the Stochastic Oscillator formula to RSI values instead of price, providing a more sensitive momentum indicator.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `STOCHRSI` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate RSI (default: `14`) |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `fastkperiod` | integer | No | Time period for fast %K (default: `5`) |
| `fastdperiod` | integer | No | Time period for fast %D (default: `3`) |
| `fastdmatype` | integer | No | Moving average type for fast %D. Valid values: `0`=SMA, `1`=EMA, `2`=WMA, `3`=DEMA, `4`=TEMA, `5`=TRIMA, `6`=T3, `7`=KAMA, `8`=MAMA (default: `0`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Stochastic Relative Strength Index (STOCHRSI)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 14,
        "6: Series Type": "close",
        "7: FastK Period": 5,
        "8: FastD Period": 3,
        "9: FastD MA Type": 0,
        "10: Time Zone": "US/Eastern"
    },
    "Technical Analysis: STOCHRSI": {
        "2024-01-15": {
            "FastK": "65.50",
            "FastD": "63.25"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=STOCHRSI&symbol=IBM&interval=daily&time_period=14&series_type=close&fastkperiod=5&fastdperiod=3&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- STOCHRSI applies Stochastic formula to RSI values
- More sensitive than standard RSI
- Values range from 0 to 100
- Values above 80 typically indicate overbought conditions
- Values below 20 typically indicate oversold conditions
- Standard parameters: time_period=14, fastkperiod=5, fastdperiod=3
