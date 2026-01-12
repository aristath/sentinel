# APO (Absolute Price Oscillator)

Absolute Price Oscillator technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Absolute Price Oscillator (APO) values for a given equity. APO measures the difference between two moving averages in absolute price terms.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `APO` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `fastperiod` | integer | No | Number of periods for the fast moving average (default: `12`) |
| `slowperiod` | integer | No | Number of periods for the slow moving average (default: `26`) |
| `matype` | integer | No | Moving average type. Valid values: `0`=SMA, `1`=EMA, `2`=WMA, `3`=DEMA, `4`=TEMA, `5`=TRIMA, `6`=T3, `7`=KAMA, `8`=MAMA (default: `0`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Absolute Price Oscillator (APO)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Series Type": "close",
        "6: Fast Period": 12,
        "7: Slow Period": 26,
        "8: MA Type": 0,
        "9: Time Zone": "US/Eastern"
    },
    "Technical Analysis: APO": {
        "2024-01-15": {
            "APO": "2.50"
        },
        "2024-01-14": {
            "APO": "2.25"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=APO&symbol=IBM&interval=daily&series_type=close&fastperiod=12&slowperiod=26&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- APO = Fast MA - Slow MA (absolute difference)
- Expressed in price units, not percentage
- Positive values indicate fast MA above slow MA
- Negative values indicate fast MA below slow MA
- Standard parameters: fastperiod=12, slowperiod=26
- Similar to MACD but expressed in absolute terms rather than percentage
