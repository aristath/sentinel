/**
 * Package services provides SecurityService that loads complete Security data from all sources.
 *
 * SecurityService is the single entry point for getting a complete Security with ALL data:
 * - Basic security data from universe.db
 * - Scores from portfolio.db
 * - Position data from portfolio.db (if held)
 * - Tags from universe.db
 * - Current price from broker API or cache
 *
 * Usage:
 *   security, _ := securityService.Get("FR0014004L86")
 *   name := security.Name
 *   cagr := security.CAGRScore
 *   prices, _ := securityService.GetHistoricalData("FR0014004L86", HistoricalDataOptions{...})
 */
package services

import (
	"fmt"
	"strings"
	"time"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

/**
 * SecurityService loads complete Security data from all sources.
 *
 * This service coordinates loading data from multiple repositories and databases
 * to return a single Security struct with everything populated.
 */
type SecurityService struct {
	securityRepo *universe.SecurityRepository
	scoreRepo    *universe.ScoreRepository
	positionRepo *portfolio.PositionRepository
	historyDB    universe.HistoryDBInterface
	priceClient  PriceClient // Optional - for current price fetching
	log          zerolog.Logger
}

/**
 * NewSecurityService creates a new SecurityService.
 *
 * Parameters:
 *   - securityRepo: Repository for basic security data
 *   - scoreRepo: Repository for security scores
 *   - positionRepo: Repository for position data
 *   - historyDB: History database client for historical prices
 *   - priceClient: Optional price client for current prices
 *   - tagRepo: Repository for security tags
 *   - log: Structured logger
 */
func NewSecurityService(
	securityRepo *universe.SecurityRepository,
	scoreRepo *universe.ScoreRepository,
	positionRepo *portfolio.PositionRepository,
	historyDB universe.HistoryDBInterface,
	priceClient PriceClient,
	log zerolog.Logger,
) *SecurityService {
	return &SecurityService{
		securityRepo: securityRepo,
		scoreRepo:    scoreRepo,
		positionRepo: positionRepo,
		historyDB:    historyDB,
		priceClient:  priceClient,
		log:          log.With().Str("service", "security").Logger(),
	}
}

/**
 * Get loads a complete Security with ALL data from all sources.
 *
 * This is the single method to get a security - it loads:
 * - Basic security data (name, symbol, geography, etc.)
 * - Scores (quality, opportunity, CAGR, etc.)
 * - Position data (if held)
 * - Tags
 * - Current price (if available)
 *
 * Parameters:
 *   - isin: Security ISIN (primary identifier)
 *
 * Returns:
 *   - *domain.Security: Complete security with all data, or nil if not found
 *   - error: Error if loading fails
 */
func (s *SecurityService) Get(isin string) (*domain.Security, error) {
	s.log.Debug().Str("isin", isin).Msg("Loading complete security data")

	// Normalize ISIN
	isin = normalizeISIN(isin)

	// Load basic security data (required)
	sec, err := s.securityRepo.GetByISIN(isin)
	if err != nil {
		return nil, fmt.Errorf("failed to load security: %w", err)
	}
	if sec == nil {
		return nil, nil // Security not found
	}

	// Convert to domain.Security
	security := &domain.Security{
		ISIN:               sec.ISIN,
		Symbol:             sec.Symbol,
		Name:               sec.Name,
		ProductType:        sec.ProductType,
		Currency:           sec.Currency,
		Geography:          sec.Geography,
		Industry:           sec.Industry,
		FullExchangeName:   sec.FullExchangeName,
		MarketCode:         sec.MarketCode,
		MinLot:             float64(sec.MinLot), // Convert int to float64
		MinPortfolioTarget: sec.MinPortfolioTarget,
		MaxPortfolioTarget: sec.MaxPortfolioTarget,
		AllowBuy:           sec.AllowBuy,
		AllowSell:          sec.AllowSell,
		PriorityMultiplier: sec.PriorityMultiplier,
		LastSynced:         sec.LastSynced,
	}

	// Load scores (optional - might not exist)
	if score, err := s.scoreRepo.GetByISIN(isin); err == nil && score != nil {
		security.TotalScore = &score.TotalScore
		security.QualityScore = &score.QualityScore
		security.OpportunityScore = &score.OpportunityScore
		security.ConsistencyScore = &score.ConsistencyScore
		security.CAGRScore = &score.CAGRScore
		security.TechnicalScore = &score.TechnicalScore
		security.StabilityScore = &score.StabilityScore
		security.AllocationFitScore = &score.AllocationFitScore
		security.AnalystScore = &score.AnalystScore
		security.SellScore = &score.SellScore
		security.RSI = &score.RSI
		security.EMA200 = &score.EMA200
		security.Below52wHighPct = &score.Below52wHighPct
		security.Volatility = &score.Volatility
		security.SharpeScore = &score.SharpeScore
		security.DrawdownScore = &score.DrawdownScore
		security.FinancialStrengthScore = &score.FinancialStrengthScore
		security.DividendBonus = &score.DividendBonus
		historyYears := int(score.HistoryYears)
		if historyYears > 0 {
			security.HistoryYears = &historyYears
		}
		if score.CalculatedAt != nil {
			security.CalculatedAt = score.CalculatedAt
		}
	}

	// Load position (optional - might not be held)
	if pos, err := s.positionRepo.GetByISIN(isin); err == nil && pos != nil {
		security.PositionQuantity = &pos.Quantity
		security.PositionAvgPrice = &pos.AvgPrice
		security.PositionCurrency = &pos.Currency
		security.PositionCurrencyRate = &pos.CurrencyRate
		security.PositionMarketValueEUR = &pos.MarketValueEUR
		security.PositionCostBasisEUR = &pos.CostBasisEUR
		security.PositionUnrealizedPnL = &pos.UnrealizedPnL
		security.PositionUnrealizedPnLPct = &pos.UnrealizedPnLPct

		// Convert Unix timestamps to time.Time
		if pos.LastUpdated != nil {
			t := time.Unix(*pos.LastUpdated, 0).UTC()
			security.PositionLastUpdated = &t
		}
		if pos.FirstBoughtAt != nil {
			t := time.Unix(*pos.FirstBoughtAt, 0).UTC()
			security.PositionFirstBoughtAt = &t
		}
		if pos.LastSoldAt != nil {
			t := time.Unix(*pos.LastSoldAt, 0).UTC()
			security.PositionLastSoldAt = &t
		}
	}

	// Load tags (optional - might fail)
	// SecurityRepository has GetTagsForSecurity method that uses its internal tagRepo
	if tags, err := s.securityRepo.GetTagsForSecurity(sec.Symbol); err == nil {
		security.Tags = tags
	}

	// Load current price (optional - might fail or not be needed)
	if s.priceClient != nil {
		if price, err := s.getCurrentPrice(sec.Symbol); err == nil && price > 0 {
			security.CurrentPrice = &price
		}
	}

	s.log.Debug().
		Str("isin", isin).
		Str("symbol", security.Symbol).
		Bool("has_scores", security.TotalScore != nil).
		Bool("has_position", security.PositionQuantity != nil).
		Msg("Security loaded successfully")

	return security, nil
}

/**
 * GetHistoricalData returns historical OHLC price data for a security.
 *
 * Parameters:
 *   - isin: Security ISIN
 *   - options: Query options (start date, end date, limit)
 *
 * Returns:
 *   - []domain.DailyPrice: Historical price data
 *   - error: Error if query fails
 */
func (s *SecurityService) GetHistoricalData(isin string, options domain.HistoricalDataOptions) ([]domain.DailyPrice, error) {
	if s.historyDB == nil {
		return nil, fmt.Errorf("HistoryDB not available")
	}

	// Normalize ISIN
	isin = normalizeISIN(isin)

	// If date range specified, filter by date
	if options.StartDate != "" || options.EndDate != "" {
		allPrices, err := s.historyDB.GetDailyPrices(isin, 0) // 0 = no limit
		if err != nil {
			return nil, fmt.Errorf("failed to load historical prices: %w", err)
		}

		// Convert universe.DailyPrice to domain.DailyPrice and filter by date
		filtered := filterPricesByDateRange(convertDailyPrices(allPrices), options.StartDate, options.EndDate, options.Limit)
		return filtered, nil
	}

	// Otherwise use limit directly
	prices, err := s.historyDB.GetDailyPrices(isin, options.Limit)
	if err != nil {
		return nil, fmt.Errorf("failed to load historical prices: %w", err)
	}

	return convertDailyPrices(prices), nil
}

/**
 * getCurrentPrice fetches current price from price client
 */
func (s *SecurityService) getCurrentPrice(symbol string) (float64, error) {
	if s.priceClient == nil {
		return 0, fmt.Errorf("price client not available")
	}

	symbolMap := map[string]*string{
		symbol: &symbol,
	}

	prices, err := s.priceClient.GetBatchQuotes(symbolMap)
	if err != nil {
		return 0, err
	}

	if price, ok := prices[symbol]; ok && price != nil {
		return *price, nil
	}

	return 0, fmt.Errorf("price not found for symbol: %s", symbol)
}

/**
 * normalizeISIN normalizes an ISIN to uppercase and trims whitespace
 */
func normalizeISIN(isin string) string {
	return strings.ToUpper(strings.TrimSpace(isin))
}

/**
 * convertDailyPrices converts universe.DailyPrice to domain.DailyPrice
 */
func convertDailyPrices(prices []universe.DailyPrice) []domain.DailyPrice {
	result := make([]domain.DailyPrice, len(prices))
	for i, p := range prices {
		result[i] = domain.DailyPrice{
			Date:          p.Date,
			Open:          p.Open,
			High:          p.High,
			Low:           p.Low,
			Close:         p.Close,
			AdjustedClose: p.AdjustedClose,
			Volume:        p.Volume,
		}
	}
	return result
}

/**
 * filterPricesByDateRange filters prices by date range and limit
 */
func filterPricesByDateRange(prices []domain.DailyPrice, startDate, endDate string, limit int) []domain.DailyPrice {
	var filtered []domain.DailyPrice

	for _, p := range prices {
		// Filter by start date
		if startDate != "" && p.Date < startDate {
			continue
		}
		// Filter by end date
		if endDate != "" && p.Date > endDate {
			continue
		}
		filtered = append(filtered, p)
	}

	// Apply limit
	if limit > 0 && len(filtered) > limit {
		filtered = filtered[:limit]
	}

	return filtered
}
