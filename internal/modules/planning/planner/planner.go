package planner

import (
	"context"
	"fmt"
	"sort"

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

// PlanResult wraps a HolisticPlan with rejected opportunities
type PlanResult struct {
	Plan               *domain.HolisticPlan
	RejectedOpportunities []domain.RejectedOpportunity
}

func (p *Planner) CreatePlan(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration) (*domain.HolisticPlan, error) {
	planResult, err := p.CreatePlanWithRejections(ctx, config)
	if err != nil {
		return nil, err
	}
	return planResult.Plan, nil
}

func (p *Planner) CreatePlanWithRejections(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration) (*PlanResult, error) {
	p.log.Info().Msg("Creating holistic plan")

	// Apply configuration to context
	ctx.ApplyConfig(config)

	// Track all identified opportunities for rejection tracking
	allIdentifiedOpportunities := make(map[string]domain.ActionCandidate) // key: "symbol|side"
	var identifiedOpportunitiesList []domain.ActionCandidate

	// Step 1: Identify opportunities
	opportunities, err := p.opportunitiesService.IdentifyOpportunities(ctx, config)
	if err != nil {
		return nil, fmt.Errorf("failed to identify opportunities: %w", err)
	}

	// Collect all identified opportunities
	for _, candidates := range opportunities {
		for _, candidate := range candidates {
			key := fmt.Sprintf("%s|%s", candidate.Symbol, candidate.Side)
			allIdentifiedOpportunities[key] = candidate
			identifiedOpportunitiesList = append(identifiedOpportunitiesList, candidate)
		}
	}

	// Step 2: Generate sequences
	sequences, err := p.sequencesService.GenerateSequences(opportunities, config)
	if err != nil {
		return nil, fmt.Errorf("failed to generate sequences: %w", err)
	}

	// Track which opportunities are in which sequences
	opportunitiesInSequences := make(map[string]bool) // key: "symbol|side"
	for _, seq := range sequences {
		for _, action := range seq.Actions {
			key := fmt.Sprintf("%s|%s", action.Symbol, action.Side)
			opportunitiesInSequences[key] = true
		}
	}

	if len(sequences) == 0 {
		p.log.Info().Msg("No sequences generated")
		rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, nil, nil, nil)
		return &PlanResult{
			Plan: &domain.HolisticPlan{
				Steps:         []domain.HolisticStep{},
				CurrentScore:  0.0,
				EndStateScore: 0.0,
				Feasible:      true,
			},
			RejectedOpportunities: rejected,
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
		bestSequence := p.selectByPriority(sequences)
		// Track opportunities in selected sequence (bestSequence)
		opportunitiesInSelectedSequence := make(map[string]bool)
		for _, action := range bestSequence.Actions {
			key := fmt.Sprintf("%s|%s", action.Symbol, action.Side)
			opportunitiesInSelectedSequence[key] = true
		}
		plan, filteredActions := p.convertToPlanWithFiltered(bestSequence, ctx, config, 0.0, 0.0)
		if len(plan.Steps) == 0 {
			rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, opportunitiesInSelectedSequence, nil, filteredActions)
			return &PlanResult{
				Plan: &domain.HolisticPlan{
					Steps:         []domain.HolisticStep{},
					CurrentScore:  0.0,
					EndStateScore: 0.0,
					Feasible:      true,
				},
				RejectedOpportunities: rejected,
			}, nil
		}
		rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, opportunitiesInSelectedSequence, plan, filteredActions)
		return &PlanResult{
			Plan:                 plan,
			RejectedOpportunities: rejected,
		}, nil
	}

	// Step 4: Select best sequences based on evaluation scores (try top N until one passes constraints)
	bestSequences := p.selectBestSequences(sequences, results, config.MaxSequenceAttempts)
	if len(bestSequences) == 0 {
		rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, nil, nil, nil)
		return &PlanResult{
			Plan: &domain.HolisticPlan{
				Steps:         []domain.HolisticStep{},
				CurrentScore:  0.0,
				EndStateScore: 0.0,
				Feasible:      true,
			},
			RejectedOpportunities: rejected,
		}, fmt.Errorf("no valid sequence found")
	}

	// Track which opportunities are in selected sequences (bestSequences)
	opportunitiesInSelectedSequences := make(map[string]bool)
	for _, seqResult := range bestSequences {
		for _, action := range seqResult.Sequence.Actions {
			key := fmt.Sprintf("%s|%s", action.Symbol, action.Side)
			opportunitiesInSelectedSequences[key] = true
		}
	}

	// Step 5: Try each sequence until we find one that passes constraints (has at least 1 step)
	var bestPlan *domain.HolisticPlan
	var bestFilteredActions []planningconstraints.FilteredAction
	var bestScore float64
	var bestSequenceIdx int

	for idx, seqResult := range bestSequences {
		plan, filteredActions := p.convertToPlanWithFiltered(seqResult.Sequence, ctx, config, 0.0, seqResult.Result.EndScore)

		// If this plan has at least one step after constraint enforcement, use it
		if len(plan.Steps) > 0 {
			bestPlan = plan
			bestFilteredActions = filteredActions
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
		rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, opportunitiesInSelectedSequences, nil, nil)
		return &PlanResult{
			Plan: &domain.HolisticPlan{
				Steps:         []domain.HolisticStep{},
				CurrentScore:  0.0,
				EndStateScore: bestSequences[0].Result.EndScore,
				Feasible:      true,
			},
			RejectedOpportunities: rejected,
		}, nil
	}

	p.log.Info().
		Int("sequence_index", bestSequenceIdx+1).
		Int("total_attempted", len(bestSequences)).
		Int("steps", len(bestPlan.Steps)).
		Float64("end_score", bestScore).
		Msg("Plan created")

	// Build rejected opportunities with all tracking information
	rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, opportunitiesInSelectedSequences, bestPlan, bestFilteredActions)

	return &PlanResult{
		Plan:                 bestPlan,
		RejectedOpportunities: rejected,
	}, nil
}

func (p *Planner) convertToPlan(sequence domain.ActionSequence, ctx *domain.OpportunityContext, config *domain.PlannerConfiguration, currentScore float64, endScore float64) *domain.HolisticPlan {
	plan, _ := p.convertToPlanWithFiltered(sequence, ctx, config, currentScore, endScore)
	return plan
}

func (p *Planner) convertToPlanWithFiltered(sequence domain.ActionSequence, ctx *domain.OpportunityContext, config *domain.PlannerConfiguration, currentScore float64, endScore float64) (*domain.HolisticPlan, []planningconstraints.FilteredAction) {
	// Enforce constraints on actions before creating steps
	validatedActions, filteredActions := p.constraintEnforcer.EnforceConstraints(sequence.Actions, ctx, config)

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
	}, filteredActions
}

// generatePortfolioHash creates a hash representing the portfolio state.
func (p *Planner) generatePortfolioHash(ctx *domain.OpportunityContext) string {
	// Convert EnrichedPosition to hash.Position
	positions := make([]hash.Position, 0, len(ctx.EnrichedPositions))
	for _, pos := range ctx.EnrichedPositions {
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

// buildRejectedOpportunities builds a list of rejected opportunities with all rejection reasons
func (p *Planner) buildRejectedOpportunities(
	allIdentified []domain.ActionCandidate,
	opportunitiesInSequences map[string]bool,
	opportunitiesInSelectedSequences map[string]bool,
	finalPlan *domain.HolisticPlan,
	filteredActions []planningconstraints.FilteredAction,
) []domain.RejectedOpportunity {
	// Build a map of opportunities in final plan (key: "symbol|side")
	finalPlanOpportunities := make(map[string]bool)
	if finalPlan != nil {
		for _, step := range finalPlan.Steps {
			key := fmt.Sprintf("%s|%s", step.Symbol, step.Side)
			finalPlanOpportunities[key] = true
		}
	}

	// Build a map of filtered actions with reasons (key: "symbol|side" -> reasons)
	filteredByConstraints := make(map[string][]string)
	for _, filtered := range filteredActions {
		key := fmt.Sprintf("%s|%s", filtered.Action.Symbol, filtered.Action.Side)
		filteredByConstraints[key] = append(filteredByConstraints[key], filtered.Reason)
	}

	// Build rejection reasons map (key: "symbol|side" -> reasons array)
	rejectionReasons := make(map[string]*domain.RejectedOpportunity)

	// Process each identified opportunity
	for _, candidate := range allIdentified {
		key := fmt.Sprintf("%s|%s", candidate.Symbol, candidate.Side)

		// Skip if this opportunity made it into the final plan
		if finalPlanOpportunities[key] {
			continue
		}

		// Initialize rejected opportunity if not already present
		if _, exists := rejectionReasons[key]; !exists {
			rejectionReasons[key] = &domain.RejectedOpportunity{
				Side:           candidate.Side,
				Symbol:         candidate.Symbol,
				Name:           candidate.Name,
				Reasons:        []string{},
				OriginalReason: candidate.Reason,
			}
		}

		rejected := rejectionReasons[key]

		// Add reasons based on opportunity lifecycle
		if !opportunitiesInSequences[key] {
			// Opportunity was not included in any sequence
			rejected.Reasons = append(rejected.Reasons, "not included in any sequence")
		} else if opportunitiesInSelectedSequences != nil && opportunitiesInSelectedSequences[key] {
			// Opportunity was in selected sequences, check if it was filtered by constraints
			if constraintReasons, hasConstraints := filteredByConstraints[key]; hasConstraints {
				// Was filtered by constraints
				for _, reason := range constraintReasons {
					rejected.Reasons = append(rejected.Reasons, reason)
				}
			} else {
				// If it's in selected sequences and not filtered by constraints, it should be in final plan
				// Since it's not in final plan, add a generic reason
				rejected.Reasons = append(rejected.Reasons, "not included in final plan")
			}
		} else {
			// Opportunity was in sequences but not in selected sequences
			rejected.Reasons = append(rejected.Reasons, "not in best sequence")
		}

		// Add original opportunity reason if available
		if candidate.Reason != "" {
			rejected.OriginalReason = candidate.Reason
			// Include original reason in Reasons array for context (e.g., "near 52-week high")
			// Check if it's not already in Reasons to avoid duplicates
			foundInReasons := false
			for _, existingReason := range rejected.Reasons {
				if existingReason == candidate.Reason {
					foundInReasons = true
					break
				}
			}
			if !foundInReasons {
				rejected.Reasons = append(rejected.Reasons, candidate.Reason)
			}
		}
	}

	// Convert map to slice and deduplicate reasons
	result := make([]domain.RejectedOpportunity, 0, len(rejectionReasons))
	for _, rejected := range rejectionReasons {
		// Deduplicate reasons
		seen := make(map[string]bool)
		uniqueReasons := []string{}
		for _, reason := range rejected.Reasons {
			if !seen[reason] {
				seen[reason] = true
				uniqueReasons = append(uniqueReasons, reason)
			}
		}
		rejected.Reasons = uniqueReasons

		// Sort reasons for consistent display
		sort.Strings(rejected.Reasons)

		result = append(result, *rejected)
	}

	// Sort result by symbol and side for consistent display
	sort.Slice(result, func(i, j int) bool {
		if result[i].Symbol != result[j].Symbol {
			return result[i].Symbol < result[j].Symbol
		}
		return result[i].Side < result[j].Side
	})

	return result
}
