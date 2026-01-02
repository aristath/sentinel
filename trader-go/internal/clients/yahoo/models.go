package yahoo

import "time"

// FundamentalData contains fundamental analysis metrics
type FundamentalData struct {
	Symbol                   string   `json:"symbol"`
	PERatio                  *float64 `json:"pe_ratio,omitempty"`
	ForwardPE                *float64 `json:"forward_pe,omitempty"`
	PEGRatio                 *float64 `json:"peg_ratio,omitempty"`
	PriceToBook              *float64 `json:"price_to_book,omitempty"`
	RevenueGrowth            *float64 `json:"revenue_growth,omitempty"`
	EarningsGrowth           *float64 `json:"earnings_growth,omitempty"`
	ProfitMargin             *float64 `json:"profit_margin,omitempty"`
	OperatingMargin          *float64 `json:"operating_margin,omitempty"`
	ROE                      *float64 `json:"roe,omitempty"`
	DebtToEquity             *float64 `json:"debt_to_equity,omitempty"`
	CurrentRatio             *float64 `json:"current_ratio,omitempty"`
	MarketCap                *int64   `json:"market_cap,omitempty"`
	DividendYield            *float64 `json:"dividend_yield,omitempty"`
	FiveYearAvgDividendYield *float64 `json:"five_year_avg_dividend_yield,omitempty"`
}

// AnalystData contains analyst recommendations and targets
type AnalystData struct {
	Symbol              string  `json:"symbol"`
	Recommendation      string  `json:"recommendation"`
	TargetPrice         float64 `json:"target_price"`
	CurrentPrice        float64 `json:"current_price"`
	UpsidePct           float64 `json:"upside_pct"`
	NumAnalysts         int     `json:"num_analysts"`
	RecommendationScore float64 `json:"recommendation_score"`
}

// HistoricalPrice represents a single OHLCV data point
type HistoricalPrice struct {
	Date     time.Time `json:"date"`
	Open     float64   `json:"open"`
	High     float64   `json:"high"`
	Low      float64   `json:"low"`
	Close    float64   `json:"close"`
	Volume   int64     `json:"volume"`
	AdjClose float64   `json:"adj_close"`
}

// QuoteData represents basic quote information from Yahoo Finance
type QuoteData struct {
	Symbol             string   `json:"symbol"`
	RegularMarketPrice *float64 `json:"regularMarketPrice,omitempty"`
	CurrentPrice       *float64 `json:"currentPrice,omitempty"`
	Country            *string  `json:"country,omitempty"`
	FullExchangeName   *string  `json:"fullExchangeName,omitempty"`
	Industry           *string  `json:"industry,omitempty"`
	Sector             *string  `json:"sector,omitempty"`
	QuoteType          *string  `json:"quoteType,omitempty"`
	LongName           *string  `json:"longName,omitempty"`
	ShortName          *string  `json:"shortName,omitempty"`
}
