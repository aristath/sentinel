package scheduler

import (
	"fmt"
	"time"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/clients/yahoo"
	"github.com/aristath/arduino-trader/internal/modules/dividends"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/scoring"
	"github.com/aristath/arduino-trader/internal/modules/trading"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/aristath/arduino-trader/internal/services"
	"github.com/rs/zerolog"
)

// DividendReinvestmentJob automatically reinvests dividends using yield-based strategy.
//
// Process:
//  1. Get all unreinvested dividends
//  2. Group dividends by symbol and sum amounts
//  3. For each symbol with total >= min_trade_size:
//     - Check dividend yield
//     - If yield >= 3%: reinvest in same security
//     - If yield < 3%: set as pending bonus for next rebalancing
//  4. For small dividends (< min_trade_size): set pending bonus
//
// Based on Python implementation: app/modules/dividends/jobs/dividend_reinvestment.py
// Simplified to focus on core DRIP functionality (high-yield reinvestment)
type DividendReinvestmentJob struct {
	log                   zerolog.Logger
	dividendRepo          *dividends.DividendRepository
	securityRepo          *universe.SecurityRepository
	scoreRepo             *universe.ScoreRepository
	portfolioService      *portfolio.PortfolioService
	tradingService        *trading.TradingService
	tradeExecutionService *services.TradeExecutionService
	tradernetClient       *tradernet.Client
	yahooClient           *yahoo.Client
	transactionCostFixed  float64 // Freedom24 fixed cost (€2.00)
	transactionCostPct    float64 // Freedom24 variable cost (0.2%)
	maxCostRatio          float64 // Maximum acceptable cost ratio (1%)
}

// DividendReinvestmentConfig holds configuration for dividend reinvestment job
type DividendReinvestmentConfig struct {
	Log                   zerolog.Logger
	DividendRepo          *dividends.DividendRepository
	SecurityRepo          *universe.SecurityRepository
	ScoreRepo             *universe.ScoreRepository
	PortfolioService      *portfolio.PortfolioService
	TradingService        *trading.TradingService
	TradeExecutionService *services.TradeExecutionService
	TradernetClient       *tradernet.Client
	YahooClient           *yahoo.Client
}

// NewDividendReinvestmentJob creates a new dividend reinvestment job
func NewDividendReinvestmentJob(cfg DividendReinvestmentConfig) *DividendReinvestmentJob {
	return &DividendReinvestmentJob{
		log:                   cfg.Log.With().Str("job", "dividend_reinvestment").Logger(),
		dividendRepo:          cfg.DividendRepo,
		securityRepo:          cfg.SecurityRepo,
		scoreRepo:             cfg.ScoreRepo,
		portfolioService:      cfg.PortfolioService,
		tradingService:        cfg.TradingService,
		tradeExecutionService: cfg.TradeExecutionService,
		tradernetClient:       cfg.TradernetClient,
		yahooClient:           cfg.YahooClient,
		// Standard Freedom24 transaction costs for dividend reinvestment
		transactionCostFixed: 2.0,
		transactionCostPct:   0.002, // 0.2%
		maxCostRatio:         0.01,  // 1% max cost-to-trade ratio
	}
}

// Name returns the job name
func (j *DividendReinvestmentJob) Name() string {
	return "dividend_reinvestment"
}

// Run executes the dividend reinvestment job
// Note: Concurrent execution is prevented by the scheduler's SkipIfStillRunning wrapper
func (j *DividendReinvestmentJob) Run() error {
	j.log.Info().Msg("Starting automatic dividend reinvestment")
	startTime := time.Now()

	// Calculate minimum trade size using Freedom24 costs
	minTradeSize := j.calculateMinTradeAmount()
	j.log.Debug().Float64("min_trade_size", minTradeSize).Msg("Calculated minimum trade size")

	// Step 1: Get all unreinvested dividends
	dividends, err := j.dividendRepo.GetUnreinvestedDividends(0.0)
	if err != nil {
		j.log.Error().Err(err).Msg("Failed to get unreinvested dividends")
		return fmt.Errorf("failed to get unreinvested dividends: %w", err)
	}

	if len(dividends) == 0 {
		j.log.Info().Msg("No unreinvested dividends found")
		return nil
	}

	j.log.Info().Int("count", len(dividends)).Msg("Found unreinvested dividends")

	// Step 2: Group dividends by symbol and sum amounts
	groupedDividends := j.groupDividendsBySymbol(dividends)
	j.log.Info().Int("symbols", len(groupedDividends)).Msg("Grouped dividends by symbol")

	// Note: Tradernet client connection is managed by the service
	// We'll use Yahoo Finance for price quotes

	// Step 4: Process each symbol - check yield and categorize
	highYieldReinvestments := make(map[string]SymbolDividendInfo)
	lowYieldDividends := make(map[string]SymbolDividendInfo)

	for symbol, info := range groupedDividends {
		// Check if total meets minimum trade size
		if info.TotalAmount < minTradeSize {
			j.log.Info().
				Str("symbol", symbol).
				Float64("total", info.TotalAmount).
				Float64("min_trade_size", minTradeSize).
				Msg("Total below min trade size, setting pending bonus")

			j.setPendingBonuses(info.Dividends)
			continue
		}

		// Get dividend yield for this security from Yahoo Finance
		// If not available, treat as low-yield (safer)
		dividendYield := j.getDividendYield(symbol)
		if dividendYield < 0 {
			j.log.Debug().
				Str("symbol", symbol).
				Msg("No dividend yield data, treating as low-yield")
			lowYieldDividends[symbol] = info
			continue
		}

		// Check if yield is high enough for same-security reinvestment
		if dividendYield >= scoring.HighDividendReinvestmentThreshold {
			// High-yield security (>=3%): reinvest in same security
			j.log.Info().
				Str("symbol", symbol).
				Float64("yield", dividendYield*100).
				Float64("total", info.TotalAmount).
				Msg("High yield, reinvesting in same security")
			highYieldReinvestments[symbol] = info
		} else {
			// Low-yield security (<3%): aggregate for best opportunities
			j.log.Info().
				Str("symbol", symbol).
				Float64("yield", dividendYield*100).
				Float64("total", info.TotalAmount).
				Msg("Low yield, aggregating for best opportunities")
			lowYieldDividends[symbol] = info
		}
	}

	// Step 5: Process high-yield reinvestments (buy same security)
	var recommendations []domain.HolisticStep
	dividendsToMark := make(map[string][]int) // symbol -> list of dividend IDs

	for symbol, info := range highYieldReinvestments {
		step, err := j.createSameSecurityReinvestment(symbol, info, minTradeSize)
		if err != nil {
			j.log.Error().
				Err(err).
				Str("symbol", symbol).
				Msg("Failed to create same-security reinvestment")
			continue
		}

		if step != nil {
			recommendations = append(recommendations, *step)
			dividendsToMark[symbol] = info.DividendIDs
		}
	}

	// Step 6: Process low-yield dividends
	// For now, set as pending bonuses - these will be used in next regular rebalancing
	// TODO: Integrate with opportunities service to find best opportunities for low-yield dividends
	if len(lowYieldDividends) > 0 {
		totalLowYield := 0.0
		for _, info := range lowYieldDividends {
			totalLowYield += info.TotalAmount
			j.setPendingBonuses(info.Dividends)
		}

		j.log.Info().
			Int("symbols", len(lowYieldDividends)).
			Float64("total", totalLowYield).
			Msg("Low-yield dividends set as pending bonuses for next rebalancing")
	}

	// Step 7: Execute trades if any
	if len(recommendations) > 0 {
		j.log.Info().
			Int("trades", len(recommendations)).
			Msg("Executing dividend reinvestment trades")

		executedCount := j.executeTrades(recommendations, dividendsToMark)

		j.log.Info().
			Int("executed", executedCount).
			Int("total", len(recommendations)).
			Dur("duration", time.Since(startTime)).
			Msg("Dividend reinvestment job completed")
	} else {
		j.log.Info().
			Dur("duration", time.Since(startTime)).
			Msg("No dividend reinvestment trades to execute")
	}

	return nil
}

// SymbolDividendInfo holds aggregated dividend information for a symbol
type SymbolDividendInfo struct {
	Dividends     []dividends.DividendRecord
	DividendIDs   []int
	TotalAmount   float64
	DividendCount int
}

// groupDividendsBySymbol groups dividends by symbol and sums amounts
func (j *DividendReinvestmentJob) groupDividendsBySymbol(
	divs []dividends.DividendRecord,
) map[string]SymbolDividendInfo {
	grouped := make(map[string]SymbolDividendInfo)

	for _, dividend := range divs {
		info, exists := grouped[dividend.Symbol]
		if !exists {
			info = SymbolDividendInfo{
				Dividends:   []dividends.DividendRecord{},
				DividendIDs: []int{},
			}
		}

		info.Dividends = append(info.Dividends, dividend)
		info.DividendIDs = append(info.DividendIDs, dividend.ID)
		info.TotalAmount += dividend.AmountEUR
		info.DividendCount++

		grouped[dividend.Symbol] = info
	}

	return grouped
}

// calculateMinTradeAmount calculates minimum trade amount where transaction costs are acceptable
// Based on Freedom24's €2 + 0.2% fee structure
func (j *DividendReinvestmentJob) calculateMinTradeAmount() float64 {
	// Solve for trade amount where: (fixed + trade * percent) / trade = max_ratio
	// fixed / trade + percent = max_ratio
	// trade = fixed / (max_ratio - percent)
	denominator := j.maxCostRatio - j.transactionCostPct
	if denominator <= 0 {
		// If variable cost exceeds max ratio, return a high minimum
		return 1000.0
	}
	return j.transactionCostFixed / denominator
}

// createSameSecurityReinvestment creates a BUY step for reinvesting in the same security
func (j *DividendReinvestmentJob) createSameSecurityReinvestment(
	symbol string,
	info SymbolDividendInfo,
	minTradeSize float64,
) (*domain.HolisticStep, error) {
	// Get security info for name and other details
	security, err := j.securityRepo.GetBySymbol(symbol)
	if err != nil || security == nil {
		j.log.Warn().
			Str("symbol", symbol).
			Msg("Security not found in universe, skipping")
		return nil, fmt.Errorf("security %s not found", symbol)
	}

	// Get current security price from Yahoo Finance
	yahooSymbol := security.YahooSymbol
	if yahooSymbol == "" {
		yahooSymbol = symbol
	}

	pricePtr, err := j.yahooClient.GetCurrentPrice(yahooSymbol, nil, 3)
	if err != nil || pricePtr == nil || *pricePtr <= 0 {
		j.log.Warn().
			Str("symbol", symbol).
			Str("yahoo_symbol", yahooSymbol).
			Msg("Could not get current price, skipping")
		return nil, fmt.Errorf("invalid price for %s", symbol)
	}

	price := *pricePtr

	// Calculate shares to buy
	quantity := int(info.TotalAmount / price)
	if quantity <= 0 {
		j.log.Warn().
			Str("symbol", symbol).
			Int("quantity", quantity).
			Msg("Calculated quantity is invalid, skipping")
		return nil, fmt.Errorf("invalid quantity for %s", symbol)
	}

	// Adjust for min_lot
	if security.MinLot > 1 {
		quantity = (quantity / security.MinLot) * security.MinLot
		if quantity == 0 {
			quantity = security.MinLot
		}
	}

	estimatedValue := float64(quantity) * price

	// Create BUY step
	step := &domain.HolisticStep{
		Symbol:         symbol,
		Name:           security.Name,
		Side:           "BUY",
		Quantity:       quantity,
		EstimatedPrice: price,
		EstimatedValue: estimatedValue,
		Currency:       security.Currency,
		Reason: fmt.Sprintf("Dividend reinvestment (high yield): %.2f EUR from %d dividend(s)",
			info.TotalAmount, info.DividendCount),
		Narrative: fmt.Sprintf("Reinvest %.2f EUR dividend in %s (high yield security)",
			info.TotalAmount, symbol),
	}

	return step, nil
}

// executeTrades executes dividend reinvestment trades and marks dividends as reinvested
func (j *DividendReinvestmentJob) executeTrades(
	recommendations []domain.HolisticStep,
	dividendsToMark map[string][]int,
) int {
	executedCount := 0

	// Convert domain.HolisticStep to services.TradeRecommendation
	tradeRecs := make([]services.TradeRecommendation, 0, len(recommendations))
	for _, rec := range recommendations {
		tradeRecs = append(tradeRecs, services.TradeRecommendation{
			Symbol:         rec.Symbol,
			Side:           rec.Side,
			Quantity:       float64(rec.Quantity),
			EstimatedPrice: rec.EstimatedPrice,
			Currency:       rec.Currency,
			Reason:         rec.Reason,
		})
	}

	// Execute all trades via trade execution service
	if j.tradeExecutionService != nil {
		results := j.tradeExecutionService.ExecuteTrades(tradeRecs)

		// Process results and mark dividends as reinvested
		for i, result := range results {
			rec := recommendations[i]

			if result.Status == "success" {
				j.log.Info().
					Str("symbol", rec.Symbol).
					Str("side", rec.Side).
					Int("quantity", rec.Quantity).
					Float64("estimated_value", rec.EstimatedValue).
					Msg("Successfully executed dividend reinvestment trade")

				// Mark dividends as reinvested
				if dividendIDs, ok := dividendsToMark[rec.Symbol]; ok {
					for _, dividendID := range dividendIDs {
						if err := j.dividendRepo.MarkReinvested(dividendID, rec.Quantity); err != nil {
							j.log.Error().
								Err(err).
								Int("dividend_id", dividendID).
								Str("symbol", rec.Symbol).
								Msg("Failed to mark dividend as reinvested")
						}
					}

					j.log.Info().
						Str("symbol", rec.Symbol).
						Int("dividends_marked", len(dividendIDs)).
						Msg("Marked dividends as reinvested")

					executedCount++
				}
			} else {
				j.log.Warn().
					Str("symbol", rec.Symbol).
					Str("status", result.Status).
					Str("error", func() string {
						if result.Error != nil {
							return *result.Error
						}
						return ""
					}()).
					Msg("Failed to execute dividend reinvestment trade")
			}
		}
	} else {
		j.log.Warn().Msg("Trade execution service not available, skipping trade execution")
	}

	return executedCount
}

// setPendingBonuses sets pending bonus for dividends that are too small to reinvest
func (j *DividendReinvestmentJob) setPendingBonuses(divs []dividends.DividendRecord) {
	for _, dividend := range divs {
		if err := j.dividendRepo.SetPendingBonus(dividend.ID, dividend.AmountEUR); err != nil {
			j.log.Error().
				Err(err).
				Int("dividend_id", dividend.ID).
				Str("symbol", dividend.Symbol).
				Float64("amount", dividend.AmountEUR).
				Msg("Failed to set pending bonus")
		}
	}
}

// getDividendYield gets the dividend yield for a symbol
// Returns -1.0 if not available
func (j *DividendReinvestmentJob) getDividendYield(symbol string) float64 {
	// Try to get from Yahoo Finance
	// First, get the security to find the Yahoo symbol
	security, err := j.securityRepo.GetBySymbol(symbol)
	if err != nil || security == nil {
		j.log.Debug().
			Str("symbol", symbol).
			Msg("Security not found, cannot get dividend yield")
		return -1.0
	}

	// Get fundamentals from Yahoo Finance
	yahooSymbol := security.YahooSymbol
	if yahooSymbol == "" {
		yahooSymbol = symbol
	}

	fundamentals, err := j.yahooClient.GetFundamentalData(yahooSymbol, nil)
	if err != nil || fundamentals == nil {
		j.log.Debug().
			Str("symbol", symbol).
			Str("yahoo_symbol", yahooSymbol).
			Msg("Failed to get fundamentals from Yahoo")
		return -1.0
	}

	// DividendYield in Yahoo is already a fraction (e.g., 0.03 for 3%)
	if fundamentals.DividendYield != nil && *fundamentals.DividendYield > 0 {
		return *fundamentals.DividendYield
	}

	return -1.0
}
