package events

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestPlanGeneratedData tests PlanGeneratedData struct
func TestPlanGeneratedData(t *testing.T) {
	data := PlanGeneratedData{
		PortfolioHash: "test_hash_123",
		Steps:         5,
		EndScore:      85.5,
		Improvement:   10.2,
		Feasible:      true,
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "test_hash_123")
	assert.Contains(t, string(jsonData), "5")
	assert.Contains(t, string(jsonData), "85.5")
	assert.Contains(t, string(jsonData), "10.2")
	assert.Contains(t, string(jsonData), "true")

	// Test JSON unmarshaling
	var unmarshaled PlanGeneratedData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.PortfolioHash, unmarshaled.PortfolioHash)
	assert.Equal(t, data.Steps, unmarshaled.Steps)
	assert.Equal(t, data.EndScore, unmarshaled.EndScore)
	assert.Equal(t, data.Improvement, unmarshaled.Improvement)
	assert.Equal(t, data.Feasible, unmarshaled.Feasible)
}

// TestRecommendationsReadyData tests RecommendationsReadyData struct
func TestRecommendationsReadyData(t *testing.T) {
	data := RecommendationsReadyData{
		PortfolioHash: "test_hash_456",
		Count:         3,
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "test_hash_456")
	assert.Contains(t, string(jsonData), "3")

	// Test JSON unmarshaling
	var unmarshaled RecommendationsReadyData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.PortfolioHash, unmarshaled.PortfolioHash)
	assert.Equal(t, data.Count, unmarshaled.Count)
}

// TestPortfolioChangedData tests PortfolioChangedData struct
func TestPortfolioChangedData(t *testing.T) {
	data := PortfolioChangedData{
		SyncCompleted: true,
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "true")

	// Test JSON unmarshaling
	var unmarshaled PortfolioChangedData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.SyncCompleted, unmarshaled.SyncCompleted)
}

// TestPriceUpdatedData tests PriceUpdatedData struct
func TestPriceUpdatedData(t *testing.T) {
	data := PriceUpdatedData{
		PricesSynced: true,
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "true")

	// Test JSON unmarshaling
	var unmarshaled PriceUpdatedData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.PricesSynced, unmarshaled.PricesSynced)
}

// TestTradeExecutedData tests TradeExecutedData struct
func TestTradeExecutedData(t *testing.T) {
	data := TradeExecutedData{
		Symbol:   "AAPL",
		Side:     "BUY",
		Quantity: 10.0,
		Price:    150.0,
		OrderID:  "order_123",
		Source:   "autonomous",
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "AAPL")
	assert.Contains(t, string(jsonData), "BUY")
	assert.Contains(t, string(jsonData), "10")
	assert.Contains(t, string(jsonData), "150")
	assert.Contains(t, string(jsonData), "order_123")
	assert.Contains(t, string(jsonData), "autonomous")

	// Test JSON unmarshaling
	var unmarshaled TradeExecutedData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.Symbol, unmarshaled.Symbol)
	assert.Equal(t, data.Side, unmarshaled.Side)
	assert.Equal(t, data.Quantity, unmarshaled.Quantity)
	assert.Equal(t, data.Price, unmarshaled.Price)
	assert.Equal(t, data.OrderID, unmarshaled.OrderID)
	assert.Equal(t, data.Source, unmarshaled.Source)
}

// TestSecurityAddedData tests SecurityAddedData struct
func TestSecurityAddedData(t *testing.T) {
	data := SecurityAddedData{
		Symbol: "AAPL",
		ISIN:   "US0378331005",
		Name:   "Apple Inc.",
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "AAPL")
	assert.Contains(t, string(jsonData), "US0378331005")
	assert.Contains(t, string(jsonData), "Apple Inc.")

	// Test JSON unmarshaling
	var unmarshaled SecurityAddedData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.Symbol, unmarshaled.Symbol)
	assert.Equal(t, data.ISIN, unmarshaled.ISIN)
	assert.Equal(t, data.Name, unmarshaled.Name)
}

// TestSecuritySyncedData tests SecuritySyncedData struct
func TestSecuritySyncedData(t *testing.T) {
	price := 150.0
	data := SecuritySyncedData{
		Symbol: "AAPL",
		ISIN:   "US0378331005",
		Price:  &price,
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "AAPL")
	assert.Contains(t, string(jsonData), "US0378331005")
	assert.Contains(t, string(jsonData), "150")

	// Test JSON unmarshaling
	var unmarshaled SecuritySyncedData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.Symbol, unmarshaled.Symbol)
	assert.Equal(t, data.ISIN, unmarshaled.ISIN)
	if data.Price != nil {
		assert.NotNil(t, unmarshaled.Price)
		assert.Equal(t, *data.Price, *unmarshaled.Price)
	}
}

// TestScoreUpdatedData tests ScoreUpdatedData struct
func TestScoreUpdatedData(t *testing.T) {
	data := ScoreUpdatedData{
		Symbol:     "AAPL",
		ISIN:       "US0378331005",
		TotalScore: 85.5,
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "AAPL")
	assert.Contains(t, string(jsonData), "US0378331005")
	assert.Contains(t, string(jsonData), "85.5")

	// Test JSON unmarshaling
	var unmarshaled ScoreUpdatedData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.Symbol, unmarshaled.Symbol)
	assert.Equal(t, data.ISIN, unmarshaled.ISIN)
	assert.Equal(t, data.TotalScore, unmarshaled.TotalScore)
}

// TestSettingsChangedData tests SettingsChangedData struct
func TestSettingsChangedData(t *testing.T) {
	data := SettingsChangedData{
		Key:   "trading_mode",
		Value: "live",
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "trading_mode")
	assert.Contains(t, string(jsonData), "live")

	// Test JSON unmarshaling
	var unmarshaled SettingsChangedData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.Key, unmarshaled.Key)
	assert.Equal(t, data.Value, unmarshaled.Value)
}

// TestSystemStatusChangedData tests SystemStatusChangedData struct
func TestSystemStatusChangedData(t *testing.T) {
	data := SystemStatusChangedData{
		Status: "healthy",
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "healthy")

	// Test JSON unmarshaling
	var unmarshaled SystemStatusChangedData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.Status, unmarshaled.Status)
}

// TestTradernetStatusChangedData tests TradernetStatusChangedData struct
func TestTradernetStatusChangedData(t *testing.T) {
	data := TradernetStatusChangedData{
		Connected: true,
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "true")

	// Test JSON unmarshaling
	var unmarshaled TradernetStatusChangedData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.Connected, unmarshaled.Connected)
}

// TestMarketsStatusChangedData tests MarketsStatusChangedData struct
func TestMarketsStatusChangedData(t *testing.T) {
	data := MarketsStatusChangedData{
		OpenCount: 5,
		Timestamp: time.Now().Format(time.RFC3339),
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "5")

	// Test JSON unmarshaling
	var unmarshaled MarketsStatusChangedData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.OpenCount, unmarshaled.OpenCount)
	assert.Equal(t, data.Timestamp, unmarshaled.Timestamp)
}

// TestAllocationTargetsChangedData tests AllocationTargetsChangedData struct
func TestAllocationTargetsChangedData(t *testing.T) {
	data := AllocationTargetsChangedData{
		Type: "country",
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "country")

	// Test JSON unmarshaling
	var unmarshaled AllocationTargetsChangedData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.Type, unmarshaled.Type)
}

// TestPlannerConfigChangedData tests PlannerConfigChangedData struct
func TestPlannerConfigChangedData(t *testing.T) {
	data := PlannerConfigChangedData{
		ConfigID: 123,
		Action:   "updated",
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "123")
	assert.Contains(t, string(jsonData), "updated")

	// Test JSON unmarshaling
	var unmarshaled PlannerConfigChangedData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.ConfigID, unmarshaled.ConfigID)
	assert.Equal(t, data.Action, unmarshaled.Action)
}

// TestEventDataInterface tests that EventData can be used with different types
func TestEventDataInterface(t *testing.T) {
	// Test that different event data types can be marshaled
	testCases := []struct {
		name     string
		data     EventData
		contains []string
	}{
		{
			name: "PlanGeneratedData",
			data: &PlanGeneratedData{
				PortfolioHash: "test",
				Steps:         5,
			},
			contains: []string{"test", "5"},
		},
		{
			name: "TradeExecutedData",
			data: &TradeExecutedData{
				Symbol:   "AAPL",
				Quantity: 10.0,
			},
			contains: []string{"AAPL", "10"},
		},
		{
			name: "SecurityAddedData",
			data: &SecurityAddedData{
				Symbol: "MSFT",
				ISIN:   "US5949181045",
			},
			contains: []string{"MSFT", "US5949181045"},
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			jsonData, err := json.Marshal(tc.data)
			require.NoError(t, err)
			for _, substr := range tc.contains {
				assert.Contains(t, string(jsonData), substr)
			}
		})
	}
}
