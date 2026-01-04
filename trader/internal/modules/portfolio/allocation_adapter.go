package portfolio

import (
	"github.com/aristath/arduino-trader/internal/modules/allocation"
)

// PortfolioSummaryAdapter adapts PortfolioService to allocation.PortfolioSummaryProvider
// This adapter breaks the circular dependency: allocation → portfolio
type PortfolioSummaryAdapter struct {
	service *PortfolioService
}

// NewPortfolioSummaryAdapter creates a new adapter
func NewPortfolioSummaryAdapter(service *PortfolioService) allocation.PortfolioSummaryProvider {
	return &PortfolioSummaryAdapter{service: service}
}

// GetPortfolioSummary implements allocation.PortfolioSummaryProvider
func (a *PortfolioSummaryAdapter) GetPortfolioSummary() (allocation.PortfolioSummary, error) {
	portfolioSummary, err := a.service.GetPortfolioSummary()
	if err != nil {
		return allocation.PortfolioSummary{}, err
	}

	// Convert portfolio.PortfolioSummary to allocation.PortfolioSummary
	return allocation.PortfolioSummary{
		CountryAllocations:  convertAllocationsToAllocation(portfolioSummary.CountryAllocations),
		IndustryAllocations: convertAllocationsToAllocation(portfolioSummary.IndustryAllocations),
		TotalValue:          portfolioSummary.TotalValue,
		CashBalance:         portfolioSummary.CashBalance,
	}, nil
}

// convertAllocationsToAllocation converts []AllocationStatus to []allocation.PortfolioAllocation
func convertAllocationsToAllocation(src []AllocationStatus) []allocation.PortfolioAllocation {
	result := make([]allocation.PortfolioAllocation, len(src))
	for i, a := range src {
		result[i] = allocation.PortfolioAllocation{
			Name:         a.Name,
			TargetPct:    a.TargetPct,
			CurrentPct:   a.CurrentPct,
			CurrentValue: a.CurrentValue,
			Deviation:    a.Deviation,
		}
	}
	return result
}
