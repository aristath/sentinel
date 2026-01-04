package narrative

import (
	"fmt"
	"strings"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// PlanGenerator generates narratives for complete action plans.
type PlanGenerator struct {
	log zerolog.Logger
}

// NewPlanGenerator creates a new plan narrative generator.
func NewPlanGenerator(log zerolog.Logger) *PlanGenerator {
	return &PlanGenerator{
		log: log.With().Str("component", "plan_narrative").Logger(),
	}
}

// Generate creates a human-readable narrative for an entire plan.
func (g *PlanGenerator) Generate(plan *domain.HolisticPlan) string {
	if plan == nil || len(plan.Steps) == 0 {
		return "No actions recommended at this time. Portfolio appears well-balanced."
	}

	var parts []string

	// Overview
	parts = append(parts, g.generateOverview(plan))

	// Strategy summary
	parts = append(parts, g.generateStrategySummary(plan))

	// Financial impact
	parts = append(parts, g.generateFinancialImpact(plan))

	// Execution guidance
	parts = append(parts, g.generateExecutionGuidance(plan))

	return strings.Join(parts, "\n\n")
}

// generateOverview creates a high-level summary of the plan.
func (g *PlanGenerator) generateOverview(plan *domain.HolisticPlan) string {
	buyCount := 0
	sellCount := 0
	totalBuyValue := 0.0
	totalSellValue := 0.0

	for _, step := range plan.Steps {
		if step.Side == "BUY" {
			buyCount++
			totalBuyValue += step.EstimatedValue
		} else if step.Side == "SELL" {
			sellCount++
			totalSellValue += step.EstimatedValue
		}
	}

	var summary strings.Builder
	summary.WriteString(fmt.Sprintf("Recommended plan with %d action(s): ", len(plan.Steps)))

	if buyCount > 0 && sellCount > 0 {
		summary.WriteString(fmt.Sprintf("%d buy orders (%.2f EUR total) and %d sell orders (%.2f EUR proceeds).",
			buyCount, totalBuyValue, sellCount, totalSellValue))
	} else if buyCount > 0 {
		summary.WriteString(fmt.Sprintf("%d buy orders totaling %.2f EUR.",
			buyCount, totalBuyValue))
	} else if sellCount > 0 {
		summary.WriteString(fmt.Sprintf("%d sell orders with %.2f EUR in expected proceeds.",
			sellCount, totalSellValue))
	}

	// Add score if available
	if plan.EndStateScore > 0 {
		summary.WriteString(fmt.Sprintf(" Expected end-state score: %.4f", plan.EndStateScore))
		if plan.Improvement > 0 {
			summary.WriteString(fmt.Sprintf(" (improvement: +%.4f)", plan.Improvement))
		}
		summary.WriteString(".")
	}

	return summary.String()
}

// generateStrategySummary explains the strategic intent of the plan.
func (g *PlanGenerator) generateStrategySummary(plan *domain.HolisticPlan) string {
	// Analyze flags and goals across all steps to understand strategy
	goalCounts := make(map[string]int)
	windfallCount := 0
	averagingDownCount := 0

	for _, step := range plan.Steps {
		if step.IsWindfall {
			windfallCount++
		}
		if step.IsAveragingDown {
			averagingDownCount++
		}
		for _, goal := range step.ContributesTo {
			goalCounts[goal]++
		}
	}

	var strategies []string

	if goalCounts["profit_taking"] > 0 {
		strategies = append(strategies, fmt.Sprintf("Taking profits on %d position(s) with gains", goalCounts["profit_taking"]))
	}

	if windfallCount > 0 {
		strategies = append(strategies, fmt.Sprintf("Capturing windfall gains from %d exceptional performer(s)", windfallCount))
	}

	if goalCounts["rebalancing"] > 0 {
		strategies = append(strategies, fmt.Sprintf("Rebalancing %d position(s) to target allocations", goalCounts["rebalancing"]))
	}

	if averagingDownCount > 0 {
		strategies = append(strategies, fmt.Sprintf("Averaging down on %d underperforming position(s)", averagingDownCount))
	}

	if goalCounts["allocation_alignment"] > 0 {
		strategies = append(strategies, fmt.Sprintf("Aligning %d position(s) with optimizer weights", goalCounts["allocation_alignment"]))
	}

	if goalCounts["diversification"] > 0 {
		strategies = append(strategies, fmt.Sprintf("Improving diversification across %d action(s)", goalCounts["diversification"]))
	}

	if len(strategies) == 0 {
		return "Strategic focus: General portfolio optimization."
	}

	return "Strategic focus: " + strings.Join(strategies, "; ") + "."
}

// generateFinancialImpact summarizes the financial effects of the plan.
func (g *PlanGenerator) generateFinancialImpact(plan *domain.HolisticPlan) string {
	totalBuyCost := 0.0
	totalSellProceeds := 0.0
	netCashFlow := 0.0

	for _, step := range plan.Steps {
		if step.Side == "BUY" {
			totalBuyCost += step.EstimatedValue
			netCashFlow -= step.EstimatedValue
		} else if step.Side == "SELL" {
			totalSellProceeds += step.EstimatedValue
			netCashFlow += step.EstimatedValue
		}
	}

	var impact strings.Builder
	impact.WriteString("Financial impact: ")

	if totalBuyCost > 0 && totalSellProceeds > 0 {
		impact.WriteString(fmt.Sprintf("Investment of %.2f EUR in buys, %.2f EUR from sells. ",
			totalBuyCost, totalSellProceeds))

		if netCashFlow > 0 {
			impact.WriteString(fmt.Sprintf("Net cash inflow: %.2f EUR.", netCashFlow))
		} else if netCashFlow < 0 {
			impact.WriteString(fmt.Sprintf("Net cash requirement: %.2f EUR.", -netCashFlow))
		} else {
			impact.WriteString("Cash-neutral rebalancing.")
		}
	} else if totalBuyCost > 0 {
		impact.WriteString(fmt.Sprintf("Total investment required: %.2f EUR.", totalBuyCost))
	} else if totalSellProceeds > 0 {
		impact.WriteString(fmt.Sprintf("Total proceeds expected: %.2f EUR.", totalSellProceeds))
	}

	return impact.String()
}

// generateExecutionGuidance provides guidance on executing the plan.
func (g *PlanGenerator) generateExecutionGuidance(plan *domain.HolisticPlan) string {
	if len(plan.Steps) == 0 {
		return ""
	}

	var guidance strings.Builder
	guidance.WriteString("Execution guidance: ")

	// Check if plan has sequenced steps (ordered by priority)
	if len(plan.Steps) == 1 {
		guidance.WriteString("Single action can be executed immediately.")
	} else {
		guidance.WriteString(fmt.Sprintf("Actions are prioritized in recommended order. "))

		// Check for sells before buys pattern
		hasSells := false
		hasBuys := false
		firstActionIsSell := plan.Steps[0].Side == "SELL"

		for _, step := range plan.Steps {
			if step.Side == "SELL" {
				hasSells = true
			} else if step.Side == "BUY" {
				hasBuys = true
			}
		}

		if hasSells && hasBuys && firstActionIsSell {
			guidance.WriteString("Sells are prioritized to generate cash for subsequent buys. ")
		}

		guidance.WriteString("Execute steps sequentially for optimal results.")
	}

	return guidance.String()
}

// GenerateCompactSummary creates a compact multi-line summary.
func (g *PlanGenerator) GenerateCompactSummary(plan *domain.HolisticPlan) string {
	if plan == nil || len(plan.Steps) == 0 {
		return "No actions recommended"
	}

	var lines []string

	// Count actions by type
	buyCount := 0
	sellCount := 0
	for _, step := range plan.Steps {
		if step.Side == "BUY" {
			buyCount++
		} else if step.Side == "SELL" {
			sellCount++
		}
	}

	// Summary line
	if buyCount > 0 && sellCount > 0 {
		lines = append(lines, fmt.Sprintf("%d buys, %d sells", buyCount, sellCount))
	} else if buyCount > 0 {
		lines = append(lines, fmt.Sprintf("%d buy recommendations", buyCount))
	} else if sellCount > 0 {
		lines = append(lines, fmt.Sprintf("%d sell recommendations", sellCount))
	}

	// List each step briefly
	for i, step := range plan.Steps {
		lines = append(lines, fmt.Sprintf("%d. %s %s: %d @ %.2f EUR",
			i+1,
			step.Side,
			step.Symbol,
			step.Quantity,
			step.EstimatedPrice,
		))
	}

	return strings.Join(lines, "\n")
}

// GenerateMarkdownReport creates a detailed markdown report.
func (g *PlanGenerator) GenerateMarkdownReport(plan *domain.HolisticPlan) string {
	if plan == nil || len(plan.Steps) == 0 {
		return "## No Recommendations\n\nNo actions recommended at this time."
	}

	var report strings.Builder

	// Title
	report.WriteString("# Portfolio Action Plan\n\n")

	// Overview
	report.WriteString("## Overview\n\n")
	report.WriteString(g.generateOverview(plan))
	report.WriteString("\n\n")

	// Strategy
	report.WriteString("## Strategy\n\n")
	report.WriteString(g.generateStrategySummary(plan))
	report.WriteString("\n\n")

	// Financial Impact
	report.WriteString("## Financial Impact\n\n")
	report.WriteString(g.generateFinancialImpact(plan))
	report.WriteString("\n\n")

	// Actions
	report.WriteString("## Recommended Actions\n\n")
	for i, step := range plan.Steps {
		report.WriteString(fmt.Sprintf("### %d. %s %s\n\n", i+1, step.Side, step.Symbol))
		report.WriteString(fmt.Sprintf("- **Security**: %s (%s)\n", step.Name, step.Symbol))
		report.WriteString(fmt.Sprintf("- **Action**: %s %d shares @ %.2f EUR\n", step.Side, step.Quantity, step.EstimatedPrice))
		report.WriteString(fmt.Sprintf("- **Estimated Value**: %.2f EUR\n", step.EstimatedValue))
		if step.Reason != "" {
			report.WriteString(fmt.Sprintf("- **Reason**: %s\n", step.Reason))
		}
		if step.IsWindfall {
			report.WriteString("- **Windfall**: Yes\n")
		}
		if step.IsAveragingDown {
			report.WriteString("- **Averaging Down**: Yes\n")
		}
		if len(step.ContributesTo) > 0 {
			report.WriteString(fmt.Sprintf("- **Contributes To**: %s\n", strings.Join(step.ContributesTo, ", ")))
		}
		report.WriteString("\n")
	}

	// Execution
	report.WriteString("## Execution\n\n")
	report.WriteString(g.generateExecutionGuidance(plan))
	report.WriteString("\n")

	return report.String()
}
