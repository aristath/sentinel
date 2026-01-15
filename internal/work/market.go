package work

// MarketChecker defines the interface for checking market status.
// This allows the work package to check market timing without directly
// depending on the market_hours module.
type MarketChecker interface {
	// IsAnyMarketOpen returns true if any market is currently open.
	IsAnyMarketOpen() bool

	// IsSecurityMarketOpen returns true if the market for a specific security is open.
	// The ISIN is used to determine which market to check.
	IsSecurityMarketOpen(isin string) bool

	// AreAllMarketsClosed returns true if all markets are closed.
	// This is used for maintenance work that should only run during maintenance windows.
	AreAllMarketsClosed() bool
}

// MarketTimingChecker checks whether work can execute based on market timing.
type MarketTimingChecker struct {
	market MarketChecker
}

// NewMarketTimingChecker creates a new market timing checker.
func NewMarketTimingChecker(market MarketChecker) *MarketTimingChecker {
	return &MarketTimingChecker{
		market: market,
	}
}

// CanExecute returns true if the work can execute given the market timing constraint.
func (c *MarketTimingChecker) CanExecute(timing MarketTiming, subject string) bool {
	switch timing {
	case AnyTime:
		return true

	case AfterMarketClose:
		if subject == "" {
			// Global work: wait for all markets to close
			return !c.market.IsAnyMarketOpen()
		}
		// Per-security work: wait for that security's market to close
		return !c.market.IsSecurityMarketOpen(subject)

	case DuringMarketOpen:
		if subject == "" {
			// Global work: run when any market is open
			return c.market.IsAnyMarketOpen()
		}
		// Per-security work: run when that security's market is open
		return c.market.IsSecurityMarketOpen(subject)

	case AllMarketsClosed:
		// Always a global check - all markets must be closed
		return c.market.AreAllMarketsClosed()

	default:
		// Unknown timing - be safe and don't execute
		return false
	}
}
