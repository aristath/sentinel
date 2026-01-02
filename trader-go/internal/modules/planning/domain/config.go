package domain

// ModuleConfig represents configuration for a single module (calculator, pattern, generator, filter).
type ModuleConfig struct {
	Enabled bool                   `toml:"enabled" json:"enabled"`
	Params  map[string]interface{} `toml:"params" json:"params"`
}

// OpportunityCalculatorsConfig contains configuration for all opportunity calculators.
type OpportunityCalculatorsConfig struct {
	ProfitTaking    ModuleConfig `toml:"profit_taking" json:"profit_taking"`
	AveragingDown   ModuleConfig `toml:"averaging_down" json:"averaging_down"`
	OpportunityBuys ModuleConfig `toml:"opportunity_buys" json:"opportunity_buys"`
	RebalanceSells  ModuleConfig `toml:"rebalance_sells" json:"rebalance_sells"`
	RebalanceBuys   ModuleConfig `toml:"rebalance_buys" json:"rebalance_buys"`
	WeightBased     ModuleConfig `toml:"weight_based" json:"weight_based"`
}

// PatternGeneratorsConfig contains configuration for all pattern generators.
type PatternGeneratorsConfig struct {
	// Basic patterns
	DirectBuy        ModuleConfig `toml:"direct_buy" json:"direct_buy"`
	ProfitTaking     ModuleConfig `toml:"profit_taking" json:"profit_taking"`
	Rebalance        ModuleConfig `toml:"rebalance" json:"rebalance"`
	AveragingDown    ModuleConfig `toml:"averaging_down" json:"averaging_down"`
	SingleBest       ModuleConfig `toml:"single_best" json:"single_best"`
	MultiSell        ModuleConfig `toml:"multi_sell" json:"multi_sell"`
	MixedStrategy    ModuleConfig `toml:"mixed_strategy" json:"mixed_strategy"`
	OpportunityFirst ModuleConfig `toml:"opportunity_first" json:"opportunity_first"`
	DeepRebalance    ModuleConfig `toml:"deep_rebalance" json:"deep_rebalance"`
	CashGeneration   ModuleConfig `toml:"cash_generation" json:"cash_generation"`
	CostOptimized    ModuleConfig `toml:"cost_optimized" json:"cost_optimized"`

	// Complex patterns
	Adaptive     ModuleConfig `toml:"adaptive" json:"adaptive"`
	MarketRegime ModuleConfig `toml:"market_regime" json:"market_regime"`
}

// SequenceGeneratorsConfig contains configuration for all sequence generators.
type SequenceGeneratorsConfig struct {
	Combinatorial         ModuleConfig `toml:"combinatorial" json:"combinatorial"`
	EnhancedCombinatorial ModuleConfig `toml:"enhanced_combinatorial" json:"enhanced_combinatorial"`
	PartialExecution      ModuleConfig `toml:"partial_execution" json:"partial_execution"`
	ConstraintRelaxation  ModuleConfig `toml:"constraint_relaxation" json:"constraint_relaxation"`
}

// FiltersConfig contains configuration for all sequence filters.
type FiltersConfig struct {
	CorrelationAware ModuleConfig `toml:"correlation_aware" json:"correlation_aware"`
	Diversity        ModuleConfig `toml:"diversity" json:"diversity"`
	Eligibility      ModuleConfig `toml:"eligibility" json:"eligibility"`
	RecentlyTraded   ModuleConfig `toml:"recently_traded" json:"recently_traded"`
}

// PlannerConfiguration represents the complete configuration for a planner instance.
// Each bucket can have its own planner configuration with different enabled modules and parameters.
type PlannerConfiguration struct {
	// Planner identification
	Name                  string `toml:"name" json:"name"`
	Description           string `toml:"description" json:"description"`
	EnableBatchGeneration bool   `toml:"enable_batch_generation" json:"enable_batch_generation"`

	// Global planner settings
	MaxDepth                    int     `toml:"max_depth" json:"max_depth"`
	MaxOpportunitiesPerCategory int     `toml:"max_opportunities_per_category" json:"max_opportunities_per_category"`
	PriorityThreshold           float64 `toml:"priority_threshold" json:"priority_threshold"`
	BeamWidth                   int     `toml:"beam_width" json:"beam_width"`
	EnableDiverseSelection      bool    `toml:"enable_diverse_selection" json:"enable_diverse_selection"`
	DiversityWeight             float64 `toml:"diversity_weight" json:"diversity_weight"`

	// Module configurations
	OpportunityCalculators OpportunityCalculatorsConfig `toml:"opportunity_calculators" json:"opportunity_calculators"`
	PatternGenerators      PatternGeneratorsConfig      `toml:"pattern_generators" json:"pattern_generators"`
	SequenceGenerators     SequenceGeneratorsConfig     `toml:"sequence_generators" json:"sequence_generators"`
	Filters                FiltersConfig                `toml:"filters" json:"filters"`

	// Advanced settings
	TransactionCostFixed   float64 `toml:"transaction_cost_fixed" json:"transaction_cost_fixed"`
	TransactionCostPercent float64 `toml:"transaction_cost_percent" json:"transaction_cost_percent"`
	AllowSell              bool    `toml:"allow_sell" json:"allow_sell"`
	AllowBuy               bool    `toml:"allow_buy" json:"allow_buy"`
}

// NewDefaultConfiguration creates a PlannerConfiguration with default settings.
func NewDefaultConfiguration() *PlannerConfiguration {
	return &PlannerConfiguration{
		Name:                        "default",
		Description:                 "",
		EnableBatchGeneration:       true,
		MaxDepth:                    5,
		MaxOpportunitiesPerCategory: 5,
		PriorityThreshold:           0.3,
		BeamWidth:                   10,
		EnableDiverseSelection:      true,
		DiversityWeight:             0.3,
		TransactionCostFixed:        5.0,
		TransactionCostPercent:      0.001,
		AllowSell:                   true,
		AllowBuy:                    true,
		OpportunityCalculators: OpportunityCalculatorsConfig{
			ProfitTaking:    ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			AveragingDown:   ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			OpportunityBuys: ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			RebalanceSells:  ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			RebalanceBuys:   ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			WeightBased:     ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
		},
		PatternGenerators: PatternGeneratorsConfig{
			DirectBuy:        ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			ProfitTaking:     ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			Rebalance:        ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			AveragingDown:    ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			SingleBest:       ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			MultiSell:        ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			MixedStrategy:    ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			OpportunityFirst: ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			DeepRebalance:    ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			CashGeneration:   ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			CostOptimized:    ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			Adaptive:         ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			MarketRegime:     ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
		},
		SequenceGenerators: SequenceGeneratorsConfig{
			Combinatorial:         ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			EnhancedCombinatorial: ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			PartialExecution:      ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			ConstraintRelaxation:  ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
		},
		Filters: FiltersConfig{
			CorrelationAware: ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			Diversity:        ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			Eligibility:      ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
			RecentlyTraded:   ModuleConfig{Enabled: true, Params: make(map[string]interface{})},
		},
	}
}

// GetEnabledCalculators returns a list of enabled opportunity calculator names.
func (c *PlannerConfiguration) GetEnabledCalculators() []string {
	enabled := []string{}
	calculators := map[string]ModuleConfig{
		"profit_taking":    c.OpportunityCalculators.ProfitTaking,
		"averaging_down":   c.OpportunityCalculators.AveragingDown,
		"opportunity_buys": c.OpportunityCalculators.OpportunityBuys,
		"rebalance_sells":  c.OpportunityCalculators.RebalanceSells,
		"rebalance_buys":   c.OpportunityCalculators.RebalanceBuys,
		"weight_based":     c.OpportunityCalculators.WeightBased,
	}
	for name, config := range calculators {
		if config.Enabled {
			enabled = append(enabled, name)
		}
	}
	return enabled
}

// GetEnabledPatterns returns a list of enabled pattern generator names.
func (c *PlannerConfiguration) GetEnabledPatterns() []string {
	enabled := []string{}
	patterns := map[string]ModuleConfig{
		"direct_buy":        c.PatternGenerators.DirectBuy,
		"profit_taking":     c.PatternGenerators.ProfitTaking,
		"rebalance":         c.PatternGenerators.Rebalance,
		"averaging_down":    c.PatternGenerators.AveragingDown,
		"single_best":       c.PatternGenerators.SingleBest,
		"multi_sell":        c.PatternGenerators.MultiSell,
		"mixed_strategy":    c.PatternGenerators.MixedStrategy,
		"opportunity_first": c.PatternGenerators.OpportunityFirst,
		"deep_rebalance":    c.PatternGenerators.DeepRebalance,
		"cash_generation":   c.PatternGenerators.CashGeneration,
		"cost_optimized":    c.PatternGenerators.CostOptimized,
		"adaptive":          c.PatternGenerators.Adaptive,
		"market_regime":     c.PatternGenerators.MarketRegime,
	}
	for name, config := range patterns {
		if config.Enabled {
			enabled = append(enabled, name)
		}
	}
	return enabled
}

// GetEnabledGenerators returns a list of enabled sequence generator names.
func (c *PlannerConfiguration) GetEnabledGenerators() []string {
	enabled := []string{}
	generators := map[string]ModuleConfig{
		"combinatorial":          c.SequenceGenerators.Combinatorial,
		"enhanced_combinatorial": c.SequenceGenerators.EnhancedCombinatorial,
		"partial_execution":      c.SequenceGenerators.PartialExecution,
		"constraint_relaxation":  c.SequenceGenerators.ConstraintRelaxation,
	}
	for name, config := range generators {
		if config.Enabled {
			enabled = append(enabled, name)
		}
	}
	return enabled
}

// GetEnabledFilters returns a list of enabled filter names.
func (c *PlannerConfiguration) GetEnabledFilters() []string {
	enabled := []string{}
	filters := map[string]ModuleConfig{
		"correlation_aware": c.Filters.CorrelationAware,
		"diversity":         c.Filters.Diversity,
		"eligibility":       c.Filters.Eligibility,
		"recently_traded":   c.Filters.RecentlyTraded,
	}
	for name, config := range filters {
		if config.Enabled {
			enabled = append(enabled, name)
		}
	}
	return enabled
}

// GetCalculatorParams returns parameters for a specific calculator.
func (c *PlannerConfiguration) GetCalculatorParams(name string) map[string]interface{} {
	calculators := map[string]ModuleConfig{
		"profit_taking":    c.OpportunityCalculators.ProfitTaking,
		"averaging_down":   c.OpportunityCalculators.AveragingDown,
		"opportunity_buys": c.OpportunityCalculators.OpportunityBuys,
		"rebalance_sells":  c.OpportunityCalculators.RebalanceSells,
		"rebalance_buys":   c.OpportunityCalculators.RebalanceBuys,
		"weight_based":     c.OpportunityCalculators.WeightBased,
	}
	if config, ok := calculators[name]; ok {
		return config.Params
	}
	return make(map[string]interface{})
}

// GetPatternParams returns parameters for a specific pattern.
func (c *PlannerConfiguration) GetPatternParams(name string) map[string]interface{} {
	patterns := map[string]ModuleConfig{
		"direct_buy":        c.PatternGenerators.DirectBuy,
		"profit_taking":     c.PatternGenerators.ProfitTaking,
		"rebalance":         c.PatternGenerators.Rebalance,
		"averaging_down":    c.PatternGenerators.AveragingDown,
		"single_best":       c.PatternGenerators.SingleBest,
		"multi_sell":        c.PatternGenerators.MultiSell,
		"mixed_strategy":    c.PatternGenerators.MixedStrategy,
		"opportunity_first": c.PatternGenerators.OpportunityFirst,
		"deep_rebalance":    c.PatternGenerators.DeepRebalance,
		"cash_generation":   c.PatternGenerators.CashGeneration,
		"cost_optimized":    c.PatternGenerators.CostOptimized,
		"adaptive":          c.PatternGenerators.Adaptive,
		"market_regime":     c.PatternGenerators.MarketRegime,
	}
	if config, ok := patterns[name]; ok {
		return config.Params
	}
	return make(map[string]interface{})
}

// GetGeneratorParams returns parameters for a specific generator.
func (c *PlannerConfiguration) GetGeneratorParams(name string) map[string]interface{} {
	generators := map[string]ModuleConfig{
		"combinatorial":          c.SequenceGenerators.Combinatorial,
		"enhanced_combinatorial": c.SequenceGenerators.EnhancedCombinatorial,
		"partial_execution":      c.SequenceGenerators.PartialExecution,
		"constraint_relaxation":  c.SequenceGenerators.ConstraintRelaxation,
	}
	if config, ok := generators[name]; ok {
		return config.Params
	}
	return make(map[string]interface{})
}

// GetFilterParams returns parameters for a specific filter.
func (c *PlannerConfiguration) GetFilterParams(name string) map[string]interface{} {
	filters := map[string]ModuleConfig{
		"correlation_aware": c.Filters.CorrelationAware,
		"diversity":         c.Filters.Diversity,
		"eligibility":       c.Filters.Eligibility,
		"recently_traded":   c.Filters.RecentlyTraded,
	}
	if config, ok := filters[name]; ok {
		return config.Params
	}
	return make(map[string]interface{})
}
