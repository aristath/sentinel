# NEWS_SENTIMENT

Market news and sentiment analysis.

## API Tier

**Free Tier Available**: No
**Premium Required**: Yes

## Description

This API delivers live and historical market news along with sentiment analysis, enabling users to gauge market sentiment based on news articles. This is a premium endpoint.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `NEWS_SENTIMENT` |
| `tickers` | string | No | Comma-separated list of stock tickers (e.g., `IBM,MSFT,AAPL`) |
| `topics` | string | No | Comma-separated list of topics (e.g., `technology,earnings,ipo`) |
| `time_from` | string | No | Start time in format `YYYYMMDDTHHMM` (e.g., `20240115T0000`) |
| `time_to` | string | No | End time in format `YYYYMMDDTHHMM` (e.g., `20240115T2359`) |
| `sort` | string | No | Sort order. Valid values: `LATEST` (default), `EARLIEST`, `RELEVANCE` |
| `limit` | integer | No | Maximum number of results to return (default: 50, max: 1000) |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "items": "50",
    "sentiment_score_definition": "x <= -0.35: Bearish; -0.35 < x <= -0.15: Somewhat-Bearish; -0.15 < x < 0.15: Neutral; 0.15 <= x < 0.35: Somewhat-Bullish; x >= 0.35: Bullish",
    "relevance_score_definition": "x > 1: the article is exclusively discussing the topic; 0 < x <= 1: the article partially discusses the topic; x = 0: the article does not discuss the topic",
    "feed": [
        {
            "title": "IBM Reports Strong Quarterly Earnings",
            "url": "https://example.com/news/ibm-earnings",
            "time_published": "20240115T160000",
            "authors": ["John Doe"],
            "summary": "IBM reported strong quarterly earnings...",
            "banner_image": "https://example.com/images/ibm.jpg",
            "source": "Financial Times",
            "category_within_source": "Technology",
            "source_domain": "ft.com",
            "topics": [
                {
                    "topic": "Earnings",
                    "relevance_score": "0.95"
                },
                {
                    "topic": "Technology",
                    "relevance_score": "0.85"
                }
            ],
            "overall_sentiment_score": 0.65,
            "overall_sentiment_label": "Somewhat-Bullish",
            "ticker_sentiment": [
                {
                    "ticker": "IBM",
                    "relevance_score": "0.98",
                    "ticker_sentiment_score": "0.70",
                    "ticker_sentiment_label": "Somewhat-Bullish"
                }
            ]
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=IBM&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Premium Tier Only**: 75-1200 requests per minute (depending on plan)

## Notes

- **Premium endpoint** - requires a paid subscription
- Sentiment scores range from -1 (very bearish) to +1 (very bullish)
- Relevance scores indicate how closely the article relates to the topic
- Can filter by tickers, topics, and time range
- Returns up to 1000 articles per request
