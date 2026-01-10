package opportunities

import (
	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// TagBasedFilter provides intelligent tag-based pre-filtering for opportunity identification.
// It uses tags to quickly reduce the candidate set from 100+ securities to 10-20,
// enabling focused calculations on a smaller, higher-quality set.
// Follows Dependency Inversion Principle - depends on SecurityRepository interface.
type TagBasedFilter struct {
	securityRepo SecurityRepository
	log          zerolog.Logger
}

// NewTagBasedFilter creates a new tag-based filter.
// Accepts SecurityRepository interface, not concrete implementation.
func NewTagBasedFilter(securityRepo SecurityRepository, log zerolog.Logger) *TagBasedFilter {
	return &TagBasedFilter{
		securityRepo: securityRepo,
		log:          log.With().Str("component", "tag_filter").Logger(),
	}
}

// GetOpportunityCandidates uses tags to quickly identify buying opportunity candidates.
// Returns a list of security symbols that match the selected opportunity tags.
// If config is provided and EnableTagFiltering is false, returns all active securities.
func (f *TagBasedFilter) GetOpportunityCandidates(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration) ([]string, error) {
	if ctx == nil {
		return nil, nil
	}

	// If tag filtering is disabled, return all active securities
	if config != nil && !config.EnableTagFiltering {
		f.log.Debug().Msg("Tag filtering disabled, returning all active securities")
		allSecurities, err := f.securityRepo.GetAllActive()
		if err != nil {
			return nil, err
		}

		symbols := make([]string, 0, len(allSecurities))
		for _, sec := range allSecurities {
			if sec.Symbol != "" {
				symbols = append(symbols, sec.Symbol)
			}
		}

		f.log.Debug().
			Int("candidates", len(symbols)).
			Msg("Returned all active securities (tag filtering disabled)")

		return symbols, nil
	}

	tags := f.selectOpportunityTags(ctx, config)
	if len(tags) == 0 {
		f.log.Debug().Msg("No opportunity tags selected")
		return []string{}, nil
	}

	f.log.Debug().
		Strs("tags", tags).
		Msg("Selecting opportunity candidates by tags")

	candidates, err := f.securityRepo.GetByTags(tags)
	if err != nil {
		return nil, err
	}

	symbols := make([]string, 0, len(candidates))
	for _, c := range candidates {
		if c.Symbol != "" {
			symbols = append(symbols, c.Symbol)
		}
	}

	f.log.Debug().
		Int("candidates", len(symbols)).
		Msg("Tag-based pre-filtering complete")

	return symbols, nil
}

// GetSellCandidates uses tags to quickly identify selling opportunity candidates.
// Returns a list of security symbols from positions that match sell-related tags.
// If config is provided and EnableTagFiltering is false, returns all position symbols.
func (f *TagBasedFilter) GetSellCandidates(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration) ([]string, error) {
	if ctx == nil || len(ctx.Positions) == 0 {
		return []string{}, nil
	}

	// Get position symbols
	positionSymbols := make([]string, 0, len(ctx.Positions))
	for _, pos := range ctx.Positions {
		if pos.Symbol != "" {
			positionSymbols = append(positionSymbols, pos.Symbol)
		}
	}

	if len(positionSymbols) == 0 {
		return []string{}, nil
	}

	// If tag filtering is disabled, return all position symbols
	if config != nil && !config.EnableTagFiltering {
		f.log.Debug().
			Int("candidates", len(positionSymbols)).
			Msg("Returned all position symbols (tag filtering disabled)")
		return positionSymbols, nil
	}

	tags := f.selectSellTags(ctx)
	if len(tags) == 0 {
		f.log.Debug().Msg("No sell tags selected")
		return []string{}, nil
	}

	f.log.Debug().
		Strs("tags", tags).
		Int("positions", len(positionSymbols)).
		Msg("Selecting sell candidates by tags")

	candidates, err := f.securityRepo.GetPositionsByTags(positionSymbols, tags)
	if err != nil {
		return nil, err
	}

	symbols := make([]string, 0, len(candidates))
	for _, c := range candidates {
		if c.Symbol != "" {
			symbols = append(symbols, c.Symbol)
		}
	}

	f.log.Debug().
		Int("candidates", len(symbols)).
		Msg("Tag-based sell pre-filtering complete")

	return symbols, nil
}

// selectOpportunityTags intelligently selects tags based on opportunity context.
// Adapts tag selection based on available cash, market conditions, strategy, and market regime.
func (f *TagBasedFilter) selectOpportunityTags(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration) []string {
	tags := []string{}

	// Always include high-quality securities
	// Note: We don't pre-filter by quality-gate-pass anymore (removed)
	// Instead, calculators will exclude quality-gate-fail
	tags = append(tags, "high-quality")

	// Detect current market regime for regime-specific tag selection
	regime := "neutral"
	if f.securityRepo != nil {
		// Use same DetectCurrentRegime logic from calculators
		bearSafe, _ := f.securityRepo.GetByTags([]string{"regime-bear-safe"})
		bullGrowth, _ := f.securityRepo.GetByTags([]string{"regime-bull-growth"})
		sidewaysValue, _ := f.securityRepo.GetByTags([]string{"regime-sideways-value"})
		volatile, _ := f.securityRepo.GetByTags([]string{"regime-volatile"})

		if len(volatile) > 10 {
			regime = "volatile"
		} else if len(bullGrowth) > len(bearSafe) && len(bullGrowth) > len(sidewaysValue) {
			regime = "bull"
		} else if len(bearSafe) > len(bullGrowth) && len(bearSafe) > len(sidewaysValue) {
			regime = "bear"
		} else if len(sidewaysValue) > len(bullGrowth) && len(sidewaysValue) > len(bearSafe) {
			regime = "sideways"
		}
	}

	// Regime-specific tag selection
	switch regime {
	case "bear":
		// Bear market: Focus on defensive, value, and dividend securities
		tags = append(tags, "regime-bear-safe", "value-opportunity", "deep-value", "quality-value")
		tags = append(tags, "dividend-opportunity", "high-dividend", "dividend-grower")
	case "bull":
		// Bull market: Focus on growth and momentum
		tags = append(tags, "regime-bull-growth", "recovery-candidate", "oversold")
		tags = append(tags, "high-total-return", "excellent-total-return")
	case "sideways":
		// Sideways market: Focus on dividends and value
		tags = append(tags, "regime-sideways-value", "dividend-opportunity", "high-dividend")
		tags = append(tags, "value-opportunity", "deep-value")
	case "volatile":
		// Volatile market: Focus on defensive and oversold opportunities
		tags = append(tags, "regime-bear-safe", "low-risk", "stable")
		tags = append(tags, "oversold", "recovery-candidate")
	default:
		// Neutral market: Use balanced approach
		// Add value opportunities if we have sufficient cash
		if ctx.AvailableCashEUR > 1000 {
			tags = append(tags, "value-opportunity", "deep-value", "quality-value")
		}
		// Add technical opportunities if market is volatile (legacy check)
		if f.IsMarketVolatile(ctx, config) {
			tags = append(tags, "oversold", "recovery-candidate") // Note: below-ema tag was deleted
		}
		// Add dividend opportunities (always relevant for long-term strategy)
		tags = append(tags, "dividend-opportunity", "high-dividend", "dividend-grower")
		// Add total return opportunities (enhanced tags)
		tags = append(tags, "high-total-return", "excellent-total-return")
	}

	// Exclude value traps and bubble risks (use negative filtering in calculators)
	// We don't add these to tags list, but calculators should check for them

	return tags
}

// selectSellTags intelligently selects tags for identifying sell opportunities.
func (f *TagBasedFilter) selectSellTags(ctx *domain.OpportunityContext) []string {
	tags := []string{}

	// Price-based sell signals
	tags = append(tags, "overvalued", "near-52w-high", "overbought")

	// Portfolio-based sell signals
	tags = append(tags, "overweight", "concentration-risk")

	// Optimizer alignment sell signals (enhanced tags)
	tags = append(tags, "needs-rebalance", "slightly-overweight")

	// Bubble detection sell signals (enhanced tags)
	tags = append(tags, "bubble-risk")

	return tags
}

// isMarketVolatile determines if market conditions are volatile.
// Checks if many securities have volatility-spike tag as a proxy for market volatility.
// Falls back to checking all securities if tags are disabled.
func (f *TagBasedFilter) IsMarketVolatile(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration) bool {
	// If tag filtering is disabled, we can't use tags to check volatility
	// Return false (conservative: assume market is not volatile)
	if config != nil && !config.EnableTagFiltering {
		f.log.Debug().Msg("Tag filtering disabled, cannot check market volatility via tags")
		return false
	}

	// Check if many securities have volatility-spike tag
	volatileSecurities, err := f.securityRepo.GetByTags([]string{"volatility-spike"})
	if err != nil {
		f.log.Warn().Err(err).Msg("Failed to check market volatility")
		return false
	}

	// Threshold for "volatile market" - if 5+ securities have volatility spike, market is volatile
	return len(volatileSecurities) >= 5
}
