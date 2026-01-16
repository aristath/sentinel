package work

import (
	"context"
	"fmt"
	"time"
)

// TradingExecutionServiceInterface defines the trading execution service interface
type TradingExecutionServiceInterface interface {
	ExecutePendingTrades() error
	HasPendingTrades() bool
}

// TradingRetryServiceInterface defines the trading retry service interface
type TradingRetryServiceInterface interface {
	RetryFailedTrades() error
	HasFailedTrades() bool
}

// TradingDeps contains all dependencies for trading work types
type TradingDeps struct {
	ExecutionService TradingExecutionServiceInterface
	RetryService     TradingRetryServiceInterface
}

// RegisterTradingWorkTypes registers all trading work types with the registry
func RegisterTradingWorkTypes(registry *Registry, deps *TradingDeps) {
	// trading:execute - Execute pending recommendations
	registry.Register(&WorkType{
		ID:           "trading:execute",
		Priority:     PriorityCritical,
		MarketTiming: DuringMarketOpen,
		FindSubjects: func() []string {
			if deps.ExecutionService.HasPendingTrades() {
				return []string{""}
			}
			return nil
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.ExecutionService.ExecutePendingTrades()
			if err != nil {
				return fmt.Errorf("failed to execute trades: %w", err)
			}

			return nil
		},
	})

	// trading:retry - Retry failed trades
	//
	// Interval: 1 hour (hardcoded)
	// Rationale: Failed trades (broker errors, connectivity issues) should retry reasonably fast
	//            without spamming the broker. 1 hour balances responsiveness vs rate limiting.
	//            Too frequent risks account suspension; too slow misses market windows.
	//
	// Market timing: DuringMarketOpen
	// Rationale: Can only execute trades during market hours.
	registry.Register(&WorkType{
		ID:           "trading:retry",
		Priority:     PriorityMedium,
		MarketTiming: DuringMarketOpen,
		Interval:     1 * time.Hour, // Hardcoded - optimal for error recovery
		FindSubjects: func() []string {
			if deps.RetryService.HasFailedTrades() {
				return []string{""}
			}
			return nil
		},
		Execute: func(ctx context.Context, subject string, progress *ProgressReporter) error {

			err := deps.RetryService.RetryFailedTrades()
			if err != nil {
				return fmt.Errorf("failed to retry trades: %w", err)
			}

			return nil
		},
	})
}
