# HT_PHASOR (Hilbert Transform - Phasor Components)

Hilbert Transform Phasor Components technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Hilbert Transform Phasor Components values for a given equity. This indicator provides the in-phase and quadrature components of the dominant cycle.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `HT_PHASOR` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Hilbert Transform - Phasor Components (HT_PHASOR)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Series Type": "close",
        "6: Time Zone": "US/Eastern"
    },
    "Technical Analysis: HT_PHASOR": {
        "2024-01-15": {
            "PHASOR_INPHASE": "0.75",
            "PHASOR_QUADRATURE": "0.65"
        },
        "2024-01-14": {
            "PHASOR_INPHASE": "0.73",
            "PHASOR_QUADRATURE": "0.63"
        }
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=HT_PHASOR&symbol=IBM&interval=daily&series_type=close&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns in-phase and quadrature components
- Uses Hilbert Transform for cycle analysis
- Components are used to calculate phase and period
- Advanced indicator for cycle analysis
- Use `series_type=close` for most standard calculations
- Part of the Hilbert Transform indicator family
