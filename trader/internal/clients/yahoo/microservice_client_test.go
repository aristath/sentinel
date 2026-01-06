package yahoo

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestGetBatchQuotes_CallsCorrectEndpoint(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Setup HTTP test server to capture the request URL
	var capturedPath string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedPath = r.URL.Path
		// Return mock response matching FastAPI ServiceResponse format
		dataJSON, _ := json.Marshal(map[string]interface{}{
			"quotes": map[string]float64{"AAPL.US": 150.0, "MSFT.US": 380.0},
		})
		response := ServiceResponse{
			Success: true,
			Data:    json.RawMessage(dataJSON),
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := NewMicroserviceClient(server.URL, log)
	symbolOverrides := map[string]*string{}
	_, err := client.GetBatchQuotes(symbolOverrides)

	assert.NoError(t, err)
	assert.Equal(t, "/api/yfinance/api/quotes/batch", capturedPath, "Client should call /api/yfinance/api/quotes/batch endpoint")
}

func TestGetCurrentPrice_CallsCorrectEndpoint(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Setup HTTP test server to capture the request URL
	var capturedPath string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedPath = r.URL.Path
		// Return mock response
		dataJSON, _ := json.Marshal(map[string]interface{}{
			"symbol": "AAPL.US",
			"price":  150.0,
		})
		response := ServiceResponse{
			Success: true,
			Data:    json.RawMessage(dataJSON),
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := NewMicroserviceClient(server.URL, log)
	_, err := client.GetCurrentPrice("AAPL.US", nil, 3)

	assert.NoError(t, err)
	assert.Equal(t, "/api/yfinance/api/quotes/AAPL.US", capturedPath, "Client should call /api/yfinance/api/quotes/{symbol} endpoint")
}
