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
	now := time.Now().Format(time.RFC3339)
	data := MarketsStatusChangedData{
		Markets: map[string]MarketStatusData{
			"XNAS": {
				Name:      "NASDAQ",
				Code:      "XNAS",
				Status:    "open",
				OpenTime:  "09:30",
				CloseTime: "16:00",
				Date:      "2024-01-09",
				UpdatedAt: now,
			},
			"XNYS": {
				Name:      "NYSE",
				Code:      "XNYS",
				Status:    "closed",
				OpenTime:  "09:30",
				CloseTime: "16:00",
				Date:      "2024-01-09",
				UpdatedAt: now,
			},
		},
		OpenCount:   1,
		ClosedCount: 1,
		LastUpdated: now,
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "XNAS")
	assert.Contains(t, string(jsonData), "NASDAQ")

	// Test JSON unmarshaling
	var unmarshaled MarketsStatusChangedData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.OpenCount, unmarshaled.OpenCount)
	assert.Equal(t, data.ClosedCount, unmarshaled.ClosedCount)
	assert.Equal(t, data.LastUpdated, unmarshaled.LastUpdated)
	assert.Equal(t, 2, len(unmarshaled.Markets))
	assert.Equal(t, "NASDAQ", unmarshaled.Markets["XNAS"].Name)
	assert.Equal(t, "open", unmarshaled.Markets["XNAS"].Status)
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

// TestJobProgressInfo tests JobProgressInfo struct
func TestJobProgressInfo(t *testing.T) {
	progress := JobProgressInfo{
		Current: 45,
		Total:   100,
		Message: "Processing items",
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(progress)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "45")
	assert.Contains(t, string(jsonData), "100")
	assert.Contains(t, string(jsonData), "Processing items")

	// Test JSON unmarshaling
	var unmarshaled JobProgressInfo
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, progress.Current, unmarshaled.Current)
	assert.Equal(t, progress.Total, unmarshaled.Total)
	assert.Equal(t, progress.Message, unmarshaled.Message)
}

// TestJobProgressInfo_WithHierarchicalProgress tests JobProgressInfo with Phase, SubPhase, Details
func TestJobProgressInfo_WithHierarchicalProgress(t *testing.T) {
	progress := JobProgressInfo{
		Current:  847,
		Total:    2500,
		Message:  "Evaluating sequences",
		Phase:    "sequence_evaluation",
		SubPhase: "batch_1",
		Details: map[string]interface{}{
			"workers_active":       4,
			"feasible_count":       823,
			"infeasible_count":     24,
			"best_score":           0.847,
			"avg_score":            0.612,
			"sequences_per_second": 520.5,
			"elapsed_ms":           1632,
			"memory_alloc_mb":      45.2,
		},
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(progress)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), `"phase":"sequence_evaluation"`)
	assert.Contains(t, string(jsonData), `"sub_phase":"batch_1"`)
	assert.Contains(t, string(jsonData), `"workers_active"`)
	assert.Contains(t, string(jsonData), `"feasible_count"`)
	assert.Contains(t, string(jsonData), `"best_score"`)

	// Test JSON unmarshaling
	var unmarshaled JobProgressInfo
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, progress.Current, unmarshaled.Current)
	assert.Equal(t, progress.Total, unmarshaled.Total)
	assert.Equal(t, progress.Message, unmarshaled.Message)
	assert.Equal(t, progress.Phase, unmarshaled.Phase)
	assert.Equal(t, progress.SubPhase, unmarshaled.SubPhase)
	assert.NotNil(t, unmarshaled.Details)

	// Verify specific details - JSON numbers unmarshal as float64
	assert.Equal(t, float64(4), unmarshaled.Details["workers_active"])
	assert.Equal(t, float64(823), unmarshaled.Details["feasible_count"])
	assert.Equal(t, float64(24), unmarshaled.Details["infeasible_count"])
	assert.Equal(t, 0.847, unmarshaled.Details["best_score"])
	assert.Equal(t, 520.5, unmarshaled.Details["sequences_per_second"])
}

// TestJobProgressInfo_WithPhaseOnly tests JobProgressInfo with just Phase (no SubPhase or Details)
func TestJobProgressInfo_WithPhaseOnly(t *testing.T) {
	progress := JobProgressInfo{
		Current: 3,
		Total:   6,
		Message: "Running profit_taking calculator",
		Phase:   "opportunity_identification",
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(progress)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), `"phase":"opportunity_identification"`)
	// SubPhase and Details should be omitted when empty
	assert.NotContains(t, string(jsonData), `"sub_phase"`)
	assert.NotContains(t, string(jsonData), `"details"`)

	// Test JSON unmarshaling
	var unmarshaled JobProgressInfo
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, progress.Phase, unmarshaled.Phase)
	assert.Equal(t, "", unmarshaled.SubPhase)
	assert.Nil(t, unmarshaled.Details)
}

// TestJobProgressInfo_SequenceGeneration tests progress during sequence generation
func TestJobProgressInfo_SequenceGeneration(t *testing.T) {
	progress := JobProgressInfo{
		Current:  3,
		Total:    10,
		Message:  "Generating depth 3/10 sequences",
		Phase:    "sequence_generation",
		SubPhase: "depth_3",
		Details: map[string]interface{}{
			"candidates_count":       15,
			"current_depth":          3,
			"combinations_at_depth":  455,
			"combinations_processed": 230,
			"sequences_generated":    1234,
			"duplicates_removed":     89,
			"infeasible_pruned":      456,
		},
	}

	// Test JSON round-trip
	jsonData, err := json.Marshal(progress)
	require.NoError(t, err)

	var unmarshaled JobProgressInfo
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)

	assert.Equal(t, "sequence_generation", unmarshaled.Phase)
	assert.Equal(t, "depth_3", unmarshaled.SubPhase)
	assert.Equal(t, float64(15), unmarshaled.Details["candidates_count"])
	assert.Equal(t, float64(1234), unmarshaled.Details["sequences_generated"])
}

// TestJobProgressInfo_OpportunityIdentification tests progress during opportunity identification
func TestJobProgressInfo_OpportunityIdentification(t *testing.T) {
	progress := JobProgressInfo{
		Current:  2,
		Total:    6,
		Message:  "Running averaging_down calculator",
		Phase:    "opportunity_identification",
		SubPhase: "averaging_down",
		Details: map[string]interface{}{
			"calculators_total":  6,
			"calculators_done":   1,
			"candidates_so_far":  3,
			"filtered_so_far":    12,
			"current_calculator": "averaging_down",
		},
	}

	// Test JSON round-trip
	jsonData, err := json.Marshal(progress)
	require.NoError(t, err)

	var unmarshaled JobProgressInfo
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)

	assert.Equal(t, "opportunity_identification", unmarshaled.Phase)
	assert.Equal(t, "averaging_down", unmarshaled.SubPhase)
	assert.Equal(t, "averaging_down", unmarshaled.Details["current_calculator"])
}

// TestJobStatusData tests JobStatusData struct
func TestJobStatusData(t *testing.T) {
	now := time.Now()
	progress := &JobProgressInfo{
		Current: 5,
		Total:   10,
		Message: "Step 5 of 10",
	}

	data := JobStatusData{
		JobID:       "job_123",
		JobType:     "planner_batch",
		Status:      "progress",
		Description: "Generating trading recommendations",
		Progress:    progress,
		Duration:    15.5,
		Metadata: map[string]interface{}{
			"step": "optimizer",
		},
		Timestamp: now,
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "job_123")
	assert.Contains(t, string(jsonData), "planner_batch")
	assert.Contains(t, string(jsonData), "progress")
	assert.Contains(t, string(jsonData), "Generating trading recommendations")
	assert.Contains(t, string(jsonData), "5")
	assert.Contains(t, string(jsonData), "10")
	assert.Contains(t, string(jsonData), "15.5")

	// Test JSON unmarshaling
	var unmarshaled JobStatusData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.JobID, unmarshaled.JobID)
	assert.Equal(t, data.JobType, unmarshaled.JobType)
	assert.Equal(t, data.Status, unmarshaled.Status)
	assert.Equal(t, data.Description, unmarshaled.Description)
	assert.Equal(t, data.Duration, unmarshaled.Duration)
	require.NotNil(t, unmarshaled.Progress)
	assert.Equal(t, progress.Current, unmarshaled.Progress.Current)
	assert.Equal(t, progress.Total, unmarshaled.Progress.Total)
	assert.Equal(t, progress.Message, unmarshaled.Progress.Message)
}

// TestJobStatusData_EventType tests EventType() returns correct type based on Status
func TestJobStatusData_EventType(t *testing.T) {
	testCases := []struct {
		status       string
		expectedType EventType
	}{
		{"started", JobStarted},
		{"progress", JobProgress},
		{"completed", JobCompleted},
		{"failed", JobFailed},
		{"unknown", JobStarted}, // Fallback to JobStarted
	}

	for _, tc := range testCases {
		t.Run(tc.status, func(t *testing.T) {
			data := &JobStatusData{Status: tc.status}
			assert.Equal(t, tc.expectedType, data.EventType())
		})
	}
}

// TestJobStatusData_WithError tests JobStatusData with error field
func TestJobStatusData_WithError(t *testing.T) {
	data := JobStatusData{
		JobID:       "job_456",
		JobType:     "sync_cycle",
		Status:      "failed",
		Description: "Syncing all data from broker",
		Error:       "connection timeout",
		Duration:    5.2,
		Timestamp:   time.Now(),
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "job_456")
	assert.Contains(t, string(jsonData), "failed")
	assert.Contains(t, string(jsonData), "connection timeout")

	// Test JSON unmarshaling
	var unmarshaled JobStatusData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.JobID, unmarshaled.JobID)
	assert.Equal(t, data.Status, unmarshaled.Status)
	assert.Equal(t, data.Error, unmarshaled.Error)
}

// TestJobStatusData_WithoutProgress tests JobStatusData with nil progress
func TestJobStatusData_WithoutProgress(t *testing.T) {
	data := JobStatusData{
		JobID:       "job_789",
		JobType:     "hourly_backup",
		Status:      "started",
		Description: "Creating hourly backup",
		Progress:    nil,
		Timestamp:   time.Now(),
	}

	// Test JSON marshaling
	jsonData, err := json.Marshal(data)
	require.NoError(t, err)
	assert.Contains(t, string(jsonData), "job_789")
	assert.Contains(t, string(jsonData), "started")

	// Test JSON unmarshaling
	var unmarshaled JobStatusData
	err = json.Unmarshal(jsonData, &unmarshaled)
	require.NoError(t, err)
	assert.Equal(t, data.JobID, unmarshaled.JobID)
	assert.Nil(t, unmarshaled.Progress)
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
		{
			name: "JobStatusData",
			data: &JobStatusData{
				JobID:       "test_job",
				JobType:     "test_type",
				Status:      "started",
				Description: "Test job",
			},
			contains: []string{"test_job", "test_type", "started"},
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
