package optimization

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/rs/zerolog"
)

// PyPFOptClient is an HTTP client for calling the PyPortfolioOpt microservice.
type PyPFOptClient struct {
	baseURL string
	client  *http.Client
	log     zerolog.Logger
}

// NewPyPFOptClient creates a new PyPortfolioOpt client.
func NewPyPFOptClient(baseURL string, log zerolog.Logger) *PyPFOptClient {
	return &PyPFOptClient{
		baseURL: baseURL,
		client: &http.Client{
			Timeout: 60 * time.Second, // Optimization can take time
		},
		log: log.With().Str("client", "pypfopt").Logger(),
	}
}

// Request types (mirror Python microservice)

// OptimizeRequest represents a mean-variance optimization request.
type OptimizeRequest struct {
	ExpectedReturns   map[string]float64 `json:"expected_returns"`
	CovarianceMatrix  [][]float64        `json:"covariance_matrix"`
	Symbols           []string           `json:"symbols"`
	WeightBounds      [][2]float64       `json:"weight_bounds"`
	SectorConstraints []SectorConstraint `json:"sector_constraints"`
	Strategy          string             `json:"strategy"`
	TargetReturn      *float64           `json:"target_return,omitempty"`
	TargetVolatility  *float64           `json:"target_volatility,omitempty"`
}

// SectorConstraint represents sector allocation constraints.
type SectorConstraint struct {
	SectorMapper map[string]string  `json:"sector_mapper"`
	SectorLower  map[string]float64 `json:"sector_lower"`
	SectorUpper  map[string]float64 `json:"sector_upper"`
}

// HRPRequest represents a Hierarchical Risk Parity optimization request.
type HRPRequest struct {
	Returns TimeSeriesData `json:"returns"`
}

// TimeSeriesData represents time series data for returns or prices.
type TimeSeriesData struct {
	Dates []string             `json:"dates"`
	Data  map[string][]float64 `json:"data"`
}

// CovarianceRequest represents a covariance matrix calculation request.
type CovarianceRequest struct {
	Prices TimeSeriesData `json:"prices"`
}

// Response types

// ServiceResponse is the standard response format from the microservice.
type ServiceResponse struct {
	Success   bool                   `json:"success"`
	Data      map[string]interface{} `json:"data"`
	Error     *string                `json:"error"`
	Timestamp string                 `json:"timestamp"`
}

// OptimizationResult contains the result of an optimization.
type OptimizationResult struct {
	Weights            map[string]float64 `json:"weights"`
	StrategyUsed       string             `json:"strategy_used"`
	ConstraintLevel    *string            `json:"constraint_level"`
	Attempts           *int               `json:"attempts"`
	AchievedReturn     *float64           `json:"achieved_return"`
	AchievedVolatility *float64           `json:"achieved_volatility"`
}

// CovarianceResult contains the covariance matrix calculation result.
type CovarianceResult struct {
	CovarianceMatrix [][]float64 `json:"covariance_matrix"`
	Symbols          []string    `json:"symbols"`
}

// Public methods

// OptimizeProgressive calls the progressive optimization endpoint.
// This endpoint tries multiple strategies with constraint relaxation.
func (c *PyPFOptClient) OptimizeProgressive(req OptimizeRequest) (*OptimizationResult, error) {
	resp, err := c.post("/optimize/progressive", req)
	if err != nil {
		return nil, err
	}

	var result OptimizationResult
	if err := c.parseData(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse optimization result: %w", err)
	}

	return &result, nil
}

// OptimizeHRP calls the Hierarchical Risk Parity optimization endpoint.
func (c *PyPFOptClient) OptimizeHRP(req HRPRequest) (map[string]float64, error) {
	resp, err := c.post("/optimize/hrp", req)
	if err != nil {
		return nil, err
	}

	// Extract weights from response
	weightsData, ok := resp.Data["weights"]
	if !ok {
		return nil, fmt.Errorf("response missing weights field")
	}

	var weights map[string]float64
	if err := c.parseData(weightsData, &weights); err != nil {
		return nil, fmt.Errorf("failed to parse HRP weights: %w", err)
	}

	return weights, nil
}

// CalculateCovariance calls the covariance matrix calculation endpoint.
func (c *PyPFOptClient) CalculateCovariance(req CovarianceRequest) (*CovarianceResult, error) {
	resp, err := c.post("/risk-model/covariance", req)
	if err != nil {
		return nil, err
	}

	var result CovarianceResult
	if err := c.parseData(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse covariance result: %w", err)
	}

	return &result, nil
}

// Private helper methods

// post sends a POST request to the microservice.
func (c *PyPFOptClient) post(endpoint string, request interface{}) (*ServiceResponse, error) {
	url := c.baseURL + endpoint

	// Marshal request to JSON
	jsonData, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	c.log.Debug().
		Str("endpoint", endpoint).
		Msg("Calling PyPortfolioOpt service")

	// Create HTTP request
	httpReq, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	// Send request
	httpResp, err := c.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer httpResp.Body.Close()

	// Read response body
	body, err := io.ReadAll(httpResp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	// Parse response
	var resp ServiceResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	// Check for service-level error
	if !resp.Success {
		errorMsg := "unknown error"
		if resp.Error != nil {
			errorMsg = *resp.Error
		}
		return nil, fmt.Errorf("optimization failed: %s", errorMsg)
	}

	c.log.Debug().
		Str("endpoint", endpoint).
		Msg("PyPortfolioOpt service call successful")

	return &resp, nil
}

// parseData converts interface{} data to the target type.
func (c *PyPFOptClient) parseData(data interface{}, target interface{}) error {
	// Convert to JSON and back to handle type conversions
	jsonData, err := json.Marshal(data)
	if err != nil {
		return err
	}
	return json.Unmarshal(jsonData, target)
}
