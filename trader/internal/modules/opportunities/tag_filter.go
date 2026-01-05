package opportunities

import (
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/rs/zerolog"
)

// TagBasedFilter provides intelligent tag-based pre-filtering for opportunity identification.
// It uses tags to quickly reduce the candidate set from 100+ securities to 10-20,
// enabling focused calculations on a smaller, higher-quality set.
type TagBasedFilter struct {
	securityRepo *universe.SecurityRepository
	log          zerolog.Logger
}

// NewTagBasedFilter creates a new tag-based filter.
func NewTagBasedFilter(securityRepo *universe.SecurityRepository, log zerolog.Logger) *TagBasedFilter {
	return &TagBasedFilter{
		securityRepo: securityRepo,
		log:          log.With().Str("component", "tag_filter").Logger(),
	}
}

// GetOpportunityCandidates uses tags to quickly identify buying opportunity candidates.
// Returns a list of security symbols that match the selected opportunity tags.
func (f *TagBasedFilter) GetOpportunityCandidates(ctx *domain.OpportunityContext) ([]string, error) {
	if ctx == nil {
		return nil, nil
	}

	tags := f.selectOpportunityTags(ctx)
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
func (f *TagBasedFilter) GetSellCandidates(ctx *domain.OpportunityContext) ([]string, error) {
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
// Adapts tag selection based on available cash, market conditions, and strategy.
func (f *TagBasedFilter) selectOpportunityTags(ctx *domain.OpportunityContext) []string {
	tags := []string{}

	// Always include quality gates (enhanced tags)
	tags = append(tags, "quality-gate-pass", "high-quality")

	// Add value opportunities if we have sufficient cash
	if ctx.AvailableCashEUR > 1000 {
		tags = append(tags, "value-opportunity", "deep-value", "quality-value")
	}

	// Add technical opportunities if market is volatile
	if f.isMarketVolatile(ctx) {
		tags = append(tags, "oversold", "below-ema", "recovery-candidate")
	}

	// Add dividend opportunities (always relevant for long-term strategy)
	tags = append(tags, "dividend-opportunity", "high-dividend", "dividend-grower")

	// Add total return opportunities (enhanced tags)
	tags = append(tags, "high-total-return", "excellent-total-return")

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
func (f *TagBasedFilter) isMarketVolatile(ctx *domain.OpportunityContext) bool {
	// Check if many securities have volatility-spike tag
	volatileSecurities, err := f.securityRepo.GetByTags([]string{"volatility-spike"})
	if err != nil {
		f.log.Warn().Err(err).Msg("Failed to check market volatility")
		return false
	}

	// Threshold for "volatile market" - if 5+ securities have volatility spike, market is volatile
	return len(volatileSecurities) >= 5
}

