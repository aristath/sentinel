package scheduler

import (
	"database/sql"
	"fmt"
	"math"
	"time"

	"github.com/aristath/arduino-trader/internal/clients/yahoo"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/aristath/arduino-trader/pkg/formulas"
	"github.com/rs/zerolog"
)

// TagUpdateJob re-evaluates and updates tags for all securities daily
// Runs at 3:00 AM daily to update tags based on current conditions
type TagUpdateJob struct {
	log          zerolog.Logger
	securityRepo *universe.SecurityRepository
	scoreRepo    *universe.ScoreRepository
	tagAssigner  *universe.TagAssigner
	yahooClient  yahoo.FullClientInterface
	historyDB    *universe.HistoryDB
	portfolioDB  *sql.DB
	positionRepo *portfolio.PositionRepository
}

// TagUpdateConfig holds configuration for tag update job
type TagUpdateConfig struct {
	Log          zerolog.Logger
	SecurityRepo *universe.SecurityRepository
	ScoreRepo    *universe.ScoreRepository
	TagAssigner  *universe.TagAssigner
	YahooClient  yahoo.FullClientInterface
	HistoryDB    *universe.HistoryDB
	PortfolioDB  *sql.DB
	PositionRepo *portfolio.PositionRepository
}

// NewTagUpdateJob creates a new tag update job
func NewTagUpdateJob(cfg TagUpdateConfig) *TagUpdateJob {
	return &TagUpdateJob{
		log:          cfg.Log.With().Str("job", "tag_update").Logger(),
		securityRepo: cfg.SecurityRepo,
		scoreRepo:    cfg.ScoreRepo,
		tagAssigner:  cfg.TagAssigner,
		yahooClient:  cfg.YahooClient,
		historyDB:    cfg.HistoryDB,
		portfolioDB:  cfg.PortfolioDB,
		positionRepo: cfg.PositionRepo,
	}
}

// Name returns the job name
func (j *TagUpdateJob) Name() string {
	return "tag_update"
}

// Run executes the tag update for all active securities
func (j *TagUpdateJob) Run() error {
	j.log.Info().Msg("Starting daily tag update")

	// Get all active securities
	securities, err := j.securityRepo.GetAllActive()
	if err != nil {
		return fmt.Errorf("failed to get active securities: %w", err)
	}

	if len(securities) == 0 {
		j.log.Info().Msg("No active securities to update tags for")
		return nil
	}

	j.log.Info().Int("count", len(securities)).Msg("Processing securities for tag update")

	var processedCount int
	var errorCount int
	var tagsUpdatedCount int

	// Process each security
	for _, security := range securities {
		if err := j.updateTagsForSecurity(security); err != nil {
			errorCount++
			j.log.Warn().
				Err(err).
				Str("symbol", security.Symbol).
				Msg("Failed to update tags for security, continuing with next")
			continue
		}
		processedCount++
	}

	// Get summary of tags updated
	tagsUpdatedCount = processedCount

	j.log.Info().
		Int("processed", processedCount).
		Int("errors", errorCount).
		Int("total", len(securities)).
		Int("tags_updated", tagsUpdatedCount).
		Msg("Tag update completed")

	if errorCount > 0 {
		return fmt.Errorf("tag update completed with %d errors out of %d securities", errorCount, len(securities))
	}

	return nil
}

// updateTagsForSecurity updates tags for a single security
// Enhanced with per-tag update frequencies - only updates tags that need updating
func (j *TagUpdateJob) updateTagsForSecurity(security universe.Security) error {
	// Get current tags with their update times
	currentTagsWithTimes, err := j.securityRepo.GetTagsWithUpdateTimes(security.Symbol)
	if err != nil {
		j.log.Debug().
			Err(err).
			Str("symbol", security.Symbol).
			Msg("Failed to get current tags with update times, will update all tags")
		currentTagsWithTimes = make(map[string]time.Time) // Empty map - will update all
	}

	// Determine which tags need updating based on frequency
	now := time.Now()
	tagsNeedingUpdate := GetTagsNeedingUpdate(currentTagsWithTimes, now)

	if len(tagsNeedingUpdate) == 0 {
		// All tags are fresh - skip update
		j.log.Debug().
			Str("symbol", security.Symbol).
			Msg("All tags are fresh, skipping update")
		return nil
	}

	j.log.Debug().
		Str("symbol", security.Symbol).
		Int("tags_needing_update", len(tagsNeedingUpdate)).
		Msg("Tags need updating")
	// Get current score
	score, err := j.scoreRepo.GetBySymbol(security.Symbol)
	if err != nil {
		j.log.Debug().Err(err).Str("symbol", security.Symbol).Msg("Failed to get score, continuing without")
		// Continue without score - tags can still be assigned based on other data
	}

	// Get group scores and sub-scores from score (if available)
	// Note: SecurityScore doesn't have group/sub scores directly, so we'll need to extract what we can
	groupScores := make(map[string]float64)
	subScores := make(map[string]map[string]float64)

	if score != nil {
		// Map available scores to group scores
		groupScores["opportunity"] = score.OpportunityScore
		groupScores["fundamentals"] = score.FundamentalScore
		// QualityScore is average of (long_term + fundamentals) / 2
		// Derive long_term from QualityScore and FundamentalScore: long_term = 2 * QualityScore - fundamentals
		// Use QualityScore as fallback if calculation would give invalid result
		if score.FundamentalScore > 0 && score.QualityScore > 0 {
			derivedLongTerm := 2*score.QualityScore - score.FundamentalScore
			if derivedLongTerm > 0 && derivedLongTerm <= 1.0 {
				groupScores["long_term"] = derivedLongTerm
			} else {
				// Fallback: use QualityScore if derivation gives invalid result
				groupScores["long_term"] = score.QualityScore
			}
		} else {
			// Fallback: use QualityScore if fundamentals not available
			groupScores["long_term"] = score.QualityScore
		}
		groupScores["technicals"] = score.TechnicalScore
		groupScores["dividends"] = score.DividendBonus // Approximate

		// Map sub-scores
		subScores["fundamentals"] = map[string]float64{
			"consistency": score.ConsistencyScore,
		}
		subScores["long_term"] = map[string]float64{
			"cagr": score.CAGRScore,
		}

		// Get raw Sharpe ratio from scores table (sharpe_score column stores raw value)
		if score.SharpeScore > 0 {
			if subScores["long_term"] == nil {
				subScores["long_term"] = make(map[string]float64)
			}
			subScores["long_term"]["sharpe_raw"] = score.SharpeScore
		}

		// Try to get raw CAGR from calculated_metrics for return-based tagging
		if j.portfolioDB != nil {
			var cagrRaw sql.NullFloat64
			err := j.portfolioDB.QueryRow(`
				SELECT COALESCE(
					MAX(CASE WHEN metric_name = 'CAGR_5Y' THEN metric_value END),
					MAX(CASE WHEN metric_name = 'CAGR_10Y' THEN metric_value END)
				) as cagr
				FROM calculated_metrics
				WHERE symbol = ? AND metric_name IN ('CAGR_5Y', 'CAGR_10Y')
			`, security.Symbol).Scan(&cagrRaw)
			if err == nil && cagrRaw.Valid && cagrRaw.Float64 > 0 {
				// Add cagr_raw to sub-scores if not already present
				if subScores["long_term"] == nil {
					subScores["long_term"] = make(map[string]float64)
				}
				subScores["long_term"]["cagr_raw"] = cagrRaw.Float64
			}
		}
	}

	// Get daily prices for technical analysis using ISIN
	// We'll also use these to calculate Sortino ratio if needed
	var dailyPrices []universe.DailyPrice
	if security.ISIN == "" {
		j.log.Debug().Str("symbol", security.Symbol).Msg("Security has no ISIN, skipping daily prices")
		dailyPrices = []universe.DailyPrice{} // Initialize empty slice to avoid nil
	} else {
		var err error
		dailyPrices, err = j.historyDB.GetDailyPrices(security.ISIN, 400)
		if err != nil {
			j.log.Debug().Err(err).Str("symbol", security.Symbol).Str("isin", security.ISIN).Msg("Failed to get daily prices, continuing without")
			dailyPrices = []universe.DailyPrice{} // Initialize empty slice to avoid nil
		}
	}

	// Extract close prices
	closePrices := make([]float64, len(dailyPrices))
	for i, dp := range dailyPrices {
		closePrices[i] = dp.Close
	}

	// Calculate Sortino ratio from daily prices if we have enough data
	// This is needed for bubble detection tags which require sortino_raw
	if len(closePrices) >= 50 {
		// Calculate returns from prices
		returns := formulas.CalculateReturns(closePrices)
		if len(returns) >= 2 {
			// Calculate Sortino ratio with 2% risk-free rate and 11% target return (0.11)
			// Using 252 periods per year for daily data
			sortinoRatio := formulas.CalculateSortinoRatio(returns, 0.02, 0.11, 252)
			if sortinoRatio != nil && *sortinoRatio > 0 {
				// Add sortino_raw to sub-scores
				if subScores["long_term"] == nil {
					subScores["long_term"] = make(map[string]float64)
				}
				subScores["long_term"]["sortino_raw"] = *sortinoRatio
			}
		}
	}

	// Get current price (latest close)
	var currentPrice *float64
	var price52wHigh *float64
	var price52wLow *float64
	if len(closePrices) > 0 {
		currentPrice = &closePrices[len(closePrices)-1]
		// Calculate 52W high/low from daily prices
		if len(closePrices) >= 252 {
			recentPrices := closePrices[len(closePrices)-252:]
			high := recentPrices[0]
			low := recentPrices[0]
			for _, p := range recentPrices {
				if p > high {
					high = p
				}
				if p < low {
					low = p
				}
			}
			price52wHigh = &high
			price52wLow = &low
		}
	}

	// Get fundamentals from Yahoo (for P/E ratio, dividend yield)
	var peRatio *float64
	var dividendYield *float64
	var fiveYearAvgDivYield *float64
	if j.yahooClient != nil {
		var yahooSymPtr *string
		if security.YahooSymbol != "" {
			yahooSymPtr = &security.YahooSymbol
		}
		fundamentals, err := j.yahooClient.GetFundamentalData(security.Symbol, yahooSymPtr)
		if err == nil && fundamentals != nil {
			peRatio = fundamentals.PERatio
			dividendYield = fundamentals.DividendYield
			fiveYearAvgDivYield = fundamentals.FiveYearAvgDividendYield
		}
	}

	// Get position data (for portfolio risk tags)
	var positionWeight *float64
	var targetWeight *float64
	var annualizedReturn *float64
	var daysHeld *int
	if j.positionRepo != nil {
		// Query position data
		var quantity, avgPrice, currentPriceDB, marketValueEUR, costBasisEUR sql.NullFloat64
		var firstBought sql.NullString
		err := j.portfolioDB.QueryRow(`
			SELECT quantity, avg_price, current_price, market_value_eur, cost_basis_eur, first_bought
			FROM positions
			WHERE symbol = ?
		`, security.Symbol).Scan(&quantity, &avgPrice, &currentPriceDB, &marketValueEUR, &costBasisEUR, &firstBought)

		if err == nil && quantity.Valid && marketValueEUR.Valid {
			// Calculate position weight
			totalValue, err := j.positionRepo.GetTotalValue()
			if err == nil && totalValue > 0 {
				weight := marketValueEUR.Float64 / totalValue
				positionWeight = &weight
			}

			// Get target weight from security (if available)
			if security.MinPortfolioTarget > 0 || security.MaxPortfolioTarget > 0 {
				// Use average of min and max if both set, otherwise use the one that's set
				var target float64
				if security.MinPortfolioTarget > 0 && security.MaxPortfolioTarget > 0 {
					target = (security.MinPortfolioTarget + security.MaxPortfolioTarget) / 2.0
				} else if security.MinPortfolioTarget > 0 {
					target = security.MinPortfolioTarget
				} else if security.MaxPortfolioTarget > 0 {
					target = security.MaxPortfolioTarget
				}
				if target > 0 {
					targetWeight = &target
				}
			}

			// Calculate days held from first_bought date
			if firstBought.Valid && firstBought.String != "" {
				// Try parsing as RFC3339 (ISO 8601)
				firstBoughtTime, err := time.Parse(time.RFC3339, firstBought.String)
				if err != nil {
					// Try alternative formats
					formats := []string{
						"2006-01-02 15:04:05",
						"2006-01-02T15:04:05Z",
						"2006-01-02",
					}
					for _, format := range formats {
						if t, parseErr := time.Parse(format, firstBought.String); parseErr == nil {
							firstBoughtTime = t
							err = nil
							break
						}
					}
				}

				if err == nil {
					days := int(time.Since(firstBoughtTime).Hours() / 24)
					daysHeld = &days

					// Calculate annualized return if we have cost basis and market value
					if costBasisEUR.Valid && costBasisEUR.Float64 > 0 && days > 0 {
						years := float64(days) / 365.0
						if years > 0 {
							returnPct := (marketValueEUR.Float64 - costBasisEUR.Float64) / costBasisEUR.Float64
							if returnPct > -1.0 { // Avoid negative base for power calculation
								annualized := math.Pow(1.0+returnPct, 1.0/years) - 1.0
								annualizedReturn = &annualized
							}
						}
					}
				}
			}
		}
	}

	// Extract volatility and other metrics from score (if available)
	var volatility *float64
	var ema200 *float64
	var rsi *float64
	var maxDrawdown *float64
	if score != nil {
		volatility = &score.Volatility
		ema200 = &score.EMA200
		rsi = &score.RSI
		maxDrawdown = &score.DrawdownScore
	}

	// Get target return settings (use defaults if not available)
	targetReturn, targetReturnThresholdPct := j.getTargetReturnSettings()

	// Build tag assignment input
	tagInput := universe.AssignTagsInput{
		Symbol:                   security.Symbol,
		Security:                 security,
		Score:                    score,
		GroupScores:              groupScores,
		SubScores:                subScores,
		Volatility:               volatility,
		DailyPrices:              closePrices,
		PERatio:                  peRatio,
		MarketAvgPE:              20.0, // Default market average P/E
		DividendYield:            dividendYield,
		FiveYearAvgDivYield:      fiveYearAvgDivYield,
		CurrentPrice:             currentPrice,
		Price52wHigh:             price52wHigh,
		Price52wLow:              price52wLow,
		EMA200:                   ema200,
		RSI:                      rsi,
		MaxDrawdown:              maxDrawdown,
		PositionWeight:           positionWeight,
		TargetWeight:             targetWeight,
		AnnualizedReturn:         annualizedReturn,
		DaysHeld:                 daysHeld,
		TargetReturn:             targetReturn,
		TargetReturnThresholdPct: targetReturnThresholdPct,
	}

	// Assign all tags (fast operation - just calculation)
	allTagIDs, err := j.tagAssigner.AssignTagsForSecurity(tagInput)
	if err != nil {
		return fmt.Errorf("failed to assign tags: %w", err)
	}

	// Filter to only tags that need updating
	tagsToUpdate := make([]string, 0)
	for _, tagID := range allTagIDs {
		if tagsNeedingUpdate[tagID] {
			tagsToUpdate = append(tagsToUpdate, tagID)
		}
	}

	// Also include any new tags that weren't in current tags
	currentTagSet := make(map[string]bool)
	for tagID := range currentTagsWithTimes {
		currentTagSet[tagID] = true
	}
	for _, tagID := range allTagIDs {
		if !currentTagSet[tagID] {
			// New tag - add it
			tagsToUpdate = append(tagsToUpdate, tagID)
		}
	}

	if len(tagsToUpdate) == 0 {
		// No tags need updating (shouldn't happen, but handle gracefully)
		j.log.Debug().
			Str("symbol", security.Symbol).
			Msg("No tags need updating after filtering")
		return nil
	}

	// Update only the tags that need updating (preserves other tags)
	if err := j.securityRepo.UpdateSpecificTags(security.Symbol, tagsToUpdate); err != nil {
		return fmt.Errorf("failed to update specific tags: %w", err)
	}

	j.log.Debug().
		Str("symbol", security.Symbol).
		Int("tags_updated", len(tagsToUpdate)).
		Strs("updated_tags", tagsToUpdate).
		Msg("Tags updated for security (per-tag frequency)")

	return nil
}

// getTargetReturnSettings fetches target return and threshold from settings
// Returns defaults if not available: 0.11 (11%) target, 0.80 (80%) threshold
func (j *TagUpdateJob) getTargetReturnSettings() (float64, float64) {
	// Use defaults for now (can be enhanced to query from configDB if available)
	targetReturn := 0.11 // Default: 11%
	thresholdPct := 0.80 // Default: 80%

	// TODO: Query from configDB if available (similar to planner_batch.go)
	// For now, use defaults which match the system defaults

	return targetReturn, thresholdPct
}
