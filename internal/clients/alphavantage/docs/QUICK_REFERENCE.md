# Alpha Vantage API Quick Reference

Quick reference guide for Alpha Vantage API endpoints.

## Base URL

```
https://www.alphavantage.co/query
```

## Authentication

All requests require an `apikey` parameter with your Alpha Vantage API key.

## Rate Limits

| Tier | Daily Limit | Per Minute Limit | Premium Endpoints |
|------|-------------|------------------|------------------|
| Free | 25 requests | N/A | No |
| Premium | Unlimited | 75-1200 requests | Yes |

## Premium Endpoints

Only 3 endpoints require premium subscription:
- `FX_INTRADAY` - Real-time forex intraday data
- `NEWS_SENTIMENT` - News sentiment analysis
- `REALTIME_OPTIONS` - Real-time options data

All other endpoints are available on the free tier.

## Common Parameters

Most endpoints share these common parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `function` | string | The API function name (required) |
| `apikey` | string | Your API key (required) |
| `datatype` | string | Output format: `json` (default) or `csv` |
| `symbol` | string | Stock ticker symbol (for stock endpoints) |
| `interval` | string | Time interval: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |

## Endpoint Categories

### Time Series Stock Data
- `TIME_SERIES_INTRADAY` - Intraday data
- `TIME_SERIES_DAILY` - Daily data
- `TIME_SERIES_DAILY_ADJUSTED` - Daily adjusted data
- `TIME_SERIES_WEEKLY` - Weekly data
- `TIME_SERIES_WEEKLY_ADJUSTED` - Weekly adjusted data
- `TIME_SERIES_MONTHLY` - Monthly data
- `TIME_SERIES_MONTHLY_ADJUSTED` - Monthly adjusted data

### Technical Indicators
Common indicators:
- `SMA`, `EMA`, `WMA`, `DEMA`, `TEMA` - Moving averages
- `RSI`, `STOCH`, `STOCHF`, `WILLR`, `MFI` - Momentum oscillators
- `MACD` - Moving Average Convergence Divergence
- `BBANDS` - Bollinger Bands
- `ADX`, `PLUS_DI`, `MINUS_DI` - Trend indicators
- `ATR`, `SAR` - Volatility indicators
- `OBV`, `AD` - Volume indicators

See [Technical Indicators README](./technical_indicators/README.md) for complete list.

### Fundamental Data
- `OVERVIEW` - Company overview
- `EARNINGS` - Earnings data
- `INCOME_STATEMENT` - Income statement
- `BALANCE_SHEET` - Balance sheet
- `CASH_FLOW` - Cash flow statement

### Forex & Cryptocurrency
- `CURRENCY_EXCHANGE_RATE` - Real-time exchange rate
- `FX_DAILY`, `FX_WEEKLY`, `FX_MONTHLY` - Forex time series
- `FX_INTRADAY` - **Premium** - Forex intraday
- `DIGITAL_CURRENCY_DAILY`, `DIGITAL_CURRENCY_WEEKLY`, `DIGITAL_CURRENCY_MONTHLY` - Crypto time series

### Alpha Intelligence
- `NEWS_SENTIMENT` - **Premium** - News sentiment analysis
- `TOP_GAINERS_LOSERS` - Top gainers, losers, most active
- `EARNINGS_CALL_TRANSCRIPT` - Earnings call transcripts
- `INSIDER_TRANSACTIONS` - Insider transaction data

### Commodities
- `WTI`, `BRENT` - Crude oil
- `NATURAL_GAS` - Natural gas
- `COPPER`, `ALUMINUM` - Metals
- `WHEAT`, `CORN`, `COTTON`, `SUGAR`, `COFFEE` - Agricultural

### Economic Indicators
- `REAL_GDP`, `REAL_GDP_PER_CAPITA` - GDP data
- `UNEMPLOYMENT` - Unemployment rate
- `CPI`, `INFLATION` - Inflation data
- `FEDERAL_FUNDS_RATE` - Federal funds rate
- `TREASURY_YIELD` - Treasury yields
- `RETAIL_SALES` - Retail sales
- `DURABLE_GOODS_ORDERS` - Durable goods orders
- `NONFARM_PAYROLL` - Nonfarm payroll

### Options Data
- `HISTORICAL_OPTIONS` - Historical options chain
- `REALTIME_OPTIONS` - **Premium** - Real-time options chain

## Example Requests

### Get Daily Stock Data
```
GET https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=IBM&apikey=YOUR_API_KEY
```

### Get RSI Indicator
```
GET https://www.alphavantage.co/query?function=RSI&symbol=IBM&interval=daily&time_period=14&series_type=close&apikey=YOUR_API_KEY
```

### Get Company Overview
```
GET https://www.alphavantage.co/query?function=OVERVIEW&symbol=IBM&apikey=YOUR_API_KEY
```

### Get Currency Exchange Rate
```
GET https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency=USD&to_currency=EUR&apikey=YOUR_API_KEY
```

## Response Format

All endpoints return JSON by default. Responses typically include:
- `Meta Data` - Metadata about the request
- Data section - The actual data (varies by endpoint)

## Error Handling

Common error responses:
- `"Error Message": "Invalid API call"` - Check function name and parameters
- `"Note": "Thank you for using Alpha Vantage!"` - Rate limit exceeded (free tier)
- `"Information": "..."` - Success response with data

## Best Practices

1. **Rate Limiting**: Implement request throttling for free tier (25/day)
2. **Error Handling**: Always check for error messages in responses
3. **Caching**: Cache responses when possible to reduce API calls
4. **Parameter Validation**: Validate all parameters before making requests
5. **Premium Consideration**: Use premium tier for production applications requiring higher limits

## Documentation

For detailed documentation on each endpoint, see:
- [Main README](./README.md) - Complete endpoint index
- [Technical Indicators README](./technical_indicators/README.md) - All technical indicators
- Individual endpoint files in respective category directories

## Support

- Official Documentation: https://www.alphavantage.co/documentation/
- API Key Registration: https://www.alphavantage.co/support/#api-key
- Premium Plans: https://www.alphavantage.co/premium/
