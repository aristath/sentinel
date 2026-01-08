package planner

import (
	"context"
	"fmt"

	"github.com/aristath/sentinel/internal/modules/opportunities"
	planningconstraints "github.com/aristath/sentinel/internal/modules/planning/constraints"
	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/planning/evaluation"
	"github.com/aristath/sentinel/internal/modules/planning/hash"
	"github.com/aristath/sentinel/internal/modules/sequences"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/internal/services"
	"github.com/rs/zerolog"
)

type Planner struct {
	opportunitiesService    *opportunities.Service
	sequencesService        *sequences.Service
	evaluationService       *evaluation.Service
	constraintEnforcer      *planningconstraints.Enforcer
	currencyExchangeService *services.CurrencyExchangeService
	log                     zerolog.Logger
}

func NewPlanner(opportunitiesService *opportunities.Service, sequencesService *sequences.Service, evaluationService *evaluation.Service, securityRepo *universe.SecurityRepository, currencyExchangeService *services.CurrencyExchangeService, log zerolog.Logger) *Planner {
	// Create security lookup function for constraint enforcer
	securityLookup := func(symbol, isin string) (*universe.Security, bool) {
		// Try ISIN first
		if isin != "" {
			sec, err := securityRepo.GetByISIN(isin)
			if err == nil && sec != nil {
				return sec, true
			}
		}
		// Fallback to symbol
		if symbol != "" {
			sec, err := securityRepo.GetBySymbol(symbol)
			if err == nil && sec != nil {
				return sec, true
			}
		}
		return nil, false
	}

	constraintEnforcer := planningconstraints.NewEnforcer(log, securityLookup)

	return &Planner{
		opportunitiesService:    opportunitiesService,
		sequencesService:        sequencesService,
		evaluationService:       evaluationService,
		constraintEnforcer:      constraintEnforcer,
		currencyExchangeService: currencyExchangeService,
		log:                     log.With().Str("component", "planner").Logger(),
	}
}

func (p *Planner) CreatePlan(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration) (*domain.HolisticPlan, error) {
	p.log.Info().Msg("Creating holistic plan")

	// Apply configuration to context
	ctx.ApplyConfig(config)

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

	// Call evaluation service (pass OpportunityContext for optimizer targets)
	evalCtx := context.Background()
	results, err := p.evaluationService.BatchEvaluate(evalCtx, sequences, portfolioHash, config, ctx)
	if err != nil {
		p.log.Error().Err(err).Msg("Evaluation failed, falling back to priority-based selection")
		// Fallback: use priority-based selection if evaluation fails
		// Try up to MaxSequenceAttempts sequences until one passes constraints
		bestSequence := p.selectByPriority(sequences)
		plan := p.convertToPlan(bestSequence, ctx, 0.0, 0.0)
		if len(plan.Steps) == 0 {
			// If the best sequence by priority was filtered out, return empty plan
			return &domain.HolisticPlan{
				Steps:         []domain.HolisticStep{},
				CurrentScore:  0.0,
				EndStateScore: 0.0,
				Feasible:      true,
			}, nil
		}
		return plan, nil
	}

	// Step 4: Select best sequences based on evaluation scores (try top N until one passes constraints)
	bestSequences := p.selectBestSequences(sequences, results, config.MaxSequenceAttempts)
	if len(bestSequences) == 0 {
		return nil, fmt.Errorf("no valid sequence found")
	}

	// Step 5: Try each sequence until we find one that passes constraints (has at least 1 step)
	var bestPlan *domain.HolisticPlan
	var bestScore float64
	var bestSequenceIdx int

	for idx, seqResult := range bestSequences {
		plan := p.convertToPlan(seqResult.Sequence, ctx, 0.0, seqResult.Result.EndScore)

		// If this plan has at least one step after constraint enforcement, use it
		if len(plan.Steps) > 0 {
			bestPlan = plan
			bestScore = seqResult.Result.EndScore
			bestSequenceIdx = idx
			p.log.Info().
				Int("sequence_index", idx+1).
				Int("total_attempted", len(bestSequences)).
				Int("steps", len(plan.Steps)).
				Float64("end_score", seqResult.Result.EndScore).
				Msg("Found valid sequence that passes constraints")
			break
		} else {
			p.log.Debug().
				Int("sequence_index", idx+1).
				Int("actions", len(seqResult.Sequence.Actions)).
				Float64("score", seqResult.Result.EndScore).
				Msg("Sequence filtered out by constraints, trying next")
		}
	}

	// If no sequence passed constraints, return empty plan
	if bestPlan == nil {
		p.log.Info().
			Int("attempted_sequences", len(bestSequences)).
			Msg("No sequences passed constraints after enforcement")
		return &domain.HolisticPlan{
			Steps:         []domain.HolisticStep{},
			CurrentScore:  0.0,
			EndStateScore: bestSequences[0].Result.EndScore,
			Feasible:      true,
		}, nil
	}

	p.log.Info().
		Int("sequence_index", bestSequenceIdx+1).
		Int("total_attempted", len(bestSequences)).
		Int("steps", len(bestPlan.Steps)).
		Float64("end_score", bestScore).
		Msg("Plan created")

	return bestPlan, nil
}

func (p *Planner) convertToPlan(sequence domain.ActionSequence, ctx *domain.OpportunityContext, currentScore float64, endScore float64) *domain.HolisticPlan {
	// Enforce constraints on actions before creating steps
	validatedActions, filteredActions := p.constraintEnforcer.EnforceConstraints(sequence.Actions, ctx)

	// Log filtered actions for debugging
	if len(filteredActions) > 0 {
		p.log.Info().
			Int("filtered_count", len(filteredActions)).
			Int("validated_count", len(validatedActions)).
			Msg("Applied constraint enforcement")
		for _, filtered := range filteredActions {
			p.log.Debug().
				Str("symbol", filtered.Action.Symbol).
				Str("side", filtered.Action.Side).
				Str("reason", filtered.Reason).
				Msg("Action filtered by constraints")
		}
	}
	var steps []domain.HolisticStep
	cashRequired := 0.0
	cashGenerated := 0.0

	// Use validated actions (after constraint enforcement)
	for i, action := range validatedActions {
		// Convert price to EUR if not already in EUR
		// This ensures all calculations use EUR prices
		priceEUR := action.Price
		if action.Currency != "EUR" && p.currencyExchangeService != nil {
			rate, err := p.currencyExchangeService.GetRate(action.Currency, "EUR")
			if err != nil {
				p.log.Warn().
					Err(err).
					Str("currency", action.Currency).
					Str("symbol", action.Symbol).
					Msg("Failed to get exchange rate, using original price")
			} else {
				priceEUR = action.Price * rate
				p.log.Debug().
					Str("currency", action.Currency).
					Str("symbol", action.Symbol).
					Float64("original_price", action.Price).
					Float64("price_eur", priceEUR).
					Float64("rate", rate).
					Msg("Converted price to EUR")
			}
		}

		step := domain.HolisticStep{
			StepNumber:     i + 1,
			Side:           action.Side,
			Symbol:         action.Symbol,
			Name:           action.Name,
			Quantity:       action.Quantity,
			EstimatedPrice: priceEUR, // Now in EUR
			EstimatedValue: action.ValueEUR,
			Currency:       "EUR", // Always EUR after conversion
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
	// Convert domain.Position to hash.Position
	positions := make([]hash.Position, 0, len(ctx.Positions))
	for _, pos := range ctx.Positions {
		positions = append(positions, hash.Position{
			Symbol:   pos.Symbol,
			Quantity: int(pos.Quantity),
		})
	}

	// Convert domain.Security to universe.Security for hashing
	// Note: We use ctx.StocksBySymbol which has the full Security objects
	securities := make([]*universe.Security, 0, len(ctx.Securities))
	for _, sec := range ctx.Securities {
		securities = append(securities, &universe.Security{
			Symbol:             sec.Symbol,
			Country:            sec.Country,
			AllowBuy:           sec.Active, // Use Active as default for AllowBuy
			AllowSell:          false,      // Default to false for safety
			MinPortfolioTarget: 0,
			MaxPortfolioTarget: 0,
		})
	}

	// Get cash balances from context (EUR only for now)
	cashBalances := make(map[string]float64)
	if ctx.AvailableCashEUR > 0 {
		cashBalances["EUR"] = ctx.AvailableCashEUR
	}

	// No pending orders in this context
	pendingOrders := []hash.PendingOrder{}

	// Generate the hash using the proper hash package
	return hash.GeneratePortfolioHash(positions, securities, cashBalances, pendingOrders)
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

// SequenceWithResult pairs a sequence with its evaluation result
type SequenceWithResult struct {
	Sequence domain.ActionSequence
	Result   *domain.EvaluationResult
}

// selectBestSequences finds the top N sequences sorted by evaluation score (descending)
// Returns up to maxAttempts sequences (or all if maxAttempts is 0)
func (p *Planner) selectBestSequences(sequences []domain.ActionSequence, results []domain.EvaluationResult, maxAttempts int) []SequenceWithResult {
	if len(sequences) == 0 || len(results) == 0 {
		return nil
	}

	// Create a map from sequence hash to evaluation result
	resultsByHash := make(map[string]*domain.EvaluationResult)
	for i := range results {
		resultsByHash[results[i].SequenceHash] = &results[i]
	}

	var validSequences []SequenceWithResult

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

		validSequences = append(validSequences, SequenceWithResult{
			Sequence: sequences[i],
			Result:   result,
		})
	}

	// Sort by score descending
	for i := 0; i < len(validSequences)-1; i++ {
		for j := i + 1; j < len(validSequences); j++ {
			if validSequences[i].Result.EndScore < validSequences[j].Result.EndScore {
				validSequences[i], validSequences[j] = validSequences[j], validSequences[i]
			}
		}
	}

	// Limit to maxAttempts if specified
	if maxAttempts > 0 && len(validSequences) > maxAttempts {
		validSequences = validSequences[:maxAttempts]
	}

	if len(validSequences) > 0 {
		p.log.Info().
			Int("total_valid", len(validSequences)).
			Int("selected", len(validSequences)).
			Float64("top_score", validSequences[0].Result.EndScore).
			Float64("bottom_score", validSequences[len(validSequences)-1].Result.EndScore).
			Msg("Selected top sequences by evaluation score")
	}

	return validSequences
}
