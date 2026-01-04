package display

// ClusterData represents a single security cluster in the portfolio display
type ClusterData struct {
	ClusterID    int     `json:"cluster_id"`    // 1-5 for top holdings, 0 for background
	Symbol       string  `json:"symbol"`        // Security symbol (empty for background)
	Pixels       int     `json:"pixels"`        // Number of pixels to display
	Brightness   int     `json:"brightness"`    // Brightness level (100-220)
	Clustering   int     `json:"clustering"`    // Clustering strength (1-10)
	Speed        int     `json:"speed"`         // Animation speed in ms
	CAGR         float64 `json:"cagr"`          // Security's CAGR (for reference)
	PortfolioPct float64 `json:"portfolio_pct"` // % of portfolio
}

// PortfolioDisplayState represents the complete portfolio visualization state
type PortfolioDisplayState struct {
	Mode     string        `json:"mode"`     // "PORTFOLIO"
	Clusters []ClusterData `json:"clusters"` // Top 5 clusters + background
	Metadata struct {
		PortfolioPerformance float64 `json:"portfolio_performance"` // Weighted performance
		PerformanceVsTarget  float64 `json:"performance_vs_target"` // Difference from target
		TotalPixels          int     `json:"total_pixels"`          // Total active pixels
	} `json:"metadata"`
}

// VisualParameters holds the calculated visual parameters for a cluster
type VisualParameters struct {
	Pixels     int
	Brightness int
	Clustering int
	Speed      int
}
