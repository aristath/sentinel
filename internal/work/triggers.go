package work

// TriggerCacheInterface defines the cache interface for triggers
type TriggerCacheInterface interface {
	Delete(key string)
	DeletePrefix(prefix string)
}

// EventBusInterface defines the event bus interface for triggers
type EventBusInterface interface {
	Subscribe(event string, handler func(data any))
}

// TriggerDeps contains all dependencies for triggers
type TriggerDeps struct {
	Cache      TriggerCacheInterface
	EventBus   EventBusInterface
	Processor  *Processor
	Completion *CompletionTracker
}

// RegisterTriggers registers event handlers that trigger work processing
func RegisterTriggers(deps *TriggerDeps) {
	// StateChanged -> Clear planner cache and trigger
	deps.EventBus.Subscribe("StateChanged", func(data any) {
		deps.Cache.DeletePrefix("planner:")
		deps.Cache.DeletePrefix("optimizer_weights")
		deps.Cache.DeletePrefix("opportunity_context")
		deps.Cache.DeletePrefix("trade_plan")
		deps.Completion.ClearByPrefix("planner:")
		deps.Processor.Trigger()
	})

	// RecommendationsReady -> Clear trading cache and trigger
	deps.EventBus.Subscribe("RecommendationsReady", func(data any) {
		deps.Cache.Delete("trading:pending")
		deps.Processor.Trigger()
	})

	// DividendDetected -> Clear dividend cache and trigger
	deps.EventBus.Subscribe("DividendDetected", func(data any) {
		deps.Cache.DeletePrefix("dividend:")
		deps.Completion.ClearByPrefix("dividend:")
		deps.Processor.Trigger()
	})

	// MarketsStatusChanged -> Trigger to check market-timed work
	deps.EventBus.Subscribe("MarketsStatusChanged", func(data any) {
		deps.Processor.Trigger()
	})

	// PortfolioSynced -> Clear dependent caches and trigger
	deps.EventBus.Subscribe("PortfolioSynced", func(data any) {
		deps.Completion.ClearByTypeID("sync:portfolio")
		deps.Processor.Trigger()
	})

	// SecurityHistorySynced -> Clear technical calculation cache for the security
	deps.EventBus.Subscribe("SecurityHistorySynced", func(data any) {
		if isin, ok := data.(string); ok && isin != "" {
			deps.Completion.Clear("security:sync", isin)
		}
		deps.Processor.Trigger()
	})
}
