package repository

import (
	"github.com/aristath/sentinel/internal/modules/planning/domain"
)

// PlannerRepositoryInterface defines the contract for planner repository operations
type PlannerRepositoryInterface interface {
	// GetSequence retrieves a sequence by sequence hash and portfolio hash
	GetSequence(sequenceHash, portfolioHash string) (*domain.ActionSequence, error)

	// ListSequencesByPortfolioHash retrieves all sequences for a portfolio hash
	ListSequencesByPortfolioHash(
		portfolioHash string,
		limit int,
	) ([]SequenceRecord, error)

	// GetPendingSequences retrieves sequences that haven't been evaluated yet
	GetPendingSequences(
		portfolioHash string,
		limit int,
	) ([]SequenceRecord, error)

	// MarkSequenceCompleted marks a sequence as completed
	MarkSequenceCompleted(sequenceHash, portfolioHash string) error

	// DeleteSequencesByPortfolioHash deletes all sequences for a portfolio hash
	DeleteSequencesByPortfolioHash(portfolioHash string) error

	// GetEvaluation retrieves an evaluation by sequence hash and portfolio hash
	GetEvaluation(sequenceHash, portfolioHash string) (*domain.EvaluationResult, error)

	// ListEvaluationsByPortfolioHash retrieves all evaluations for a portfolio hash
	ListEvaluationsByPortfolioHash(
		portfolioHash string,
	) ([]EvaluationRecord, error)

	// DeleteEvaluationsByPortfolioHash deletes all evaluations for a portfolio hash
	DeleteEvaluationsByPortfolioHash(portfolioHash string) error

	// GetBestResult retrieves the best result for a portfolio hash
	GetBestResult(portfolioHash string) (*domain.HolisticPlan, error)

	// DeleteBestResult deletes the best result for a portfolio hash
	DeleteBestResult(portfolioHash string) error

	// CountSequences returns the total number of sequences for a portfolio hash
	CountSequences(portfolioHash string) (int, error)

	// CountPendingSequences returns the number of pending sequences for a portfolio hash
	CountPendingSequences(portfolioHash string) (int, error)

	// CountEvaluations returns the total number of evaluations for a portfolio hash
	CountEvaluations(portfolioHash string) (int, error)

	// DeleteAllSequences deletes all sequences from all portfolios
	// Used by UniverseMonitor to clear all data when state changes
	DeleteAllSequences() error

	// DeleteAllEvaluations deletes all evaluations from all portfolios
	// Used by UniverseMonitor to clear all data when state changes
	DeleteAllEvaluations() error

	// DeleteAllBestResults deletes all best results from all portfolios
	// Used by UniverseMonitor to clear all data when state changes
	DeleteAllBestResults() error
}

// Compile-time check that InMemoryPlannerRepository implements PlannerRepositoryInterface
var _ PlannerRepositoryInterface = (*InMemoryPlannerRepository)(nil)
