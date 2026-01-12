# AD (Chaikin A/D Line)

Chaikin Accumulation/Distribution Line technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Chaikin Accumulation/Distribution (A/D) Line values for a given equity. The A/D Line uses volume and price to measure the cumulative flow of money into or out of a security.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `AD` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Chaikin A/D Line (AD)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Zone": "US/Eastern"
    },
    "Technical Analysis: AD": {
        "2024-01-15": {
            "Chaikin A/D": "1234567890"
        },
        "2024-01-14": {
            "Chaikin A/D": "1230000000"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=AD&symbol=IBM&interval=daily&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- A/D Line is a cumulative indicator that adds volume on up days and subtracts on down days
- Rising A/D Line suggests accumulation (buying pressure)
- Falling A/D Line suggests distribution (selling pressure)
- A/D Line divergences from price can signal trend reversals
- No time period parameter needed - it's a cumulative calculation
- Similar to OBV but uses a different volume calculation method
