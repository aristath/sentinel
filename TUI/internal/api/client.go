package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"time"
)

type Client struct {
	baseURL    string
	httpClient *http.Client
}

func NewClient(baseURL string) *Client {
	return &Client{
		baseURL:    baseURL,
		httpClient: &http.Client{Timeout: 10 * time.Second},
	}
}

func (c *Client) SetBaseURL(baseURL string) {
	c.baseURL = baseURL
}

// Response types

type Health struct {
	TradingMode string `json:"trading_mode"`
}

type Portfolio struct {
	TotalValueEUR float64    `json:"total_value_eur"`
	TotalCashEUR  float64    `json:"total_cash_eur"`
	Positions     []Position `json:"positions"`
}

type Position struct {
	Symbol    string  `json:"symbol"`
	Name      string  `json:"name"`
	Quantity  float64 `json:"quantity"`
	ValueEUR  float64 `json:"value_eur"`
	ProfitPct float64 `json:"profit_pct"`
}

type PnLHistory struct {
	Snapshots []PnLSnapshot `json:"snapshots"`
	Summary   PnLSummary    `json:"summary"`
}

type PnLSnapshot struct {
	Date          string  `json:"date"`
	TotalValueEUR float64 `json:"total_value_eur"`
	PnLEUR        float64 `json:"pnl_eur"`
	PnLPct        float64 `json:"pnl_pct"`
}

type PnLSummary struct {
	PnLPercent float64 `json:"pnl_percent"`
}

type Recommendation struct {
	Symbol   string  `json:"symbol"`
	Action   string  `json:"action"`
	Quantity int     `json:"quantity"`
	Price    float64 `json:"price"`
	Reason   string  `json:"reason"`
}

type PricePoint struct {
	Date  string  `json:"date"`
	Close float64 `json:"close"`
}

type Security struct {
	Symbol            string       `json:"symbol"`
	Name              string       `json:"name"`
	ValueEUR          float64      `json:"value_eur"`
	ProfitPct         float64      `json:"profit_pct"`
	HasPosition       bool         `json:"has_position"`
	PlannerScore      float64      `json:"planner_score"`
	Quantity          float64      `json:"quantity"`
	AvgCost           float64      `json:"avg_cost"`
	CurrentPrice      float64      `json:"current_price"`
	ProfitValueEUR    float64      `json:"profit_value_eur"`
	CurrentAllocation float64      `json:"current_allocation"`
	TargetAllocation  float64      `json:"target_allocation"`
	Score             float64      `json:"score"`
	ExpectedReturn    float64      `json:"expected_return"`
	Geography         string       `json:"geography"`
	Industry          string       `json:"industry"`
	Currency          string       `json:"currency"`
	Prices            []PricePoint `json:"prices"`
}

// Internal helpers

func (c *Client) get(path string, params url.Values, target any) error {
	u := c.baseURL + path
	if params != nil {
		u += "?" + params.Encode()
	}
	resp, err := c.httpClient.Get(u)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("API returned %d", resp.StatusCode)
	}
	return json.NewDecoder(resp.Body).Decode(target)
}

// Endpoints

func (c *Client) Health() (Health, error) {
	var h Health
	return h, c.get("/api/health", nil, &h)
}

func (c *Client) Portfolio() (Portfolio, error) {
	var p Portfolio
	return p, c.get("/api/portfolio", nil, &p)
}

func (c *Client) PnLHistory(period string) (PnLHistory, error) {
	var h PnLHistory
	return h, c.get("/api/portfolio/pnl-history", url.Values{"period": {period}}, &h)
}

func (c *Client) Recommendations() ([]Recommendation, error) {
	var resp struct {
		Recommendations []Recommendation `json:"recommendations"`
	}
	err := c.get("/api/planner/recommendations", nil, &resp)
	return resp.Recommendations, err
}

func (c *Client) Unified() ([]Security, error) {
	var s []Security
	return s, c.get("/api/unified", nil, &s)
}
