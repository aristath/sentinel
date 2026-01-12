# STOCH (Stochastic Oscillator)

Stochastic Oscillator technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Stochastic Oscillator values for a given equity. The Stochastic Oscillator compares a security's closing price to its price range over a given time period.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `STOCH` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `fastkperiod` | integer | No | The time period of the fastk moving average (default: `5`) |
| `slowkperiod` | integer | No | The time period of the slowk moving average (default: `3`) |
| `slowdperiod` | integer | No | The time period of the slowd moving average (default: `3`) |
| `slowkmatype` | integer | No | Moving average type for slowk. Valid values: `0`=SMA, `1`=EMA, `2`=WMA, `3`=DEMA, `4`=TEMA, `5`=TRIMA, `6`=T3, `7`=KAMA, `8`=MAMA (default: `0`) |
| `slowdmatype` | integer | No | Moving average type for slowd. Valid values: `0`=SMA, `1`=EMA, `2`=WMA, `3`=DEMA, `4`=TEMA, `5`=TRIMA, `6`=T3, `7`=KAMA, `8`=MAMA (default: `0`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Stochastic (STOCH)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: FastK Period": 5,
        "6: SlowK Period": 3,
        "7: SlowK MA Type": 0,
        "8: SlowD Period": 3,
        "9: SlowD MA Type": 0,
        "10: Time Zone": "US/Eastern"
    },
    "Technical Analysis: STOCH": {
        "2024-01-15": {
            "SlowK": "65.2345",
            "SlowD": "63.1234"
        },
        "2024-01-14": {
            "SlowK": "63.1234",
            "SlowD": "61.5678"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=STOCH&symbol=IBM&interval=daily&fastkperiod=5&slowkperiod=3&slowdperiod=3&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Stochastic values range from 0 to 100
- Values above 80 typically indicate overbought conditions
- Values below 20 typically indicate oversold conditions
- Standard parameters: fastkperiod=5, slowkperiod=3, slowdperiod=3
- SlowK and SlowD are smoothed versions of the raw stochastic values
