package optimization

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestOptimizeProgressive_CallsCorrectEndpoint(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Setup HTTP test server to capture the request URL
	var capturedPath string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedPath = r.URL.Path
		// Return mock response matching FastAPI ServiceResponse format
		response := ServiceResponse{
			Success: true,
			Data: map[string]interface{}{
				"weights":          map[string]float64{"AAPL": 0.5, "MSFT": 0.5},
				"strategy_used":    "min_volatility",
				"constraint_level": "full",
				"attempts":         1,
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := NewPyPFOptClient(server.URL, log)
	req := OptimizeRequest{
		ExpectedReturns:  map[string]float64{"AAPL": 0.12, "MSFT": 0.10},
		CovarianceMatrix: [][]float64{{0.04, 0.02}, {0.02, 0.05}},
		Symbols:          []string{"AAPL", "MSFT"},
		WeightBounds:     [][2]float64{{0.02, 0.50}, {0.02, 0.50}},
		Strategy:         "min_volatility",
	}
	_, err := client.OptimizeProgressive(req)

	assert.NoError(t, err)
	assert.Equal(t, "/api/pypfopt/optimize/progressive", capturedPath, "Client should call /api/pypfopt/optimize/progressive endpoint")
}

func TestCalculateCovariance_CallsCorrectEndpoint(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Setup HTTP test server to capture the request URL
	var capturedPath string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedPath = r.URL.Path
		// Return mock response
		response := ServiceResponse{
			Success: true,
			Data: map[string]interface{}{
				"covariance_matrix": [][]float64{{0.04, 0.02}, {0.02, 0.05}},
				"symbols":           []string{"AAPL", "MSFT"},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := NewPyPFOptClient(server.URL, log)
	req := CovarianceRequest{
		Prices: TimeSeriesData{
			Dates: []string{"2025-01-01", "2025-01-02"},
			Data:  map[string][]float64{"AAPL": {150.0, 151.0}, "MSFT": {380.0, 382.0}},
		},
	}
	_, err := client.CalculateCovariance(req)

	assert.NoError(t, err)
	assert.Equal(t, "/api/pypfopt/risk-model/covariance", capturedPath, "Client should call /api/pypfopt/risk-model/covariance endpoint")
}
