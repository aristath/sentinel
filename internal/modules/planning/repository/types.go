package repository

import "time"

// SequenceRecord represents a sequence in the repository.
type SequenceRecord struct {
	SequenceHash  string
	PortfolioHash string
	SequenceJSON  string // JSON serialized ActionSequence
	PatternType   string
	Depth         int
	Priority      float64
	Completed     bool
	EvaluatedAt   *time.Time // Nullable
	CreatedAt     time.Time
}

// EvaluationRecord represents an evaluation in the repository.
type EvaluationRecord struct {
	SequenceHash            string
	PortfolioHash           string
	EndScore                float64
	BreakdownJSON           string // JSON serialized score breakdown
	EndCash                 float64
	EndContextPositionsJSON string // JSON serialized positions
	DiversificationScore    float64
	TotalValue              float64
	EvaluatedAt             time.Time
}

// BestResultRecord represents the best result in the repository.
type BestResultRecord struct {
	PortfolioHash string
	SequenceHash  string
	PlanData      string // JSON serialized HolisticPlan
	Score         float64
	CreatedAt     time.Time
	UpdatedAt     time.Time
}
