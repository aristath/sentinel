// Package planner provides the core planning logic for portfolio recommendations.
package planner

import (
	"context"
	"fmt"
	"sort"
	"time"

	maindomain "github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/opportunities"
	planningconstraints "github.com/aristath/sentinel/internal/modules/planning/constraints"
	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/planning/evaluation"
	"github.com/aristath/sentinel/internal/modules/planning/hash"
	"github.com/aristath/sentinel/internal/modules/planning/progress"
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

// PlanResult wraps a HolisticPlan with rejected opportunities, pre-filtered securities, and rejected sequences
type PlanResult struct {
	Plan                  *domain.HolisticPlan
	RejectedOpportunities []domain.RejectedOpportunity
	PreFilteredSecurities []domain.PreFilteredSecurity
	RejectedSequences     []domain.RejectedSequence
}

func (p *Planner) CreatePlan(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration) (*domain.HolisticPlan, error) {
	planResult, err := p.CreatePlanWithRejections(ctx, config, nil)
	if err != nil {
		return nil, err
	}
	return planResult.Plan, nil
}

// CreatePlanWithDetailedProgress creates a holistic trading plan with detailed progress reporting.
// The detailedCallback receives structured progress updates with phase, subphase, and metrics.
// This method provides rich progress information for debugging and UI display.
func (p *Planner) CreatePlanWithDetailedProgress(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration, detailedCallback progress.DetailedCallback) (*PlanResult, error) {
	p.log.Info().Msg("Creating holistic plan with detailed progress")

	// Apply configuration to context
	ctx.ApplyConfig(config)

	// Track all identified opportunities for rejection tracking
	allIdentifiedOpportunities := make(map[string]domain.ActionCandidate) // key: "symbol|side"
	var identifiedOpportunitiesList []domain.ActionCandidate

	// Step 1: Identify opportunities with per-calculator progress reporting
	opportunitiesResult, err := p.opportunitiesService.IdentifyOpportunitiesWithProgress(ctx, config, detailedCallback)
	if err != nil {
		return nil, fmt.Errorf("failed to identify opportunities: %w", err)
	}

	// Extract opportunities for sequence generation
	opportunities := opportunitiesResult.ToOpportunitiesByCategory()

	// Collect all pre-filtered securities across categories
	preFilteredSecurities := opportunitiesResult.AllPreFiltered()

	// Count total candidates
	totalCandidates := 0
	for _, candidates := range opportunities {
		totalCandidates += len(candidates)
	}

	// Report completion of opportunity identification
	progress.CallDetailed(detailedCallback, progress.Update{
		Phase:    "opportunity_identification",
		SubPhase: "complete",
		Current:  1,
		Total:    1,
		Message:  fmt.Sprintf("Identified %d trading opportunities", totalCandidates),
		Details: map[string]any{
			"total_candidates":   totalCandidates,
			"pre_filtered_count": len(preFilteredSecurities),
			"categories":         len(opportunities),
		},
	})

	// Collect all identified opportunities
	for _, candidates := range opportunities {
		for _, candidate := range candidates {
			key := fmt.Sprintf("%s|%s", candidate.Symbol, candidate.Side)
			allIdentifiedOpportunities[key] = candidate
			identifiedOpportunitiesList = append(identifiedOpportunitiesList, candidate)
		}
	}

	// Step 2: Generate sequences with detailed progress
	sequences, err := p.sequencesService.GenerateSequencesWithDetailedProgress(opportunities, ctx, config, detailedCallback)
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
		rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, nil, nil)
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

	// Step 3: Evaluate sequences using evaluation service with detailed progress
	p.log.Info().Int("sequence_count", len(sequences)).Msg("Evaluating sequences")

	// Generate portfolio hash
	portfolioHash := p.generatePortfolioHash(ctx)

	// Call evaluation service with detailed progress
	evalCtx := context.Background()
	results, err := p.evaluationService.BatchEvaluateDetailed(evalCtx, sequences, portfolioHash, config, ctx, detailedCallback)
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
		plan := p.convertToPlan(bestSequence, ctx, config, 0.0, 0.0)
		if len(plan.Steps) == 0 {
			rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, opportunitiesInSelectedSequence, nil)
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
		rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, opportunitiesInSelectedSequence, plan)
		return &PlanResult{
			Plan:                  plan,
			RejectedOpportunities: rejected,
			PreFilteredSecurities: preFilteredSecurities,
		}, nil
	}

	// Step 4: Select best sequences based on evaluation scores
	bestSequences := p.selectBestSequences(sequences, results, config.MaxSequenceAttempts)
	if len(bestSequences) == 0 {
		rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, nil, nil)
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

	// Count feasible and infeasible sequences
	feasibleCount := 0
	infeasibleCount := 0
	var bestScore float64
	for _, result := range results {
		if result.Feasible {
			feasibleCount++
			if result.EndScore > bestScore {
				bestScore = result.EndScore
			}
		} else {
			infeasibleCount++
		}
	}

	// Report selection phase completion
	progress.CallDetailed(detailedCallback, progress.Update{
		Phase:    "sequence_selection",
		SubPhase: "complete",
		Current:  1,
		Total:    1,
		Message:  fmt.Sprintf("Selected best sequence from %d candidates", len(bestSequences)),
		Details: map[string]any{
			"total_sequences":  len(sequences),
			"feasible_count":   feasibleCount,
			"infeasible_count": infeasibleCount,
			"best_score":       bestScore,
			"selected_count":   len(bestSequences),
		},
	})

	// Step 5: Select the best sequence (highest score)
	if len(bestSequences) == 0 {
		p.log.Info().Msg("No sequences generated")
		rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, nil, nil)
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

	// Take the best sequence (first in sorted list)
	bestSequence := bestSequences[0]
	bestPlan := p.convertToPlan(bestSequence.Sequence, ctx, config, 0.0, bestSequence.Result.EndScore)

	p.log.Info().
		Int("total_candidates", len(bestSequences)).
		Int("steps", len(bestPlan.Steps)).
		Float64("end_score", bestSequence.Result.EndScore).
		Float64("improvement", bestSequence.Result.EndScore-bestPlan.CurrentScore).
		Msg("Selected best sequence with detailed progress")

	// Track which opportunities are in the selected sequence
	opportunitiesInSelectedSequence := make(map[string]bool)
	for _, action := range bestSequence.Sequence.Actions {
		key := fmt.Sprintf("%s|%s", action.Symbol, action.Side)
		opportunitiesInSelectedSequence[key] = true
	}

	// Build rejected opportunities
	rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, opportunitiesInSelectedSequence, bestPlan)

	// Build rejected sequences (all sequences except the winning one)
	rejectedSequences := p.buildRejectedSequences(sequences, results, bestSequence.Sequence.SequenceHash)

	return &PlanResult{
		Plan:                  bestPlan,
		RejectedOpportunities: rejected,
		PreFilteredSecurities: preFilteredSecurities,
		RejectedSequences:     rejectedSequences,
	}, nil
}

// CacheInterface defines methods needed for caching planner data
type CacheInterface interface {
	SetJSON(key string, value interface{}, expiresAt int64) error
}

// CreatePlanWithCache creates a holistic plan and caches sequences and best-sequence in the provided cache.
func (p *Planner) CreatePlanWithCache(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration, cache CacheInterface) (*domain.HolisticPlan, error) {
	if cache == nil {
		// Fallback to regular CreatePlan if no cache provided
		return p.CreatePlan(ctx, config)
	}

	planResult, err := p.CreatePlanWithRejectionsAndCache(ctx, config, nil, cache)
	if err != nil {
		return nil, err
	}
	return planResult.Plan, nil
}

// CreatePlanWithRejections creates a holistic trading plan with rejection tracking.
// The progressCallback is called during sequence generation and evaluation to report progress.
func (p *Planner) CreatePlanWithRejections(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration, progressCallback progress.Callback) (*PlanResult, error) {
	return p.CreatePlanWithRejectionsAndCache(ctx, config, progressCallback, nil)
}

// CreatePlanWithRejectionsAndCache creates a holistic trading plan with rejection tracking and optional caching.
// The progressCallback is called during sequence generation and evaluation to report progress.
// If cache is provided, sequences and best-sequence will be cached with 5-minute expiration.
func (p *Planner) CreatePlanWithRejectionsAndCache(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration, progressCallback progress.Callback, cache CacheInterface) (*PlanResult, error) {
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

	// Extract opportunities for sequence generation
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
	sequences, err := p.sequencesService.GenerateSequences(opportunities, ctx, config, progressCallback)
	if err != nil {
		return nil, fmt.Errorf("failed to generate sequences: %w", err)
	}

	// Cache sequences if cache is provided
	if cache != nil {
		expiresAt := time.Now().Add(5 * time.Minute).Unix()
		if err := cache.SetJSON("sequences", sequences, expiresAt); err != nil {
			p.log.Warn().Err(err).Msg("Failed to cache sequences")
		}
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
		rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, nil, nil)
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
	results, err := p.evaluationService.BatchEvaluate(evalCtx, sequences, portfolioHash, config, ctx, progressCallback)
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
		plan := p.convertToPlan(bestSequence, ctx, config, 0.0, 0.0)
		if len(plan.Steps) == 0 {
			rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, opportunitiesInSelectedSequence, nil)
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

		// Cache best-sequence (HolisticPlan) if cache is provided (fallback path)
		if cache != nil {
			expiresAt := time.Now().Add(5 * time.Minute).Unix()
			if err := cache.SetJSON("best-sequence", plan, expiresAt); err != nil {
				p.log.Warn().Err(err).Msg("Failed to cache best-sequence (fallback path)")
			}
		}

		rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, opportunitiesInSelectedSequence, plan)
		return &PlanResult{
			Plan:                  plan,
			RejectedOpportunities: rejected,
			PreFilteredSecurities: preFilteredSecurities,
		}, nil
	}

	// Step 4: Select best sequences based on evaluation scores
	bestSequences := p.selectBestSequences(sequences, results, config.MaxSequenceAttempts)
	if len(bestSequences) == 0 {
		rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, nil, nil)
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

	// Step 5: Select the best sequence (highest score)
	// All actions are already validated by the generator - no re-filtering needed
	// Note: len(bestSequences) == 0 is already checked above at line 462

	// Take the best sequence (first in sorted list)
	bestSequence := bestSequences[0]
	bestPlan := p.convertToPlan(bestSequence.Sequence, ctx, config, 0.0, bestSequence.Result.EndScore)

	p.log.Info().
		Int("total_candidates", len(bestSequences)).
		Int("steps", len(bestPlan.Steps)).
		Float64("end_score", bestSequence.Result.EndScore).
		Float64("improvement", bestSequence.Result.EndScore-bestPlan.CurrentScore).
		Msg("Selected best sequence")

	// Cache best-sequence (HolisticPlan) if cache is provided
	if cache != nil {
		expiresAt := time.Now().Add(5 * time.Minute).Unix()
		if err := cache.SetJSON("best-sequence", bestPlan, expiresAt); err != nil {
			p.log.Warn().Err(err).Msg("Failed to cache best-sequence")
		}
	}

	// Log top 5 candidates for debugging
	for i := 0; i < min(5, len(bestSequences)); i++ {
		seq := bestSequences[i]
		p.log.Debug().
			Int("rank", i+1).
			Int("actions", len(seq.Sequence.Actions)).
			Float64("score", seq.Result.EndScore).
			Bool("selected", i == 0).
			Msg("Candidate sequence")
	}

	// Track which opportunities are in the selected sequence
	opportunitiesInSelectedSequence := make(map[string]bool)
	for _, action := range bestSequence.Sequence.Actions {
		key := fmt.Sprintf("%s|%s", action.Symbol, action.Side)
		opportunitiesInSelectedSequence[key] = true
	}

	// Build rejected opportunities
	rejected := p.buildRejectedOpportunities(identifiedOpportunitiesList, opportunitiesInSequences, opportunitiesInSelectedSequence, bestPlan)

	// Build rejected sequences (all sequences except the winning one)
	rejectedSequences := p.buildRejectedSequences(sequences, results, bestSequence.Sequence.SequenceHash)

	return &PlanResult{
		Plan:                  bestPlan,
		RejectedOpportunities: rejected,
		PreFilteredSecurities: preFilteredSecurities,
		RejectedSequences:     rejectedSequences,
	}, nil
}

func (p *Planner) convertToPlan(sequence domain.ActionSequence, ctx *domain.OpportunityContext, config *domain.PlannerConfiguration, currentScore float64, endScore float64) *domain.HolisticPlan {
	// No constraint enforcement needed - generator already filtered infeasible actions
	// All actions in the sequence are guaranteed to be executable
	var steps []domain.HolisticStep
	cashRequired := 0.0
	cashGenerated := 0.0

	// Use sequence actions directly - generator already validated feasibility
	for i, action := range sequence.Actions {
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
	}
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

	// Convert universe.Security to universe.Security for hashing
	// Note: We use ctx.StocksBySymbol which has the full Security objects
	securities := make([]*universe.Security, 0, len(ctx.Securities))
	for _, sec := range ctx.Securities {
		securities = append(securities, &universe.Security{
			Symbol:             sec.Symbol,
			Geography:          sec.Geography,
			AllowBuy:           true,  // After migration 038: All securities in database are active
			AllowSell:          false, // Default to false for safety
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
) []domain.RejectedOpportunity {
	// Build a map of opportunities in final plan (key: "symbol|side")
	finalPlanOpportunities := make(map[string]bool)
	if finalPlan != nil {
		for _, step := range finalPlan.Steps {
			key := fmt.Sprintf("%s|%s", step.Symbol, step.Side)
			finalPlanOpportunities[key] = true
		}
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
			// This happens when the exhaustive generator didn't create a sequence with this opportunity
			rejected.Reasons = append(rejected.Reasons, "not selected by sequence generator (may need different parameters or lower priority)")
		} else if opportunitiesInSelectedSequences != nil && opportunitiesInSelectedSequences[key] {
			// Opportunity was in one of the top evaluated sequences but not the winning one
			rejected.Reasons = append(rejected.Reasons, "in alternative sequence (a different sequence had higher score)")
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

// min returns the minimum of two integers.
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// buildRejectedSequences builds a list of rejected sequences from evaluation results.
// All sequences except the winning one (rank 1) are marked as rejected with appropriate reasons.
func (p *Planner) buildRejectedSequences(sequences []domain.ActionSequence, results []domain.EvaluationResult, winningHash string) []domain.RejectedSequence {
	if len(sequences) == 0 || len(results) == 0 {
		return nil
	}

	// Create a map from sequence hash to evaluation result
	resultsByHash := make(map[string]*domain.EvaluationResult)
	for i := range results {
		resultsByHash[results[i].SequenceHash] = &results[i]
	}

	// Create a map from sequence hash to sequence
	sequencesByHash := make(map[string]domain.ActionSequence)
	for _, seq := range sequences {
		sequencesByHash[seq.SequenceHash] = seq
	}

	// Build list of all sequences with results (including infeasible)
	type sequenceWithScore struct {
		hash     string
		sequence domain.ActionSequence
		result   *domain.EvaluationResult
	}
	var allSequences []sequenceWithScore

	for _, seq := range sequences {
		result, ok := resultsByHash[seq.SequenceHash]
		if !ok {
			continue
		}
		allSequences = append(allSequences, sequenceWithScore{
			hash:     seq.SequenceHash,
			sequence: seq,
			result:   result,
		})
	}

	// Sort by score descending (feasible first, then by score)
	for i := 0; i < len(allSequences)-1; i++ {
		for j := i + 1; j < len(allSequences); j++ {
			// Feasible sequences come before infeasible
			if allSequences[i].result.Feasible != allSequences[j].result.Feasible {
				if allSequences[j].result.Feasible {
					allSequences[i], allSequences[j] = allSequences[j], allSequences[i]
				}
			} else if allSequences[i].result.EndScore < allSequences[j].result.EndScore {
				allSequences[i], allSequences[j] = allSequences[j], allSequences[i]
			}
		}
	}

	// Build rejected sequences list (all except rank 1 / winning hash)
	var rejected []domain.RejectedSequence
	rank := 1
	for _, sws := range allSequences {
		if sws.hash == winningHash {
			rank++ // Skip the winning sequence but still increment rank
			continue
		}

		reason := "lower_score"
		if !sws.result.Feasible {
			if sws.result.Error != "" {
				reason = sws.result.Error
			} else {
				reason = "infeasible"
			}
		}

		rejected = append(rejected, domain.RejectedSequence{
			Rank:     rank,
			Actions:  sws.sequence.Actions,
			Score:    sws.result.EndScore,
			Feasible: sws.result.Feasible,
			Reason:   reason,
		})
		rank++
	}

	return rejected
}
