# Alpha Vantage API Usage Examples

Practical examples for common use cases with Alpha Vantage API.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Stock Price Data](#stock-price-data)
3. [Technical Analysis](#technical-analysis)
4. [Fundamental Analysis](#fundamental-analysis)
5. [Forex and Crypto](#forex-and-crypto)
6. [Market Intelligence](#market-intelligence)
7. [Error Handling](#error-handling)
8. [Rate Limiting Strategies](#rate-limiting-strategies)

## Getting Started

### Basic Request Structure

All requests follow this pattern:
```
https://www.alphavantage.co/query?function=FUNCTION_NAME&param1=value1&param2=value2&apikey=YOUR_API_KEY
```

### Python Example - Basic Setup

```python
import requests
import json

API_KEY = "YOUR_API_KEY"
BASE_URL = "https://www.alphavantage.co/query"

def make_request(params):
    params['apikey'] = API_KEY
    response = requests.get(BASE_URL, params=params)
    return response.json()

# Example: Get daily stock data
data = make_request({
    'function': 'TIME_SERIES_DAILY',
    'symbol': 'IBM',
    'outputsize': 'compact'
})
print(json.dumps(data, indent=2))
```

### JavaScript Example - Basic Setup

```javascript
const API_KEY = 'YOUR_API_KEY';
const BASE_URL = 'https://www.alphavantage.co/query';

async function makeRequest(params) {
    params.apikey = API_KEY;
    const queryString = new URLSearchParams(params).toString();
    const response = await fetch(`${BASE_URL}?${queryString}`);
    return await response.json();
}

// Example: Get daily stock data
const data = await makeRequest({
    function: 'TIME_SERIES_DAILY',
    symbol: 'IBM',
    outputsize: 'compact'
});
console.log(data);
```

## Stock Price Data

### Get Latest Stock Price

```python
def get_latest_price(symbol):
    params = {
        'function': 'TIME_SERIES_DAILY',
        'symbol': symbol,
        'outputsize': 'compact'
    }
    data = make_request(params)

    if 'Time Series (Daily)' in data:
        latest_date = max(data['Time Series (Daily)'].keys())
        latest_data = data['Time Series (Daily)'][latest_date]
        return {
            'date': latest_date,
            'close': float(latest_data['4. close']),
            'volume': int(latest_data['5. volume'])
        }
    return None

price = get_latest_price('IBM')
print(f"IBM Latest Close: ${price['close']}")
```

### Get Historical Price Range

```python
def get_price_range(symbol, days=30):
    params = {
        'function': 'TIME_SERIES_DAILY',
        'symbol': symbol,
        'outputsize': 'full'
    }
    data = make_request(params)

    if 'Time Series (Daily)' in data:
        prices = []
        for date, values in list(data['Time Series (Daily)'].items())[:days]:
            prices.append(float(values['4. close']))

        return {
            'high': max(prices),
            'low': min(prices),
            'current': prices[0]
        }
    return None

range_data = get_price_range('IBM', days=30)
print(f"30-day range: ${range_data['low']:.2f} - ${range_data['high']:.2f}")
```

## Technical Analysis

### Calculate Multiple Indicators

```python
def get_technical_indicators(symbol):
    indicators = {}

    # RSI
    rsi_data = make_request({
        'function': 'RSI',
        'symbol': symbol,
        'interval': 'daily',
        'time_period': 14,
        'series_type': 'close'
    })
    if 'Technical Analysis: RSI' in rsi_data:
        latest_rsi = list(rsi_data['Technical Analysis: RSI'].values())[0]
        indicators['RSI'] = float(latest_rsi['RSI'])

    # MACD
    macd_data = make_request({
        'function': 'MACD',
        'symbol': symbol,
        'interval': 'daily',
        'series_type': 'close'
    })
    if 'Technical Analysis: MACD' in macd_data:
        latest_macd = list(macd_data['Technical Analysis: MACD'].values())[0]
        indicators['MACD'] = {
            'MACD': float(latest_macd['MACD']),
            'Signal': float(latest_macd['MACD_Signal']),
            'Hist': float(latest_macd['MACD_Hist'])
        }

    # Bollinger Bands
    bb_data = make_request({
        'function': 'BBANDS',
        'symbol': symbol,
        'interval': 'daily',
        'time_period': 20,
        'series_type': 'close'
    })
    if 'Technical Analysis: BBANDS' in bb_data:
        latest_bb = list(bb_data['Technical Analysis: BBANDS'].values())[0]
        indicators['BBANDS'] = {
            'Upper': float(latest_bb['Real Upper Band']),
            'Middle': float(latest_bb['Real Middle Band']),
            'Lower': float(latest_bb['Real Lower Band'])
        }

    return indicators

tech_data = get_technical_indicators('IBM')
print(f"RSI: {tech_data['RSI']:.2f}")
print(f"MACD: {tech_data['MACD']}")
```

### Moving Average Crossover Strategy

```python
def check_ma_crossover(symbol):
    # Get 50-day SMA
    sma50_data = make_request({
        'function': 'SMA',
        'symbol': symbol,
        'interval': 'daily',
        'time_period': 50,
        'series_type': 'close'
    })

    # Get 200-day SMA
    sma200_data = make_request({
        'function': 'SMA',
        'symbol': symbol,
        'interval': 'daily',
        'time_period': 200,
        'series_type': 'close'
    })

    if 'Technical Analysis: SMA' in sma50_data and 'Technical Analysis: SMA' in sma200_data:
        latest_50 = list(sma50_data['Technical Analysis: SMA'].values())[0]
        latest_200 = list(sma200_data['Technical Analysis: SMA'].values())[0]

        sma50 = float(latest_50['SMA'])
        sma200 = float(latest_200['SMA'])

        if sma50 > sma200:
            return "Bullish: 50-day MA above 200-day MA"
        else:
            return "Bearish: 50-day MA below 200-day MA"

    return None

signal = check_ma_crossover('IBM')
print(signal)
```

## Fundamental Analysis

### Get Company Fundamentals

```python
def get_company_fundamentals(symbol):
    overview = make_request({
        'function': 'OVERVIEW',
        'symbol': symbol
    })

    if 'Symbol' in overview:
        return {
            'name': overview.get('Name'),
            'sector': overview.get('Sector'),
            'industry': overview.get('Industry'),
            'market_cap': overview.get('MarketCapitalization'),
            'pe_ratio': overview.get('PERatio'),
            'dividend_yield': overview.get('DividendYield'),
            'eps': overview.get('EPS'),
            'beta': overview.get('Beta')
        }
    return None

fundamentals = get_company_fundamentals('IBM')
print(f"Company: {fundamentals['name']}")
print(f"Sector: {fundamentals['sector']}")
print(f"P/E Ratio: {fundamentals['pe_ratio']}")
```

### Compare Multiple Stocks

```python
def compare_stocks(symbols):
    comparison = {}

    for symbol in symbols:
        overview = make_request({
            'function': 'OVERVIEW',
            'symbol': symbol
        })

        if 'Symbol' in overview:
            comparison[symbol] = {
                'pe_ratio': overview.get('PERatio'),
                'dividend_yield': overview.get('DividendYield'),
                'market_cap': overview.get('MarketCapitalization'),
                'beta': overview.get('Beta')
            }

    return comparison

stocks = compare_stocks(['IBM', 'MSFT', 'AAPL'])
for symbol, data in stocks.items():
    print(f"{symbol}: P/E={data['pe_ratio']}, Yield={data['dividend_yield']}")
```

## Forex and Crypto

### Get Currency Exchange Rate

```python
def get_exchange_rate(from_currency, to_currency):
    data = make_request({
        'function': 'CURRENCY_EXCHANGE_RATE',
        'from_currency': from_currency,
        'to_currency': to_currency
    })

    if 'Realtime Currency Exchange Rate' in data:
        rate = data['Realtime Currency Exchange Rate']
        return {
            'from': rate['1. From_Currency Code'],
            'to': rate['3. To_Currency Code'],
            'rate': float(rate['5. Exchange Rate']),
            'last_refreshed': rate['6. Last Refreshed']
        }
    return None

rate = get_exchange_rate('USD', 'EUR')
print(f"1 {rate['from']} = {rate['rate']:.4f} {rate['to']}")
```

### Get Cryptocurrency Price

```python
def get_crypto_price(symbol, market='USD'):
    data = make_request({
        'function': 'DIGITAL_CURRENCY_DAILY',
        'symbol': symbol,
        'market': market
    })

    if 'Time Series (Digital Currency Daily)' in data:
        latest_date = max(data['Time Series (Digital Currency Daily)'].keys())
        latest_data = data['Time Series (Digital Currency Daily)'][latest_date]
        return {
            'date': latest_date,
            'close': float(latest_data['4a. close (USD)']),
            'volume': float(latest_data['5. volume']),
            'market_cap': float(latest_data['6. market cap (USD)'])
        }
    return None

btc = get_crypto_price('BTC', 'USD')
print(f"BTC Price: ${btc['close']:,.2f}")
print(f"Market Cap: ${btc['market_cap']:,.0f}")
```

## Market Intelligence

### Get Top Gainers and Losers

```python
def get_market_movers():
    data = make_request({
        'function': 'TOP_GAINERS_LOSERS'
    })

    if 'top_gainers' in data:
        return {
            'gainers': data.get('top_gainers', []),
            'losers': data.get('top_losers', []),
            'most_active': data.get('most_actively_traded', [])
        }
    return None

movers = get_market_movers()
print("Top Gainers:")
for stock in movers['gainers'][:5]:
    print(f"  {stock['ticker']}: {stock['change_percentage']}")
```

### Get News Sentiment (Premium)

```python
def get_news_sentiment(symbol, limit=10):
    data = make_request({
        'function': 'NEWS_SENTIMENT',
        'tickers': symbol,
        'limit': limit
    })

    if 'feed' in data:
        articles = []
        for item in data['feed']:
            articles.append({
                'title': item.get('title'),
                'sentiment': item.get('overall_sentiment_label'),
                'score': item.get('overall_sentiment_score'),
                'url': item.get('url')
            })
        return articles
    return None

# Note: Requires premium API key
news = get_news_sentiment('IBM', limit=5)
for article in news:
    print(f"{article['title']}: {article['sentiment']} ({article['score']:.2f})")
```

## Error Handling

### Robust Request Handler

```python
import time
from typing import Optional, Dict, Any

def safe_request(params: Dict[str, Any], max_retries: int = 3) -> Optional[Dict]:
    """Make API request with error handling and retries."""
    for attempt in range(max_retries):
        try:
            response = make_request(params)

            # Check for API errors
            if 'Error Message' in response:
                print(f"API Error: {response['Error Message']}")
                return None

            if 'Note' in response:
                print(f"Rate limit: {response['Note']}")
                time.sleep(60)  # Wait 1 minute if rate limited
                continue

            # Check for invalid function
            if 'Information' not in response and 'Meta Data' not in response:
                print(f"Unexpected response format")
                return None

            return response

        except Exception as e:
            print(f"Request failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                return None

    return None

# Usage
data = safe_request({
    'function': 'TIME_SERIES_DAILY',
    'symbol': 'IBM'
})
```

## Rate Limiting Strategies

### Request Queue with Rate Limiting

```python
import time
from collections import deque
from threading import Lock

class RateLimitedAPI:
    def __init__(self, api_key, requests_per_day=25):
        self.api_key = api_key
        self.requests_per_day = requests_per_day
        self.request_times = deque(maxlen=requests_per_day)
        self.lock = Lock()

    def make_request(self, params):
        with self.lock:
            # Check if we've hit the daily limit
            if len(self.request_times) >= self.requests_per_day:
                # Wait until oldest request is 24 hours old
                oldest_time = self.request_times[0]
                wait_time = 86400 - (time.time() - oldest_time)
                if wait_time > 0:
                    print(f"Rate limit reached. Waiting {wait_time/60:.1f} minutes...")
                    time.sleep(wait_time)

            # Make request
            params['apikey'] = self.api_key
            response = requests.get(BASE_URL, params=params)
            self.request_times.append(time.time())

            return response.json()

# Usage
api = RateLimitedAPI('YOUR_API_KEY', requests_per_day=25)
data = api.make_request({
    'function': 'TIME_SERIES_DAILY',
    'symbol': 'IBM'
})
```

### Batch Processing with Delays

```python
def batch_process_symbols(symbols, function, delay=12):
    """Process multiple symbols with delay between requests."""
    results = {}

    for i, symbol in enumerate(symbols):
        print(f"Processing {symbol} ({i+1}/{len(symbols)})...")

        data = make_request({
            'function': function,
            'symbol': symbol
        })

        results[symbol] = data

        # Wait between requests to avoid rate limiting
        if i < len(symbols) - 1:
            time.sleep(delay)  # 12 seconds = ~5 requests/minute

    return results

# Process 10 symbols (will take ~2 minutes with 12s delay)
symbols = ['IBM', 'MSFT', 'AAPL', 'GOOGL', 'AMZN']
results = batch_process_symbols(symbols, 'OVERVIEW', delay=12)
```

## Best Practices

1. **Cache Responses**: Store API responses to reduce requests
2. **Handle Errors**: Always check for error messages in responses
3. **Rate Limiting**: Implement proper rate limiting for free tier
4. **Data Validation**: Validate responses before processing
5. **Use Premium**: Consider premium tier for production applications
6. **Batch Requests**: Group related requests when possible
7. **Monitor Usage**: Track API calls to stay within limits

## Additional Resources

- [Main Documentation](./README.md)
- [Quick Reference](./QUICK_REFERENCE.md)
- [Technical Indicators](./technical_indicators/README.md)
