package filters

import (
	"testing"

	"github.com/aristath/arduino-trader/internal/modules/optimization"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// mockRiskBuilder implements a mock RiskModelBuilder for testing
type mockRiskBuilder struct {
	correlations []optimization.CorrelationPair
	err          error
}

func (m *mockRiskBuilder) BuildCovarianceMatrix(symbols []string, lookbackDays int) ([][]float64, map[string][]float64, []optimization.CorrelationPair, error) {
	return nil, nil, m.correlations, m.err
}

func TestCorrelationAwareFilter_NoCorrleationData(t *testing.T) {
	log := zerolog.Nop()
	mockBuilder := &mockRiskBuilder{
		correlations: []optimization.CorrelationPair{},
		err:          nil,
	}

	filter := NewCorrelationAwareFilter(log, mockBuilder)

	sequences := []domain.ActionSequence{
		{
			SequenceHash: "seq1",
			Actions: []domain.ActionCandidate{
				{Side: "BUY", Symbol: "AAPL"},
				{Side: "BUY", Symbol: "MSFT"},
			},
		},
	}

	result, err := filter.Filter(sequences, map[string]interface{}{})

	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}

	if len(result) != 1 {
		t.Fatalf("Expected 1 sequence, got %d", len(result))
	}
}

func TestCorrelationAwareFilter_NoCorrelatedSymbols(t *testing.T) {
	log := zerolog.Nop()

	// Mock correlations below threshold
	mockBuilder := &mockRiskBuilder{
		correlations: []optimization.CorrelationPair{
			{Symbol1: "AAPL", Symbol2: "MSFT", Correlation: 0.5},
		},
		err: nil,
	}

	filter := NewCorrelationAwareFilter(log, mockBuilder)

	sequences := []domain.ActionSequence{
		{
			SequenceHash: "seq1",
			Actions: []domain.ActionCandidate{
				{Side: "BUY", Symbol: "AAPL"},
				{Side: "BUY", Symbol: "MSFT"},
			},
		},
	}

	result, err := filter.Filter(sequences, map[string]interface{}{
		"correlation_threshold": 0.7,
	})

	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}

	if len(result) != 1 {
		t.Fatalf("Expected 1 sequence (below threshold), got %d", len(result))
	}
}

func TestCorrelationAwareFilter_HighCorrelation(t *testing.T) {
	log := zerolog.Nop()

	// Mock high correlation
	mockBuilder := &mockRiskBuilder{
		correlations: []optimization.CorrelationPair{
			{Symbol1: "AAPL", Symbol2: "MSFT", Correlation: 0.9},
		},
		err: nil,
	}

	filter := NewCorrelationAwareFilter(log, mockBuilder)

	sequences := []domain.ActionSequence{
		{
			SequenceHash: "seq1",
			Actions: []domain.ActionCandidate{
				{Side: "BUY", Symbol: "AAPL"},
				{Side: "BUY", Symbol: "MSFT"},
			},
		},
		{
			SequenceHash: "seq2",
			Actions: []domain.ActionCandidate{
				{Side: "BUY", Symbol: "GOOGL"},
			},
		},
	}

	result, err := filter.Filter(sequences, map[string]interface{}{
		"correlation_threshold": 0.7,
	})

	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}

	// Should filter out seq1 (high correlation), keep seq2
	if len(result) != 1 {
		t.Fatalf("Expected 1 sequence (filtered), got %d", len(result))
	}

	if result[0].SequenceHash != "seq2" {
		t.Fatalf("Expected seq2 to remain, got %s", result[0].SequenceHash)
	}
}

func TestCorrelationAwareFilter_OnlyBUYActionsChecked(t *testing.T) {
	log := zerolog.Nop()

	// High correlation between AAPL and MSFT
	mockBuilder := &mockRiskBuilder{
		correlations: []optimization.CorrelationPair{
			{Symbol1: "AAPL", Symbol2: "MSFT", Correlation: 0.9},
		},
		err: nil,
	}

	filter := NewCorrelationAwareFilter(log, mockBuilder)

	sequences := []domain.ActionSequence{
		{
			SequenceHash: "seq1",
			Actions: []domain.ActionCandidate{
				{Side: "BUY", Symbol: "AAPL"},
				{Side: "SELL", Symbol: "MSFT"}, // SELL should be ignored
			},
		},
	}

	result, err := filter.Filter(sequences, map[string]interface{}{
		"correlation_threshold": 0.7,
	})

	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}

	// Should keep sequence because only one BUY action
	if len(result) != 1 {
		t.Fatalf("Expected 1 sequence (SELL ignored), got %d", len(result))
	}
}

func TestCorrelationAwareFilter_SingleBUYPerSequence(t *testing.T) {
	log := zerolog.Nop()

	mockBuilder := &mockRiskBuilder{
		correlations: []optimization.CorrelationPair{
			{Symbol1: "AAPL", Symbol2: "MSFT", Correlation: 0.9},
		},
		err: nil,
	}

	filter := NewCorrelationAwareFilter(log, mockBuilder)

	sequences := []domain.ActionSequence{
		{
			SequenceHash: "seq1",
			Actions: []domain.ActionCandidate{
				{Side: "BUY", Symbol: "AAPL"},
			},
		},
	}

	result, err := filter.Filter(sequences, map[string]interface{}{
		"correlation_threshold": 0.7,
	})

	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}

	// Should keep sequence (can't correlate single symbol)
	if len(result) != 1 {
		t.Fatalf("Expected 1 sequence (single BUY), got %d", len(result))
	}
}

func TestCorrelationAwareFilter_PreProvidedMatrix(t *testing.T) {
	log := zerolog.Nop()

	// Mock builder should not be called
	mockBuilder := &mockRiskBuilder{
		correlations: nil,
		err:          nil,
	}

	filter := NewCorrelationAwareFilter(log, mockBuilder)

	// Pre-provide correlation matrix
	correlationMatrix := map[string]float64{
		"AAPL:MSFT": 0.9,
		"MSFT:AAPL": 0.9,
	}

	sequences := []domain.ActionSequence{
		{
			SequenceHash: "seq1",
			Actions: []domain.ActionCandidate{
				{Side: "BUY", Symbol: "AAPL"},
				{Side: "BUY", Symbol: "MSFT"},
			},
		},
	}

	result, err := filter.Filter(sequences, map[string]interface{}{
		"correlation_threshold": 0.7,
		"correlation_matrix":    correlationMatrix,
	})

	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}

	// Should filter out based on pre-provided matrix
	if len(result) != 0 {
		t.Fatalf("Expected 0 sequences (pre-provided matrix), got %d", len(result))
	}
}

func TestCorrelationAwareFilter_SymmetricKeys(t *testing.T) {
	log := zerolog.Nop()

	mockBuilder := &mockRiskBuilder{
		correlations: []optimization.CorrelationPair{
			{Symbol1: "AAPL", Symbol2: "MSFT", Correlation: 0.9},
		},
		err: nil,
	}

	filter := NewCorrelationAwareFilter(log, mockBuilder)

	// Test with symbols in different order
	sequences := []domain.ActionSequence{
		{
			SequenceHash: "seq1",
			Actions: []domain.ActionCandidate{
				{Side: "BUY", Symbol: "MSFT"}, // Reversed order
				{Side: "BUY", Symbol: "AAPL"},
			},
		},
	}

	result, err := filter.Filter(sequences, map[string]interface{}{
		"correlation_threshold": 0.7,
	})

	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}

	// Should still filter (symmetric lookup)
	if len(result) != 0 {
		t.Fatalf("Expected 0 sequences (symmetric keys), got %d", len(result))
	}
}

func TestCorrelationAwareFilter_NegativeCorrelation(t *testing.T) {
	log := zerolog.Nop()

	// Negative correlation (inverse relationship)
	mockBuilder := &mockRiskBuilder{
		correlations: []optimization.CorrelationPair{
			{Symbol1: "AAPL", Symbol2: "MSFT", Correlation: -0.9},
		},
		err: nil,
	}

	filter := NewCorrelationAwareFilter(log, mockBuilder)

	sequences := []domain.ActionSequence{
		{
			SequenceHash: "seq1",
			Actions: []domain.ActionCandidate{
				{Side: "BUY", Symbol: "AAPL"},
				{Side: "BUY", Symbol: "MSFT"},
			},
		},
	}

	result, err := filter.Filter(sequences, map[string]interface{}{
		"correlation_threshold": 0.7,
	})

	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}

	// Should filter (absolute value check)
	if len(result) != 0 {
		t.Fatalf("Expected 0 sequences (negative correlation), got %d", len(result))
	}
}

func TestCorrelationAwareFilter_EmptySequences(t *testing.T) {
	log := zerolog.Nop()

	mockBuilder := &mockRiskBuilder{
		correlations: []optimization.CorrelationPair{},
		err:          nil,
	}

	filter := NewCorrelationAwareFilter(log, mockBuilder)

	result, err := filter.Filter([]domain.ActionSequence{}, map[string]interface{}{})

	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}

	if len(result) != 0 {
		t.Fatalf("Expected 0 sequences (empty input), got %d", len(result))
	}
}

func TestBuildCorrelationMap(t *testing.T) {
	pairs := []optimization.CorrelationPair{
		{Symbol1: "AAPL", Symbol2: "MSFT", Correlation: 0.85},
		{Symbol1: "GOOGL", Symbol2: "AMZN", Correlation: 0.75},
	}

	correlationMap := optimization.BuildCorrelationMap(pairs)

	// Check bidirectional storage
	if correlationMap["AAPL:MSFT"] != 0.85 {
		t.Errorf("Expected 0.85 for AAPL:MSFT, got %f", correlationMap["AAPL:MSFT"])
	}

	if correlationMap["MSFT:AAPL"] != 0.85 {
		t.Errorf("Expected 0.85 for MSFT:AAPL, got %f", correlationMap["MSFT:AAPL"])
	}

	if correlationMap["GOOGL:AMZN"] != 0.75 {
		t.Errorf("Expected 0.75 for GOOGL:AMZN, got %f", correlationMap["GOOGL:AMZN"])
	}

	if correlationMap["AMZN:GOOGL"] != 0.75 {
		t.Errorf("Expected 0.75 for AMZN:GOOGL, got %f", correlationMap["AMZN:GOOGL"])
	}

	// Should have 4 entries (2 pairs * 2 directions)
	if len(correlationMap) != 4 {
		t.Errorf("Expected 4 entries, got %d", len(correlationMap))
	}
}
