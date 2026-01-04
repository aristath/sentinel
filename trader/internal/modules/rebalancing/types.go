package rebalancing

// RebalanceRecommendation represents a trade recommendation from the rebalancing service
type RebalanceRecommendation struct {
	Symbol         string  `json:"symbol"`
	Name           string  `json:"name"`
	Side           string  `json:"side"` // "BUY" or "SELL"
	Quantity       int     `json:"quantity"`
	EstimatedPrice float64 `json:"estimated_price"`
	EstimatedValue float64 `json:"estimated_value"`
	Currency       string  `json:"currency"`
	Reason         string  `json:"reason"`
	Priority       float64 `json:"priority"` // Lower = higher priority
}
