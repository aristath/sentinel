package planner

import (
	"context"
	"fmt"

	"github.com/aristath/arduino-trader/internal/modules/opportunities"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/planning/evaluation"
	"github.com/aristath/arduino-trader/internal/modules/sequences"
	"github.com/rs/zerolog"
)

type Planner struct {
	opportunitiesService *opportunities.Service
	sequencesService     *sequences.Service
	evaluationClient     *evaluation.Client
	log                  zerolog.Logger
}

func NewPlanner(opportunitiesService *opportunities.Service, sequencesService *sequences.Service, evaluationClient *evaluation.Client, log zerolog.Logger) *Planner {
	return &Planner{
		opportunitiesService: opportunitiesService,
		sequencesService:     sequencesService,
		evaluationClient:     evaluationClient,
		log:                  log.With().Str("component", "planner").Logger(),
	}
}

func (p *Planner) CreatePlan(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration) (*domain.HolisticPlan, error) {
	p.log.Info().Msg("Creating holistic plan")

	// Step 1: Identify opportunities
	opportunities, err := p.opportunitiesService.IdentifyOpportunities(ctx, config)
	if err != nil {
		return nil, fmt.Errorf("failed to identify opportunities: %w", err)
	}

	// Step 2: Generate sequences
	sequences, err := p.sequencesService.GenerateSequences(opportunities, config)
	if err != nil {
		return nil, fmt.Errorf("failed to generate sequences: %w", err)
	}

	if len(sequences) == 0 {
		p.log.Info().Msg("No sequences generated")
		return &domain.HolisticPlan{
			Steps:         []domain.HolisticStep{},
			CurrentScore:  0.0,
			EndStateScore: 0.0,
			Feasible:      true,
		}, nil
	}

	// Step 3: Evaluate sequences using evaluation service
	p.log.Info().Int("sequence_count", len(sequences)).Msg("Evaluating sequences")

	// Generate portfolio hash (simplified - would use actual portfolio state hash)
	portfolioHash := p.generatePortfolioHash(ctx)

	// Call evaluation service
	evalCtx := context.Background()
	results, err := p.evaluationClient.BatchEvaluate(evalCtx, sequences, portfolioHash)
	if err != nil {
		p.log.Error().Err(err).Msg("Evaluation failed, falling back to priority-based selection")
		// Fallback: use priority-based selection if evaluation fails
		bestSequence := p.selectByPriority(sequences)
		plan := p.convertToPlan(bestSequence, 0.0, 0.0)
		return plan, nil
	}

	// Step 4: Select best sequence based on evaluation scores
	bestSequence, bestResult := p.selectBestSequence(sequences, results)
	if bestSequence == nil {
		return nil, fmt.Errorf("no valid sequence found")
	}

	// Step 5: Convert to HolisticPlan
	plan := p.convertToPlan(*bestSequence, 0.0, bestResult.EndScore)

	p.log.Info().
		Int("steps", len(plan.Steps)).
		Float64("end_score", bestResult.EndScore).
		Msg("Plan created")

	return plan, nil
}

func (p *Planner) convertToPlan(sequence domain.ActionSequence, currentScore float64, endScore float64) *domain.HolisticPlan {
	var steps []domain.HolisticStep
	cashRequired := 0.0
	cashGenerated := 0.0

	for i, action := range sequence.Actions {
		step := domain.HolisticStep{
			StepNumber:     i + 1,
			Side:           action.Side,
			Symbol:         action.Symbol,
			Name:           action.Name,
			Quantity:       action.Quantity,
			EstimatedPrice: action.Price,
			EstimatedValue: action.ValueEUR,
			Currency:       action.Currency,
			Reason:         action.Reason,
			Narrative:      fmt.Sprintf("Step %d: %s %d shares of %s", i+1, action.Side, action.Quantity, action.Symbol),
		}

		if action.Side == "BUY" {
			cashRequired += action.ValueEUR
		} else {
			cashGenerated += action.ValueEUR
		}

		steps = append(steps, step)
	}

	improvement := endScore - currentScore

	return &domain.HolisticPlan{
		Steps:            steps,
		CurrentScore:     currentScore,
		EndStateScore:    endScore,
		Improvement:      improvement,
		NarrativeSummary: fmt.Sprintf("Execute %d actions to improve portfolio", len(steps)),
		CashRequired:     cashRequired,
		CashGenerated:    cashGenerated,
		Feasible:         true,
	}
}

// generatePortfolioHash creates a hash representing the portfolio state.
func (p *Planner) generatePortfolioHash(ctx *domain.OpportunityContext) string {
	// Simplified hash generation - in production would use crypto/md5 or similar
	// and hash all relevant portfolio state
	return fmt.Sprintf("portfolio_%d_positions", len(ctx.Positions))
}

// selectByPriority selects the sequence with highest priority (fallback when evaluation fails).
func (p *Planner) selectByPriority(sequences []domain.ActionSequence) domain.ActionSequence {
	if len(sequences) == 0 {
		return domain.ActionSequence{}
	}

	best := sequences[0]
	for _, seq := range sequences[1:] {
		if seq.Priority > best.Priority {
			best = seq
		}
	}

	p.log.Info().
		Float64("priority", best.Priority).
		Str("pattern", best.PatternType).
		Msg("Selected sequence by priority (fallback mode)")

	return best
}

// selectBestSequence finds the sequence with the highest evaluation score.
func (p *Planner) selectBestSequence(sequences []domain.ActionSequence, results []domain.EvaluationResult) (*domain.ActionSequence, *domain.EvaluationResult) {
	if len(sequences) == 0 || len(results) == 0 {
		return nil, nil
	}

	// Create a map from sequence hash to evaluation result
	resultsByHash := make(map[string]*domain.EvaluationResult)
	for i := range results {
		resultsByHash[results[i].SequenceHash] = &results[i]
	}

	var bestSequence *domain.ActionSequence
	var bestResult *domain.EvaluationResult
	bestScore := -999999.0

	for i := range sequences {
		result, ok := resultsByHash[sequences[i].SequenceHash]
		if !ok {
			p.log.Warn().
				Str("hash", sequences[i].SequenceHash).
				Msg("No evaluation result for sequence")
			continue
		}

		// Skip infeasible sequences
		if !result.Feasible {
			continue
		}

		if result.EndScore > bestScore {
			bestScore = result.EndScore
			bestSequence = &sequences[i]
			bestResult = result
		}
	}

	if bestSequence != nil {
		p.log.Info().
			Float64("score", bestScore).
			Str("pattern", bestSequence.PatternType).
			Int("actions", len(bestSequence.Actions)).
			Msg("Selected best sequence by evaluation score")
	}

	return bestSequence, bestResult
}
