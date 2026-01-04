package narrative

import (
	"fmt"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// Generator creates human-readable narratives for action plans.
type Generator struct {
	stepGenerator *StepGenerator
	planGenerator *PlanGenerator
	log           zerolog.Logger
}

// NewGenerator creates a new narrative generator.
func NewGenerator(log zerolog.Logger) *Generator {
	return &Generator{
		stepGenerator: NewStepGenerator(log),
		planGenerator: NewPlanGenerator(log),
		log:           log.With().Str("component", "narrative_generator").Logger(),
	}
}

// GenerateStepNarrative generates a narrative for a single step.
func (g *Generator) GenerateStepNarrative(step *domain.HolisticStep) string {
	if step == nil {
		return ""
	}

	return g.stepGenerator.Generate(step)
}

// GeneratePlanNarrative generates an overall narrative for the entire plan.
func (g *Generator) GeneratePlanNarrative(plan *domain.HolisticPlan) string {
	if plan == nil {
		return ""
	}

	return g.planGenerator.Generate(plan)
}

// EnrichPlan adds narratives to a plan and all its steps.
func (g *Generator) EnrichPlan(plan *domain.HolisticPlan) error {
	if plan == nil {
		return fmt.Errorf("plan cannot be nil")
	}

	g.log.Debug().
		Int("steps", len(plan.Steps)).
		Msg("Enriching plan with narratives")

	// Generate narrative for each step
	for i := range plan.Steps {
		narrative := g.stepGenerator.Generate(&plan.Steps[i])
		plan.Steps[i].Narrative = narrative

		g.log.Debug().
			Int("step_index", i).
			Str("side", plan.Steps[i].Side).
			Int("narrative_length", len(narrative)).
			Msg("Generated step narrative")
	}

	// Generate overall plan narrative
	plan.NarrativeSummary = g.planGenerator.Generate(plan)

	g.log.Info().
		Int("steps", len(plan.Steps)).
		Int("plan_narrative_length", len(plan.NarrativeSummary)).
		Msg("Plan enrichment complete")

	return nil
}

// GenerateBriefSummary creates a one-line summary of a plan.
func (g *Generator) GenerateBriefSummary(plan *domain.HolisticPlan) string {
	if plan == nil || len(plan.Steps) == 0 {
		return "No actions recommended"
	}

	buyCount := 0
	sellCount := 0

	for _, step := range plan.Steps {
		if step.Side == "BUY" {
			buyCount++
		} else if step.Side == "SELL" {
			sellCount++
		}
	}

	if buyCount > 0 && sellCount > 0 {
		return fmt.Sprintf("%d buy and %d sell recommendations", buyCount, sellCount)
	} else if buyCount > 0 {
		return fmt.Sprintf("%d buy recommendations", buyCount)
	} else if sellCount > 0 {
		return fmt.Sprintf("%d sell recommendations", sellCount)
	}

	return "No specific action recommendations"
}

// GenerateExecutionSummary creates a summary after executing a step.
func (g *Generator) GenerateExecutionSummary(step *domain.HolisticStep, success bool) string {
	if step == nil {
		return "Invalid step"
	}

	action := "executed"
	if !success {
		action = "failed to execute"
	}

	return fmt.Sprintf("%s %s: %d shares of %s at %.2f EUR",
		action,
		step.Side,
		step.Quantity,
		step.Symbol,
		step.EstimatedPrice,
	)
}
