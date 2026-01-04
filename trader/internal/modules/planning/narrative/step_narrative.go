package narrative

import (
	"fmt"
	"strings"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// StepGenerator generates narratives for individual action steps.
type StepGenerator struct {
	log zerolog.Logger
}

// NewStepGenerator creates a new step narrative generator.
func NewStepGenerator(log zerolog.Logger) *StepGenerator {
	return &StepGenerator{
		log: log.With().Str("component", "step_narrative").Logger(),
	}
}

// Generate creates a human-readable narrative for a single step.
func (g *StepGenerator) Generate(step *domain.HolisticStep) string {
	if step == nil {
		return ""
	}

	var parts []string

	// Action header
	parts = append(parts, g.generateActionHeader(step))

	// Reason
	if step.Reason != "" {
		parts = append(parts, g.formatReason(step.Reason))
	}

	// Value impact
	parts = append(parts, g.generateValueImpact(step))

	// Context from flags and contributes_to
	context := g.generateStepContext(step)
	if context != "" {
		parts = append(parts, context)
	}

	return strings.Join(parts, " ")
}

// generateActionHeader creates the main action description.
func (g *StepGenerator) generateActionHeader(step *domain.HolisticStep) string {
	if step.Side == "BUY" {
		return fmt.Sprintf("Buy %d shares of %s (%s) at %.2f EUR",
			step.Quantity,
			step.Name,
			step.Symbol,
			step.EstimatedPrice,
		)
	}

	return fmt.Sprintf("Sell %d shares of %s (%s) at %.2f EUR",
		step.Quantity,
		step.Name,
		step.Symbol,
		step.EstimatedPrice,
	)
}

// formatReason formats the reason string for better readability.
func (g *StepGenerator) formatReason(reason string) string {
	// Capitalize first letter if not already
	if len(reason) > 0 {
		firstChar := strings.ToUpper(string(reason[0]))
		reason = firstChar + reason[1:]
	}

	// Ensure it ends with a period
	if !strings.HasSuffix(reason, ".") && !strings.HasSuffix(reason, "!") {
		reason = reason + "."
	}

	return reason
}

// generateValueImpact describes the financial impact of the action.
func (g *StepGenerator) generateValueImpact(step *domain.HolisticStep) string {
	if step.Side == "BUY" {
		return fmt.Sprintf("Total cost: %.2f EUR (including transaction fees).", step.EstimatedValue)
	}

	return fmt.Sprintf("Net proceeds: %.2f EUR (after transaction fees).", step.EstimatedValue)
}

// generateStepContext creates contextual information from step flags and goals.
func (g *StepGenerator) generateStepContext(step *domain.HolisticStep) string {
	var contexts []string

	// Check windfall flag
	if step.IsWindfall {
		contexts = append(contexts, "Position has experienced windfall gains")
	}

	// Check averaging down flag
	if step.IsAveragingDown {
		contexts = append(contexts, "Averaging down on position with unrealized loss")
	}

	// Add goals/contributions
	if len(step.ContributesTo) > 0 {
		for _, goal := range step.ContributesTo {
			switch goal {
			case "rebalancing":
				contexts = append(contexts, "Part of portfolio rebalancing")
			case "profit_taking":
				contexts = append(contexts, "This is a profit-taking opportunity")
			case "diversification":
				contexts = append(contexts, "Improves portfolio diversification")
			case "allocation_alignment":
				contexts = append(contexts, "Aligns with target allocations")
			default:
				contexts = append(contexts, fmt.Sprintf("Contributes to %s", goal))
			}
		}
	}

	if len(contexts) == 0 {
		return ""
	}

	return strings.Join(contexts, "; ") + "."
}

// GenerateShortSummary creates a brief one-line summary of a step.
func (g *StepGenerator) GenerateShortSummary(step *domain.HolisticStep) string {
	if step == nil {
		return ""
	}

	action := strings.ToUpper(step.Side)
	return fmt.Sprintf("%s %s: %d shares @ %.2f EUR",
		action,
		step.Symbol,
		step.Quantity,
		step.EstimatedPrice,
	)
}

// GenerateDetailedAnalysis creates an in-depth analysis of a step.
func (g *StepGenerator) GenerateDetailedAnalysis(step *domain.HolisticStep) string {
	if step == nil {
		return ""
	}

	var parts []string

	// Basic action
	parts = append(parts, g.generateActionHeader(step))

	// Step number
	parts = append(parts, fmt.Sprintf("Step %d in sequence.", step.StepNumber))

	// Reason
	if step.Reason != "" {
		parts = append(parts, g.formatReason(step.Reason))
	}

	// Financial details
	parts = append(parts, g.generateFinancialDetails(step))

	// Currency information
	if step.Currency != "EUR" {
		parts = append(parts, fmt.Sprintf("Trade currency: %s.", step.Currency))
	}

	// Context analysis (windfall, averaging down, goals)
	context := g.generateDetailedContext(step)
	if context != "" {
		parts = append(parts, context)
	}

	return strings.Join(parts, " ")
}

// generateFinancialDetails creates detailed financial breakdown.
func (g *StepGenerator) generateFinancialDetails(step *domain.HolisticStep) string {
	totalValue := float64(step.Quantity) * step.EstimatedPrice

	if step.Side == "BUY" {
		transactionCost := step.EstimatedValue - totalValue
		return fmt.Sprintf("Position value: %.2f EUR, transaction cost: %.2f EUR, total: %.2f EUR.",
			totalValue,
			transactionCost,
			step.EstimatedValue,
		)
	}

	transactionCost := totalValue - step.EstimatedValue
	return fmt.Sprintf("Sale value: %.2f EUR, transaction cost: %.2f EUR, net: %.2f EUR.",
		totalValue,
		transactionCost,
		step.EstimatedValue,
	)
}

// generateDetailedContext creates detailed analysis from step flags and goals.
func (g *StepGenerator) generateDetailedContext(step *domain.HolisticStep) string {
	var analysis []string

	// Analyze windfall and averaging down
	if step.IsWindfall && step.Side == "SELL" {
		analysis = append(analysis, "This position has experienced exceptional gains and warrants profit-taking")
	}

	if step.IsAveragingDown && step.Side == "BUY" {
		analysis = append(analysis, "Averaging down to reduce cost basis on underperforming position")
	}

	// Analyze goals
	hasRebalancing := false
	hasProfitTaking := false
	hasAllocation := false

	for _, goal := range step.ContributesTo {
		switch goal {
		case "rebalancing":
			hasRebalancing = true
		case "profit_taking":
			hasProfitTaking = true
		case "allocation_alignment":
			hasAllocation = true
		}
	}

	if hasProfitTaking && !step.IsWindfall {
		analysis = append(analysis, "Taking profits on a position with solid gains")
	}

	if hasRebalancing {
		analysis = append(analysis, "Action contributes to overall portfolio rebalancing")
	}

	if hasAllocation {
		analysis = append(analysis, "Aligned with optimizer-recommended target weights")
	}

	if len(analysis) == 0 {
		return ""
	}

	return strings.Join(analysis, "; ") + "."
}
