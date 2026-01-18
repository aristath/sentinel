/**
 * Package di provides dependency injection for the work processor.
 *
 * This package initializes the work processor system which handles background jobs
 * with event-driven execution, dependency resolution, and market-aware scheduling.
 */
package di

import (
	"github.com/aristath/sentinel/internal/work"
	"github.com/rs/zerolog"
)

// WorkComponents holds all work processor components
type WorkComponents struct {
	Registry  *work.Registry
	Market    *work.MarketTimingChecker
	Processor *work.Processor
	Handlers  *work.Handlers
}

// workCache is an in-memory cache for work types
type workCache struct {
	data map[string]interface{}
}

func newWorkCache() *workCache {
	return &workCache{
		data: make(map[string]interface{}),
	}
}

func (c *workCache) Has(key string) bool {
	_, exists := c.data[key]
	return exists
}

func (c *workCache) Get(key string) interface{} {
	return c.data[key]
}

func (c *workCache) Set(key string, value interface{}) {
	c.data[key] = value
}

func (c *workCache) Delete(key string) {
	delete(c.data, key)
}

func (c *workCache) DeletePrefix(prefix string) {
	for key := range c.data {
		if len(key) >= len(prefix) && key[:len(prefix)] == prefix {
			delete(c.data, key)
		}
	}
}

// getJobDescription returns a human-readable description for a job type
func getJobDescription(jobType string) string {
	descriptions := map[string]string{
		"sync:portfolio":          "Syncing portfolio positions",
		"sync:trades":             "Syncing trades from broker",
		"sync:cashflows":          "Syncing cash flows",
		"sync:prices":             "Updating security prices",
		"sync:exchange-rates":     "Updating exchange rates",
		"sync:display":            "Updating LED display",
		"sync:negative-balances":  "Checking account balances",
		"planner:weights":         "Calculating portfolio weights",
		"planner:context":         "Building opportunity context",
		"planner:plan":            "Creating trade plan",
		"planner:store":           "Storing recommendations",
		"trading:execute":         "Executing trade",
		"trading:retry":           "Retrying failed trades",
		"maintenance:backup":      "Creating backup",
		"maintenance:r2-backup":   "Uploading backup to cloud",
		"maintenance:vacuum":      "Optimizing databases",
		"maintenance:health":      "Running health checks",
		"maintenance:cleanup":     "Cleaning up old data",
		"security:metadata":       "Syncing security metadata",
		"security:metadata:batch": "Batch syncing all security metadata",
		"security:history":        "Syncing historical prices",
		"dividend:detection":      "Detecting unreinvested dividends",
		"dividend:execution":      "Executing dividend trades",
		"analysis:market-regime":  "Analyzing market regime",
		"deployment:check":        "Checking for system updates",
	}
	if desc, ok := descriptions[jobType]; ok {
		return desc
	}
	return jobType
}

// InitializeWork creates and wires up all work processor components
func InitializeWork(container *Container, log zerolog.Logger) (*WorkComponents, error) {
	// Create core components
	registry := work.NewRegistry()
	market := work.NewMarketTimingChecker(&marketHoursAdapter{container: container})
	cache := work.NewCache(container.CacheDB.Conn())
	processor := work.NewProcessor(registry, market, cache)

	// Wire event emitter for progress reporting
	if container.EventManager != nil {
		processor.SetEventEmitter(&eventEmitterAdapter{manager: container.EventManager})
	}

	handlers := work.NewHandlers(processor, registry)

	// Create work cache (still used by dividend work)
	workCache := newWorkCache()

	// Register planner work types (use SQLite cache from processor, not in-memory workCache)
	registerPlannerWork(registry, container, cache, log)

	// Register sync work types
	registerSyncWork(registry, container, log)

	// Register maintenance work types
	registerMaintenanceWork(registry, container, log)

	// Register trading work types
	registerTradingWork(registry, container, log)

	// Register security work types
	registerSecurityWork(registry, container, log)

	// Register dividend work types
	registerDividendWork(registry, container, workCache, log)

	// Register analysis work types
	registerAnalysisWork(registry, container, log)

	// Register deployment work types
	registerDeploymentWork(registry, container, log)

	// Register triggers
	registerTriggers(container, processor, cache, workCache, log)

	log.Info().Int("work_types", registry.Count()).Msg("Work processor initialized")

	return &WorkComponents{
		Registry:  registry,
		Market:    market,
		Processor: processor,
		Handlers:  handlers,
	}, nil
}
