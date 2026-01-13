// Package planner provides the core planning logic for portfolio recommendations.
package planner

import (
	"context"
	"fmt"
	"sort"

	maindomain "github.com/aristath/sentinel/internal/domain"
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
	brokerClient            maindomain.BrokerClient
	securityRepo            *universe.SecurityRepository // For symbol-to-ISIN lookups
	log                     zerolog.Logger
}

func NewPlanner(opportunitiesService *opportunities.Service, sequencesService *sequences.Service, evaluationService *evaluation.Service, securityRepo *universe.SecurityRepository, currencyExchangeService *services.CurrencyExchangeService, brokerClient maindomain.BrokerClient, log zerolog.Logger) *Planner {
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
		brokerClient:            brokerClient,
		securityRepo:            securityRepo,
		log:                     log.With().Str("component", "planner").Logger(),
	}
}

// PlanResult wraps a HolisticPlan with rejected opportunities and pre-filtered securities
type PlanResult struct {
	Plan                  *domain.HolisticPlan
	RejectedOpportunities []domain.RejectedOpportunity
	PreFilteredSecurities []domain.PreFilteredSecurity
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

	// Step 1: Identify opportunities with exclusions
	opportunitiesResult, err := p.opportunitiesService.IdentifyOpportunitiesWithExclusions(ctx, config)
	if err != nil {
		return nil, fmt.Errorf("failed to identify opportunities: %w", err)
	}

	// Extract opportunities for backward compatibility with sequence generation
	opportunities := opportunitiesResult.ToOpportunitiesByCategory()

	// Collect all pre-filtered securities across categories
	preFilteredSecurities := opportunitiesResult.AllPreFiltered()

	// Collect all identified opportunities
	for _, candidates := range opportunities {
		for _, candidate := range candidates {
			key := fmt.Sprintf("%s|%s", candidate.Symbol, candidate.Side)
			allIdentifiedOpportunities[key] = candidate
			identifiedOpportunitiesList = append(identifiedOpportunitiesList, candidate)
		}
	}

	// Step 2: Generate sequences
	sequences, err := p.sequencesService.GenerateSequences(opportunities, ctx, config)
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
			PreFilteredSecurities: preFilteredSecurities,
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
				PreFilteredSecurities: preFilteredSecurities,
			}, nil
		}
		rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, opportunitiesInSelectedSequence, plan, filteredActions)
		return &PlanResult{
			Plan:                  plan,
			RejectedOpportunities: rejected,
			PreFilteredSecurities: preFilteredSecurities,
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
			PreFilteredSecurities: preFilteredSecurities,
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
			PreFilteredSecurities: preFilteredSecurities,
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
		Plan:                  bestPlan,
		RejectedOpportunities: rejected,
		PreFilteredSecurities: preFilteredSecurities,
	}, nil
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

		// Check tags for windfall and averaging down flags
		isWindfall := containsTag(action.Tags, "windfall")
		isAveragingDown := containsTag(action.Tags, "averaging_down")

		step := domain.HolisticStep{
			StepNumber:      i + 1,
			Side:            action.Side,
			ISIN:            action.ISIN,   // Primary identifier
			Symbol:          action.Symbol, // For broker API and UI display
			Name:            action.Name,
			Quantity:        action.Quantity,
			EstimatedPrice:  priceEUR, // Now in EUR
			EstimatedValue:  action.ValueEUR,
			Currency:        "EUR", // Always EUR after conversion
			Reason:          action.Reason,
			Narrative:       fmt.Sprintf("Step %d: %s %d shares of %s", i+1, action.Side, action.Quantity, action.Symbol),
			IsWindfall:      isWindfall,
			IsAveragingDown: isAveragingDown,
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

	// Fetch pending orders from broker and convert to hash format
	pendingOrders := p.fetchPendingOrdersForHash()

	// Generate the hash using the proper hash package
	return hash.GeneratePortfolioHash(positions, securities, cashBalances, pendingOrders)
}

// fetchPendingOrdersForHash fetches pending orders from the broker and converts them to hash.PendingOrder format.
// This assumes all pending trades will complete successfully - the portfolio hash should reflect the expected future state.
func (p *Planner) fetchPendingOrdersForHash() []hash.PendingOrder {
	pendingOrders := []hash.PendingOrder{}

	// Check if broker client is available
	if p.brokerClient == nil || !p.brokerClient.IsConnected() {
		p.log.Debug().Msg("Broker client not available - skipping pending orders in hash")
		return pendingOrders
	}

	// Fetch pending orders from broker
	brokerOrders, err := p.brokerClient.GetPendingOrders()
	if err != nil {
		p.log.Warn().Err(err).Msg("Failed to fetch pending orders for portfolio hash")
		return pendingOrders
	}

	// Convert to hash.PendingOrder format
	for _, order := range brokerOrders {
		pendingOrders = append(pendingOrders, hash.PendingOrder{
			Symbol:   order.Symbol,
			Side:     order.Side,
			Quantity: int(order.Quantity),
			Price:    order.Price,
			Currency: order.Currency,
		})
	}

	if len(pendingOrders) > 0 {
		p.log.Info().Int("count", len(pendingOrders)).Msg("Including pending orders in portfolio hash")
	}

	return pendingOrders
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

// buildRejectedOpportunities builds a list of rejected opportunities with clear, actionable rejection reasons
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

		// Add reasons based on opportunity lifecycle with clear explanations
		if !opportunitiesInSequences[key] {
			// Opportunity was not included in any sequence
			// This happens when patterns don't pick up this opportunity
			rejected.Reasons = append(rejected.Reasons, "not selected by any pattern (may need different pattern or lower priority)")
		} else if opportunitiesInSelectedSequences != nil && opportunitiesInSelectedSequences[key] {
			// Opportunity was in one of the top evaluated sequences
			if constraintReasons, hasConstraints := filteredByConstraints[key]; hasConstraints {
				// Was filtered by constraints
				for _, reason := range constraintReasons {
					rejected.Reasons = append(rejected.Reasons, fmt.Sprintf("constraint: %s", reason))
				}
			} else {
				// Opportunity was in a candidate sequence that wasn't the winning one
				// This is the key fix: be specific about WHY it wasn't included
				rejected.Reasons = append(rejected.Reasons, "in alternative sequence (a different sequence had higher score)")
			}
		} else {
			// Opportunity was in sequences but not in top evaluated sequences
			rejected.Reasons = append(rejected.Reasons, "sequence not in top candidates (lower combined priority)")
		}

		// Add original opportunity reason if available (for context)
		if candidate.Reason != "" {
			rejected.OriginalReason = candidate.Reason
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

// containsTag checks if a tag is present in a slice of tags.
func containsTag(tags []string, target string) bool {
	for _, tag := range tags {
		if tag == target {
			return true
		}
	}
	return false
}
