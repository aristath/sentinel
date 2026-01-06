package tradernet

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestGetPendingOrders_CallsCorrectEndpoint(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Setup HTTP test server to capture the request URL
	var capturedPath string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedPath = r.URL.Path
		// Return mock response matching FastAPI ServiceResponse format
		response := ServiceResponse{
			Success: true,
			Data:    json.RawMessage(`{"orders":[]}`),
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := NewClient(server.URL, log)
	_, err := client.GetPendingOrders()

	assert.NoError(t, err)
	assert.Equal(t, "/api/tradernet/api/trading/pending-orders", capturedPath, "Client should call /api/tradernet/api/trading/pending-orders endpoint")
}
