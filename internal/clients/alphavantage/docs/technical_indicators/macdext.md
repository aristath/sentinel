# MACDEXT (MACD with Controllable Moving Average Type)

MACD with controllable moving average type technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the MACDEXT (MACD Extended) values for a given equity. MACDEXT is similar to MACD but allows you to specify the type of moving average used for the fast, slow, and signal lines.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `MACDEXT` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `fastperiod` | integer | No | Number of periods for the fast moving average (default: `12`) |
| `slowperiod` | integer | No | Number of periods for the slow moving average (default: `26`) |
| `signalperiod` | integer | No | Number of periods for the signal line (default: `9`) |
| `fastmatype` | integer | No | Moving average type for fast line. Valid values: `0`=SMA, `1`=EMA, `2`=WMA, `3`=DEMA, `4`=TEMA, `5`=TRIMA, `6`=T3, `7`=KAMA, `8`=MAMA (default: `0`) |
| `slowmatype` | integer | No | Moving average type for slow line. Valid values: same as fastmatype (default: `0`) |
| `signalmatype` | integer | No | Moving average type for signal line. Valid values: same as fastmatype (default: `0`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "MACD with Controllable MA Type (MACDEXT)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Fast Period": 12,
        "6: Slow Period": 26,
        "7: Signal Period": 9,
        "8: Fast MA Type": 0,
        "9: Slow MA Type": 0,
        "10: Signal MA Type": 0,
        "11: Series Type": "close",
        "12: Time Zone": "US/Eastern"
    },
    "Technical Analysis: MACDEXT": {
        "2024-01-15": {
            "MACD": "0.1234",
            "MACD_Signal": "0.1123",
            "MACD_Hist": "0.0111"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=MACDEXT&symbol=IBM&interval=daily&series_type=close&fastperiod=12&slowperiod=26&signalperiod=9&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- MACDEXT allows customization of moving average types
- Can use different MA types for fast, slow, and signal lines
- Standard parameters: 12, 26, 9 (same as MACD)
- Default MA type is SMA (0) for all lines
- More flexible than standard MACD indicator
