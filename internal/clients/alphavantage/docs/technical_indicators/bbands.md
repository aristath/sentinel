# BBANDS (Bollinger Bands)

Bollinger Bands technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns Bollinger Bands values for a given equity. Bollinger Bands consist of a middle band (SMA) and two outer bands that are standard deviations away from the middle band.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `BBANDS` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each BBANDS value (default: `5`) |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `nbdevup` | float | No | Standard deviation multiplier for the upper band (default: `2`) |
| `nbdevdn` | float | No | Standard deviation multiplier for the lower band (default: `2`) |
| `matype` | integer | No | Moving average type for the middle band. Valid values: `0`=SMA, `1`=EMA, `2`=WMA, `3`=DEMA, `4`=TEMA, `5`=TRIMA, `6`=T3, `7`=KAMA, `8`=MAMA (default: `0`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Bollinger Bands (BBANDS)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 5,
        "6: Series Type": "close",
        "7: Time Zone": "US/Eastern"
    },
    "Technical Analysis: BBANDS": {
        "2024-01-15": {
            "Real Upper Band": "190.1234",
            "Real Middle Band": "185.0000",
            "Real Lower Band": "179.8766"
        },
        "2024-01-14": {
            "Real Upper Band": "189.5000",
            "Real Middle Band": "184.5000",
            "Real Lower Band": "179.5000"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=BBANDS&symbol=IBM&interval=daily&time_period=5&series_type=close&nbdevup=2&nbdevdn=2&matype=0&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Upper and lower bands indicate potential overbought/oversold conditions
- Prices touching upper band may indicate overbought condition
- Prices touching lower band may indicate oversold condition
- Standard deviation multipliers are typically 2
- Common time periods: 20, 50
