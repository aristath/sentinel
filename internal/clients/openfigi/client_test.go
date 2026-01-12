package openfigi

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewClient(t *testing.T) {
	client := NewClient("", nil, zerolog.Nop())
	assert.NotNil(t, client)
	assert.Empty(t, client.apiKey)

	clientWithKey := NewClient("test-api-key", nil, zerolog.Nop())
	assert.Equal(t, "test-api-key", clientWithKey.apiKey)
}

func TestLookupISIN_Success(t *testing.T) {
	// Mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "POST", r.Method)
		assert.Equal(t, "/mapping", r.URL.Path)
		assert.Equal(t, "application/json", r.Header.Get("Content-Type"))

		// Check request body
		var req []MappingRequest
		err := json.NewDecoder(r.Body).Decode(&req)
		require.NoError(t, err)
		require.Len(t, req, 1)
		assert.Equal(t, "ID_ISIN", req[0].IDType)
		assert.Equal(t, "US0378331005", req[0].IDValue)

		// Return mock response
		resp := []MappingResponse{
			{
				Data: []MappingResult{
					{
						FIGI:         "BBG000B9XRY4",
						Ticker:       "AAPL",
						ExchCode:     "US",
						Name:         "APPLE INC",
						MarketSector: "Equity",
						SecurityType: "Common Stock",
					},
				},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	client := NewClient("", nil, zerolog.Nop())
	client.baseURL = server.URL

	results, err := client.LookupISIN("US0378331005")
	require.NoError(t, err)
	require.Len(t, results, 1)

	assert.Equal(t, "BBG000B9XRY4", results[0].FIGI)
	assert.Equal(t, "AAPL", results[0].Ticker)
	assert.Equal(t, "US", results[0].ExchCode)
	assert.Equal(t, "APPLE INC", results[0].Name)
	assert.Equal(t, "Equity", results[0].MarketSector)
}

func TestLookupISIN_MultipleResults(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := []MappingResponse{
			{
				Data: []MappingResult{
					{FIGI: "BBG000B9XRY4", Ticker: "AAPL", ExchCode: "US"},
					{FIGI: "BBG0020P10C5", Ticker: "AAPL", ExchCode: "LN"},
				},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	client := NewClient("", nil, zerolog.Nop())
	client.baseURL = server.URL

	results, err := client.LookupISIN("US0378331005")
	require.NoError(t, err)
	require.Len(t, results, 2)

	assert.Equal(t, "US", results[0].ExchCode)
	assert.Equal(t, "LN", results[1].ExchCode)
}

func TestLookupISIN_NoResults(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := []MappingResponse{
			{
				Data:    nil,
				Warning: "No match found for the specified ISIN",
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	client := NewClient("", nil, zerolog.Nop())
	client.baseURL = server.URL

	results, err := client.LookupISIN("INVALID123456")
	require.NoError(t, err)
	assert.Empty(t, results)
}

func TestLookupISINForExchange(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := []MappingResponse{
			{
				Data: []MappingResult{
					{FIGI: "BBG000B9XRY4", Ticker: "AAPL", ExchCode: "US"},
					{FIGI: "BBG0020P10C5", Ticker: "AAPL", ExchCode: "LN"},
				},
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	client := NewClient("", nil, zerolog.Nop())
	client.baseURL = server.URL

	result, err := client.LookupISINForExchange("US0378331005", "US")
	require.NoError(t, err)
	require.NotNil(t, result)

	assert.Equal(t, "AAPL", result.Ticker)
	assert.Equal(t, "US", result.ExchCode)
}

func TestLookupISINForExchange_NotFound(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := []MappingResponse{{Data: nil}}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	client := NewClient("", nil, zerolog.Nop())
	client.baseURL = server.URL

	result, err := client.LookupISINForExchange("US0378331005", "XX")
	require.NoError(t, err)
	assert.Nil(t, result)
}

func TestBatchLookup(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var req []MappingRequest
		json.NewDecoder(r.Body).Decode(&req)

		// Return results for each ISIN
		resp := make([]MappingResponse, len(req))
		for i, mreq := range req {
			resp[i] = MappingResponse{
				Data: []MappingResult{
					{FIGI: "BBG" + mreq.IDValue[:6], Ticker: "TICK" + string(rune('A'+i)), ExchCode: "US"},
				},
			}
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	client := NewClient("", nil, zerolog.Nop())
	client.baseURL = server.URL

	isins := []string{"US0378331005", "US5949181045", "US88160R1014"}
	results, err := client.BatchLookup(isins)
	require.NoError(t, err)
	require.Len(t, results, 3)

	assert.Contains(t, results, "US0378331005")
	assert.Contains(t, results, "US5949181045")
	assert.Contains(t, results, "US88160R1014")
}

func TestClient_WithAPIKey(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Check for API key header
		apiKey := r.Header.Get("X-OPENFIGI-APIKEY")
		assert.Equal(t, "my-api-key", apiKey)

		resp := []MappingResponse{{Data: []MappingResult{{Ticker: "TEST"}}}}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	client := NewClient("my-api-key", nil, zerolog.Nop())
	client.baseURL = server.URL

	_, err := client.LookupISIN("US0378331005")
	require.NoError(t, err)
}

func TestClient_HTTPError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("Internal Server Error"))
	}))
	defer server.Close()

	client := NewClient("", nil, zerolog.Nop())
	client.baseURL = server.URL

	_, err := client.LookupISIN("US0378331005")
	assert.Error(t, err)
}

func TestClient_InvalidJSON(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte("invalid json"))
	}))
	defer server.Close()

	client := NewClient("", nil, zerolog.Nop())
	client.baseURL = server.URL

	_, err := client.LookupISIN("US0378331005")
	assert.Error(t, err)
}

func TestNoCaching_WithNilRepo(t *testing.T) {
	// Without a cache repo, each call should hit the API
	callCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callCount++
		resp := []MappingResponse{{Data: []MappingResult{{Ticker: "AAPL", ExchCode: "US"}}}}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	client := NewClient("", nil, zerolog.Nop())
	client.baseURL = server.URL

	// First call
	_, err := client.LookupISIN("US0378331005")
	require.NoError(t, err)
	assert.Equal(t, 1, callCount)

	// Second call - should also hit API since no cache repo
	_, err = client.LookupISIN("US0378331005")
	require.NoError(t, err)
	assert.Equal(t, 2, callCount)
}

func TestMappingResult_Fields(t *testing.T) {
	result := MappingResult{
		FIGI:            "BBG000B9XRY4",
		Ticker:          "AAPL",
		ExchCode:        "US",
		Name:            "APPLE INC",
		MarketSector:    "Equity",
		SecurityType:    "Common Stock",
		CompositeFIGI:   "BBG000B9XRY4",
		ShareClassFIGI:  "BBG001S5N8V8",
		UniqueID:        "EQ0010169500001000",
		SecurityType2:   "Common Stock",
		MarketSectorDes: "Equity",
	}

	assert.Equal(t, "BBG000B9XRY4", result.FIGI)
	assert.Equal(t, "AAPL", result.Ticker)
	assert.Equal(t, "US", result.ExchCode)
	assert.Equal(t, "APPLE INC", result.Name)
	assert.Equal(t, "Equity", result.MarketSector)
	assert.Equal(t, "BBG000B9XRY4", result.CompositeFIGI)
	assert.Equal(t, "BBG001S5N8V8", result.ShareClassFIGI)
	assert.Equal(t, "EQ0010169500001000", result.UniqueID)
	assert.Equal(t, "Common Stock", result.SecurityType2)
	assert.Equal(t, "Equity", result.MarketSectorDes)
	assert.Equal(t, "Common Stock", result.SecurityType)
}
