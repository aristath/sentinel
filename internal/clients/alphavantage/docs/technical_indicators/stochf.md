# STOCHF (Stochastic Fast)

Stochastic Fast technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Stochastic Fast (STOCHF) values for a given equity. STOCHF is the fast version of the Stochastic Oscillator, providing faster signals but potentially more false signals.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `STOCHF` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `fastkperiod` | integer | No | The time period of the fastk moving average (default: `5`) |
| `fastdperiod` | integer | No | The time period of the fastd moving average (default: `3`) |
| `fastdmatype` | integer | No | Moving average type for fastd. Valid values: `0`=SMA, `1`=EMA, `2`=WMA, `3`=DEMA, `4`=TEMA, `5`=TRIMA, `6`=T3, `7`=KAMA, `8`=MAMA (default: `0`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Stochastic Fast (STOCHF)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: FastK Period": 5,
        "6: FastD Period": 3,
        "7: FastD MA Type": 0,
        "8: Time Zone": "US/Eastern"
    },
    "Technical Analysis: STOCHF": {
        "2024-01-15": {
            "FastK": "65.2345",
            "FastD": "63.1234"
        },
        "2024-01-14": {
            "FastK": "63.1234",
            "FastD": "61.5678"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=STOCHF&symbol=IBM&interval=daily&fastkperiod=5&fastdperiod=3&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- STOCHF values range from 0 to 100
- Faster response than STOCH but may produce more false signals
- Values above 80 typically indicate overbought conditions
- Values below 20 typically indicate oversold conditions
- Standard parameters: fastkperiod=5, fastdperiod=3
