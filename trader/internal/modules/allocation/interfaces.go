package allocation

// PortfolioSummaryProvider provides portfolio summary data without creating
// a dependency on the portfolio package. This interface breaks the circular
// dependency: allocation → portfolio → cash_flows → satellites → trading → allocation
type PortfolioSummaryProvider interface {
	GetPortfolioSummary() (PortfolioSummary, error)
}

// ConcentrationAlertProvider provides concentration alert detection without
// requiring direct dependency on ConcentrationAlertService. This interface
// breaks the circular dependency: trading → allocation
type ConcentrationAlertProvider interface {
	DetectAlerts(summary PortfolioSummary) ([]ConcentrationAlert, error)
}
