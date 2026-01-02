package planner

import (
	"fmt"

	"github.com/aristath/arduino-trader/internal/modules/opportunities"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/sequences"
	"github.com/rs/zerolog"
)

type Planner struct {
	opportunitiesService *opportunities.Service
	sequencesService     *sequences.Service
	log                  zerolog.Logger
}

func NewPlanner(opportunitiesService *opportunities.Service, sequencesService *sequences.Service, log zerolog.Logger) *Planner {
	return &Planner{
		opportunitiesService: opportunitiesService,
		sequencesService:     sequencesService,
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
			Steps:        []domain.HolisticStep{},
			CurrentScore: 0.0,
			EndStateScore: 0.0,
			Feasible:     true,
		}, nil
	}

	// Step 3: Evaluate sequences (would call evaluation service)
	// For now, just pick highest priority sequence
	bestSequence := sequences[0]
	for _, seq := range sequences {
		if seq.Priority > bestSequence.Priority {
			bestSequence = seq
		}
	}

	// Step 4: Convert to HolisticPlan
	plan := p.convertToPlan(bestSequence)

	p.log.Info().Int("steps", len(plan.Steps)).Float64("priority", bestSequence.Priority).Msg("Plan created")
	return plan, nil
}

func (p *Planner) convertToPlan(sequence domain.ActionSequence) *domain.HolisticPlan {
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

	return &domain.HolisticPlan{
		Steps:            steps,
		CurrentScore:     0.0,
		EndStateScore:    sequence.Priority,
		Improvement:      sequence.Priority,
		NarrativeSummary: fmt.Sprintf("Execute %d actions to improve portfolio", len(steps)),
		CashRequired:     cashRequired,
		CashGenerated:    cashGenerated,
		Feasible:         true,
	}
}
