package work

import (
	"context"
	"fmt"
	"time"
)

// PortfolioSyncServiceInterface defines the portfolio sync service interface
type PortfolioSyncServiceInterface interface {
	SyncPortfolio() error
}

// TradesSyncServiceInterface defines the trades sync service interface
type TradesSyncServiceInterface interface {
	SyncTrades() error
}

// CashFlowsSyncServiceInterface defines the cash flows sync service interface
type CashFlowsSyncServiceInterface interface {
	SyncCashFlows() error
}

// PricesSyncServiceInterface defines the prices sync service interface
type PricesSyncServiceInterface interface {
	SyncPrices() error
}

// ExchangeRateSyncServiceInterface defines the exchange rate sync service interface
type ExchangeRateSyncServiceInterface interface {
	SyncExchangeRates() error
}

// DisplayUpdateServiceInterface defines the display update service interface
type DisplayUpdateServiceInterface interface {
	UpdateDisplay() error
}

// NegativeBalanceServiceInterface defines the negative balance check service interface
type NegativeBalanceServiceInterface interface {
	CheckNegativeBalances() error
}

// SyncEventManagerInterface defines the event manager interface for sync
type SyncEventManagerInterface interface {
	Emit(event string, data any)
}

// SyncDeps contains all dependencies for sync work types
type SyncDeps struct {
	PortfolioService       PortfolioSyncServiceInterface
	TradesService          TradesSyncServiceInterface
	CashFlowsService       CashFlowsSyncServiceInterface
	PricesService          PricesSyncServiceInterface
	ExchangeRateService    ExchangeRateSyncServiceInterface
	DisplayService         DisplayUpdateServiceInterface
	NegativeBalanceService NegativeBalanceServiceInterface
	EventManager           SyncEventManagerInterface
}

// RegisterSyncWorkTypes registers all sync work types with the registry
func RegisterSyncWorkTypes(registry *Registry, deps *SyncDeps) {
	// sync:portfolio - Sync portfolio from broker (root of sync chain)
	registry.Register(&WorkType{
		ID:           "sync:portfolio",
		Priority:     PriorityHigh,
		MarketTiming: DuringMarketOpen,
		Interval:     5 * time.Minute,
		FindSubjects: func() []string {
			// Always return work, interval check handles frequency
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.PortfolioService.SyncPortfolio()
			if err != nil {
				return fmt.Errorf("failed to sync portfolio: %w", err)
			}

			// Emit event for dependents
			deps.EventManager.Emit("PortfolioSynced", nil)

			return nil
		},
	})

	// sync:trades - Sync trade history (depends on portfolio)
	registry.Register(&WorkType{
		ID:           "sync:trades",
		DependsOn:    []string{"sync:portfolio"},
		Priority:     PriorityHigh,
		MarketTiming: DuringMarketOpen,
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.TradesService.SyncTrades()
			if err != nil {
				return fmt.Errorf("failed to sync trades: %w", err)
			}

			return nil
		},
	})

	// sync:cashflows - Sync cash flows (depends on portfolio)
	registry.Register(&WorkType{
		ID:           "sync:cashflows",
		DependsOn:    []string{"sync:portfolio"},
		Priority:     PriorityHigh,
		MarketTiming: DuringMarketOpen,
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.CashFlowsService.SyncCashFlows()
			if err != nil {
				return fmt.Errorf("failed to sync cash flows: %w", err)
			}

			return nil
		},
	})

	// sync:prices - Sync current prices (depends on portfolio)
	registry.Register(&WorkType{
		ID:           "sync:prices",
		DependsOn:    []string{"sync:portfolio"},
		Priority:     PriorityMedium,
		MarketTiming: DuringMarketOpen,
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.PricesService.SyncPrices()
			if err != nil {
				return fmt.Errorf("failed to sync prices: %w", err)
			}

			return nil
		},
	})

	// sync:rates - Sync exchange rates (independent, runs anytime)
	registry.Register(&WorkType{
		ID:           "sync:rates",
		Priority:     PriorityMedium,
		MarketTiming: AnyTime,
		Interval:     1 * time.Hour,
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.ExchangeRateService.SyncExchangeRates()
			if err != nil {
				return fmt.Errorf("failed to sync exchange rates: %w", err)
			}

			return nil
		},
	})

	// sync:display - Update LED display (depends on prices)
	registry.Register(&WorkType{
		ID:           "sync:display",
		DependsOn:    []string{"sync:prices"},
		Priority:     PriorityLow,
		MarketTiming: AnyTime,
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.DisplayService.UpdateDisplay()
			if err != nil {
				return fmt.Errorf("failed to update display: %w", err)
			}

			return nil
		},
	})

	// sync:negative-balances - Check for negative balances (depends on portfolio)
	registry.Register(&WorkType{
		ID:           "sync:negative-balances",
		DependsOn:    []string{"sync:portfolio"},
		Priority:     PriorityHigh,
		MarketTiming: AnyTime,
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.NegativeBalanceService.CheckNegativeBalances()
			if err != nil {
				return fmt.Errorf("failed to check negative balances: %w", err)
			}

			return nil
		},
	})
}
