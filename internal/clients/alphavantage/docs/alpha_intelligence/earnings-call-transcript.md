# EARNINGS_CALL_TRANSCRIPT

Earnings call transcripts with sentiment analysis.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API provides access to earnings call transcripts enriched with sentiment analysis powered by large language models (LLMs), offering deeper insights into company performance discussions.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `EARNINGS_CALL_TRANSCRIPT` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `quarter` | integer | Yes | The fiscal quarter (1, 2, 3, or 4) |
| `year` | integer | Yes | The fiscal year (e.g., `2023`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "symbol": "IBM",
    "quarter": 3,
    "year": 2023,
    "transcript": [
        {
            "speaker": "CEO",
            "time": "00:00:00",
            "content": "Good morning, everyone. Thank you for joining us...",
            "sentiment": "neutral"
        },
        {
            "speaker": "CFO",
            "time": "00:05:30",
            "content": "Our revenue for the quarter was $15 billion...",
            "sentiment": "positive"
        }
    ],
    "summary": {
        "overall_sentiment": "positive",
        "sentiment_score": 0.65,
        "key_topics": [
            "Revenue growth",
            "Cloud services",
            "AI initiatives"
        ]
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=EARNINGS_CALL_TRANSCRIPT&symbol=IBM&quarter=3&year=2023&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Provides full earnings call transcripts
- Includes sentiment analysis for each speaker segment
- Summarizes overall sentiment and key topics
- Available for companies that hold earnings calls
