package scheduler

import (
	"database/sql"
	"fmt"
	"math"
	"time"

	"github.com/aristath/sentinel/internal/modules/dividends"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/pkg/formulas"
	"github.com/rs/zerolog"
)

// TagUpdateJob re-evaluates and updates tags for all securities daily
// Runs at 3:00 AM daily to update tags based on current conditions
type TagUpdateJob struct {
	JobBase
	log             zerolog.Logger
	securityRepo    *universe.SecurityRepository
	scoreRepo       *universe.ScoreRepository
	tagAssigner     *universe.TagAssigner
	yieldCalculator *dividends.DividendYieldCalculator
	historyDB       *universe.HistoryDB
	portfolioDB     *sql.DB
	positionRepo    *portfolio.PositionRepository
}

// TagUpdateConfig holds configuration for tag update job
type TagUpdateConfig struct {
	Log             zerolog.Logger
	SecurityRepo    *universe.SecurityRepository
	ScoreRepo       *universe.ScoreRepository
	TagAssigner     *universe.TagAssigner
	YieldCalculator *dividends.DividendYieldCalculator
	HistoryDB       *universe.HistoryDB
	PortfolioDB     *sql.DB
	PositionRepo    *portfolio.PositionRepository
}

// NewTagUpdateJob creates a new tag update job
func NewTagUpdateJob(cfg TagUpdateConfig) *TagUpdateJob {
	return &TagUpdateJob{
		log:             cfg.Log.With().Str("job", "tag_update").Logger(),
		securityRepo:    cfg.SecurityRepo,
		scoreRepo:       cfg.ScoreRepo,
		tagAssigner:     cfg.TagAssigner,
		yieldCalculator: cfg.YieldCalculator,
		historyDB:       cfg.HistoryDB,
		portfolioDB:     cfg.PortfolioDB,
		positionRepo:    cfg.PositionRepo,
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
		groupScores["stability"] = score.StabilityScore
		// QualityScore is average of (long_term + stability) / 2
		// Derive long_term from QualityScore and StabilityScore: long_term = 2 * QualityScore - stability
		// Use QualityScore as fallback if calculation would give invalid result
		if score.StabilityScore > 0 && score.QualityScore > 0 {
			derivedLongTerm := 2*score.QualityScore - score.StabilityScore
			if derivedLongTerm > 0 && derivedLongTerm <= 1.0 {
				groupScores["long_term"] = derivedLongTerm
			} else {
				// Fallback: use QualityScore if derivation gives invalid result
				// NOTE: This is a conservative fallback - QualityScore is an average, so it's typically lower than actual long_term
				// This may cause some securities to fail the quality gate even if they should pass
				groupScores["long_term"] = score.QualityScore
			}
		} else {
			// Fallback: use QualityScore if stability not available
			groupScores["long_term"] = score.QualityScore
		}
		groupScores["technicals"] = score.TechnicalScore
		groupScores["dividends"] = score.DividendBonus // Approximate

		// Map sub-scores
		subScores["stability"] = map[string]float64{
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

		// Try to get raw CAGR from scores table for return-based tagging
		// Use ISIN directly (PRIMARY KEY lookup - fastest)
		if j.portfolioDB != nil && security.ISIN != "" {
			var cagrScore sql.NullFloat64
			err := j.portfolioDB.QueryRow(`
				SELECT cagr_score
				FROM scores
				WHERE isin = ? AND cagr_score IS NOT NULL AND cagr_score > 0
				ORDER BY last_updated DESC
				LIMIT 1
			`, security.ISIN).Scan(&cagrScore)
			if err == nil && cagrScore.Valid && cagrScore.Float64 > 0 {
				// Convert normalized cagr_score back to approximate CAGR percentage
				// convertCAGRScoreToCAGR converts normalized cagr_score (0-1) back to approximate CAGR percentage.
				// Reverse mapping based on scoreCAGRWithBubbleDetection logic:
				// - cagr_score 1.0 → ~20% CAGR (excellent)
				// - cagr_score 0.8 → ~11% CAGR (target)
				// - cagr_score 0.5 → ~6-8% CAGR (below target)
				// - cagr_score 0.15 → 0% CAGR (floor)
				// Linear interpolation between key points
				convertCAGRScoreToCAGR := func(cagrScore float64) float64 {
					if cagrScore <= 0 {
						return 0.0
					}

					var cagrValue float64
					if cagrScore >= 0.8 {
						// Above target: 0.8 (11%) to 1.0 (20%)
						cagrValue = 0.11 + (cagrScore-0.8)*(0.20-0.11)/(1.0-0.8)
					} else if cagrScore >= 0.15 {
						// Below target: 0.15 (0%) to 0.8 (11%)
						cagrValue = 0.0 + (cagrScore-0.15)*(0.11-0.0)/(0.8-0.15)
					} else {
						// At or below floor
						cagrValue = 0.0
					}

					return cagrValue
				}
				cagrRaw := convertCAGRScoreToCAGR(cagrScore.Float64)
				if cagrRaw > 0 {
					// Add cagr_raw to sub-scores if not already present
					if subScores["long_term"] == nil {
						subScores["long_term"] = make(map[string]float64)
					}
					subScores["long_term"]["cagr_raw"] = cagrRaw
				}
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

	// Get dividend yield from internal calculator (no external data source needed)
	var dividendYield *float64
	var fiveYearAvgDivYield *float64
	if j.yieldCalculator != nil && security.ISIN != "" {
		yieldResult, err := j.yieldCalculator.CalculateYield(security.ISIN)
		if err == nil && yieldResult != nil {
			if yieldResult.CurrentYield > 0 {
				dividendYield = &yieldResult.CurrentYield
			}
			if yieldResult.FiveYearAvgYield > 0 {
				fiveYearAvgDivYield = &yieldResult.FiveYearAvgYield
			}
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
		var firstBoughtUnix sql.NullInt64
		err := j.portfolioDB.QueryRow(`
			SELECT quantity, avg_price, current_price, market_value_eur, cost_basis_eur, first_bought
			FROM positions
			WHERE symbol = ?
		`, security.Symbol).Scan(&quantity, &avgPrice, &currentPriceDB, &marketValueEUR, &costBasisEUR, &firstBoughtUnix)

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

			// Calculate days held from first_bought Unix timestamp
			if firstBoughtUnix.Valid {
				firstBoughtTime := time.Unix(firstBoughtUnix.Int64, 0).UTC()
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

	// Replace all tags atomically - ensures stale tags are removed
	// SetTagsForSecurity deletes existing tags and inserts the new set,
	// which correctly removes tags that no longer apply (e.g., quality-gate-fail
	// when a security now passes the quality gate)
	if err := j.securityRepo.SetTagsForSecurity(security.Symbol, allTagIDs); err != nil {
		return fmt.Errorf("failed to set tags: %w", err)
	}

	j.log.Debug().
		Str("symbol", security.Symbol).
		Int("tag_count", len(allTagIDs)).
		Msg("Tags replaced for security")

	return nil
}

// getTargetReturnSettings fetches target return and threshold from settings
// Returns defaults: 0.11 (11%) target, 0.80 (80%) threshold
// These match the system defaults in planning/domain/config.go
func (j *TagUpdateJob) getTargetReturnSettings() (float64, float64) {
	targetReturn := 0.11 // 11% - matches DefaultConfig().OptimizerTargetReturn
	thresholdPct := 0.80 // 80% - standard threshold
	return targetReturn, thresholdPct
}
