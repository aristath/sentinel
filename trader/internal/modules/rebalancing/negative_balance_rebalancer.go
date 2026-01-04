package rebalancing

import (
	"fmt"
	"sort"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/modules/planning"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/settings"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/aristath/arduino-trader/internal/scheduler"
	"github.com/aristath/arduino-trader/internal/services"
	"github.com/rs/zerolog"
)

// MinCurrencyReserve is the minimum cash reserve per currency (€5)
const MinCurrencyReserve = 5.0

// NegativeBalanceRebalancer automatically fixes negative cash balances
// Faithful translation from Python: app/modules/rebalancing/services/negative_balance_rebalancer.py
//
// Executes 3-step rebalancing process:
// 1. Currency exchange from other currencies
// 2. Position sales (if exchange insufficient)
// 3. Final currency exchange to ensure all currencies have minimum
type NegativeBalanceRebalancer struct {
	log                     zerolog.Logger
	tradernetClient         *tradernet.Client
	securityRepo            *universe.SecurityRepository
	positionRepo            *portfolio.PositionRepository
	settingsRepo            *settings.Repository
	currencyExchangeService *services.CurrencyExchangeService
	tradeExecutionService   *services.TradeExecutionService
	recommendationRepo      *planning.RecommendationRepository
	marketHoursService      *scheduler.MarketHoursService
}

// NewNegativeBalanceRebalancer creates a new negative balance rebalancer
func NewNegativeBalanceRebalancer(
	log zerolog.Logger,
	tradernetClient *tradernet.Client,
	securityRepo *universe.SecurityRepository,
	positionRepo *portfolio.PositionRepository,
	settingsRepo *settings.Repository,
	currencyExchangeService *services.CurrencyExchangeService,
	tradeExecutionService *services.TradeExecutionService,
	recommendationRepo *planning.RecommendationRepository,
	marketHoursService *scheduler.MarketHoursService,
) *NegativeBalanceRebalancer {
	return &NegativeBalanceRebalancer{
		log:                     log.With().Str("service", "negative_balance_rebalancer").Logger(),
		tradernetClient:         tradernetClient,
		securityRepo:            securityRepo,
		positionRepo:            positionRepo,
		settingsRepo:            settingsRepo,
		currencyExchangeService: currencyExchangeService,
		tradeExecutionService:   tradeExecutionService,
		recommendationRepo:      recommendationRepo,
		marketHoursService:      marketHoursService,
	}
}

// GetTradingCurrencies gets currencies from active securities in the universe
func (r *NegativeBalanceRebalancer) GetTradingCurrencies() (map[string]bool, error) {
	securities, err := r.securityRepo.GetAllActive()
	if err != nil {
		return nil, fmt.Errorf("failed to get active securities: %w", err)
	}

	currencies := make(map[string]bool)
	for _, security := range securities {
		if security.Currency != "" {
			currencies[security.Currency] = true
		}
	}

	r.log.Debug().
		Int("security_count", len(securities)).
		Int("currency_count", len(currencies)).
		Msg("Retrieved trading currencies")

	return currencies, nil
}

// CheckCurrencyMinimums checks which currencies are below minimum reserve
//
// Returns: Map of currency -> shortfall amount (only currencies below minimum)
func (r *NegativeBalanceRebalancer) CheckCurrencyMinimums(cashBalances map[string]float64) (map[string]float64, error) {
	tradingCurrencies, err := r.GetTradingCurrencies()
	if err != nil {
		return nil, fmt.Errorf("failed to get trading currencies: %w", err)
	}

	shortfalls := make(map[string]float64)

	// Check all currencies that are either:
	// 1. Trading currencies (from active securities), OR
	// 2. Have negative balances (must fix regardless)
	currenciesToCheck := make(map[string]bool)
	for curr := range tradingCurrencies {
		currenciesToCheck[curr] = true
	}
	for currency, balance := range cashBalances {
		if balance < 0 {
			// Always fix negative balances, even if not a trading currency
			currenciesToCheck[currency] = true
		}
	}

	for currency := range currenciesToCheck {
		balance := cashBalances[currency]
		if balance < MinCurrencyReserve {
			shortfall := MinCurrencyReserve - balance
			shortfalls[currency] = shortfall
			r.log.Warn().
				Str("currency", currency).
				Float64("balance", balance).
				Float64("minimum", MinCurrencyReserve).
				Float64("shortfall", shortfall).
				Msg("Currency below minimum reserve")
		}
	}

	return shortfalls, nil
}

// HasNegativeBalances checks if any currency has a negative balance
func (r *NegativeBalanceRebalancer) HasNegativeBalances() (bool, error) {
	if !r.tradernetClient.IsConnected() {
		r.log.Warn().Msg("Tradernet not connected, cannot check balances")
		return false, fmt.Errorf("tradernet not connected")
	}

	balances, err := r.tradernetClient.GetCashBalances()
	if err != nil {
		return false, fmt.Errorf("failed to get cash balances: %w", err)
	}

	for _, balance := range balances {
		if balance.Amount < 0 {
			r.log.Warn().
				Str("currency", balance.Currency).
				Float64("amount", balance.Amount).
				Msg("Negative balance detected")
			return true, nil
		}
	}

	return false, nil
}

// HasCurrenciesBelowMinimum checks if any trading currency is below minimum reserve
func (r *NegativeBalanceRebalancer) HasCurrenciesBelowMinimum() (bool, error) {
	if !r.tradernetClient.IsConnected() {
		r.log.Warn().Msg("Tradernet not connected, cannot check balances")
		return false, fmt.Errorf("tradernet not connected")
	}

	balances, err := r.tradernetClient.GetCashBalances()
	if err != nil {
		return false, fmt.Errorf("failed to get cash balances: %w", err)
	}

	cashBalances := make(map[string]float64)
	for _, balance := range balances {
		cashBalances[balance.Currency] = balance.Amount
	}

	shortfalls, err := r.CheckCurrencyMinimums(cashBalances)
	if err != nil {
		return false, err
	}

	return len(shortfalls) > 0, nil
}

// RebalanceNegativeBalances executes the 3-step rebalancing process
//
// Step 1: Currency exchange from other currencies
// Step 2: Position sales (if exchange insufficient)
// Step 3: Final currency exchange to ensure all currencies have minimum
//
// Returns true if rebalancing completed, false otherwise
func (r *NegativeBalanceRebalancer) RebalanceNegativeBalances() (bool, error) {
	if !r.tradernetClient.IsConnected() {
		r.log.Error().Msg("Cannot connect to Tradernet for rebalancing")
		return false, fmt.Errorf("tradernet not connected")
	}

	// Get current cash balances
	balancesRaw, err := r.tradernetClient.GetCashBalances()
	if err != nil {
		return false, fmt.Errorf("failed to get cash balances: %w", err)
	}

	cashBalances := make(map[string]float64)
	for _, balance := range balancesRaw {
		cashBalances[balance.Currency] = balance.Amount
	}

	// Check for currencies below minimum
	shortfalls, err := r.CheckCurrencyMinimums(cashBalances)
	if err != nil {
		return false, fmt.Errorf("failed to check currency minimums: %w", err)
	}

	if len(shortfalls) == 0 {
		r.log.Info().Msg("All currencies meet minimum reserve requirements")

		// Clean up any existing emergency recommendations
		emergencyPortfolioHash := "EMERGENCY:negative_balance_rebalancing"
		dismissedCount, err := r.recommendationRepo.DismissAllByPortfolioHash(emergencyPortfolioHash)
		if err != nil {
			r.log.Warn().Err(err).Msg("Failed to dismiss emergency recommendations")
		} else if dismissedCount > 0 {
			r.log.Info().
				Int("dismissed_count", dismissedCount).
				Msg("Dismissed emergency recommendations after successful rebalancing")
		}

		return true, nil
	}

	r.log.Warn().
		Int("currency_count", len(shortfalls)).
		Msg("Starting negative balance rebalancing")

	// Get trading mode
	tradingModePtr, err := r.settingsRepo.Get("trading_mode")
	if err != nil {
		r.log.Warn().Err(err).Msg("Failed to get trading mode, defaulting to research")
	}
	tradingMode := "research"
	if tradingModePtr != nil {
		tradingMode = *tradingModePtr
	}

	// Step 1: Try currency exchange
	remainingShortfalls, err := r.step1CurrencyExchange(shortfalls, cashBalances, tradingMode)
	if err != nil {
		return false, fmt.Errorf("failed in currency exchange step: %w", err)
	}

	if len(remainingShortfalls) == 0 {
		r.log.Info().Msg("Currency exchange resolved all shortfalls")

		// Clean up emergency recommendations
		emergencyPortfolioHash := "EMERGENCY:negative_balance_rebalancing"
		dismissedCount, err := r.recommendationRepo.DismissAllByPortfolioHash(emergencyPortfolioHash)
		if err != nil {
			r.log.Warn().Err(err).Msg("Failed to dismiss emergency recommendations")
		} else if dismissedCount > 0 {
			r.log.Info().
				Int("dismissed_count", dismissedCount).
				Msg("Dismissed emergency recommendations after currency exchange")
		}

		return true, nil
	}

	// Step 2: Position sales if exchange insufficient
	if err := r.step2PositionSales(remainingShortfalls, tradingMode); err != nil {
		return false, fmt.Errorf("failed in position sales step: %w", err)
	}

	// Step 3: Final currency exchange
	if err := r.step3FinalExchange(tradingMode); err != nil {
		return false, fmt.Errorf("failed in final exchange step: %w", err)
	}

	r.log.Info().Msg("Negative balance rebalancing completed")
	return true, nil
}

// step1CurrencyExchange tries to resolve shortfalls via currency exchange
func (r *NegativeBalanceRebalancer) step1CurrencyExchange(
	shortfalls map[string]float64,
	cashBalances map[string]float64,
	tradingMode string,
) (map[string]float64, error) {
	// Research mode: skip execution
	if tradingMode == "research" {
		r.log.Info().Msg("Research mode: Currency exchanges recommended but NOT executed")
		return shortfalls, nil
	}

	remainingShortfalls := make(map[string]float64)
	for k, v := range shortfalls {
		remainingShortfalls[k] = v
	}

	maxIterations := 20
	iteration := 0

	// Keep trying until all shortfalls resolved or no more cash available
	for len(remainingShortfalls) > 0 && iteration < maxIterations {
		iteration++
		progressMade := false

		// Refresh balances at start of each iteration
		balancesRaw, err := r.tradernetClient.GetCashBalances()
		if err != nil {
			return remainingShortfalls, fmt.Errorf("failed to refresh balances: %w", err)
		}

		cashBalances = make(map[string]float64)
		for _, balance := range balancesRaw {
			cashBalances[balance.Currency] = balance.Amount
		}

		// Check if there's any cash available to exchange
		totalAvailableCash := 0.0
		for _, balance := range cashBalances {
			if balance > MinCurrencyReserve {
				totalAvailableCash += balance - MinCurrencyReserve
			}
		}

		if totalAvailableCash <= 0 {
			r.log.Info().
				Int("remaining_shortfalls", len(remainingShortfalls)).
				Msg("No more cash available for currency exchange")
			break
		}

		// Try to cover each remaining shortfall
		for currency, needed := range remainingShortfalls {
			// Find currencies with excess (balance > minimum)
			type ExcessCurrency struct {
				Currency string
				Balance  float64
			}
			var excessCurrencies []ExcessCurrency

			for otherCurrency, balance := range cashBalances {
				if otherCurrency == currency {
					continue
				}
				if balance > MinCurrencyReserve {
					excessCurrencies = append(excessCurrencies, ExcessCurrency{
						Currency: otherCurrency,
						Balance:  balance,
					})
				}
			}

			// Try to exchange from currencies with excess
			for _, excess := range excessCurrencies {
				if _, exists := remainingShortfalls[currency]; !exists {
					break // Already covered
				}

				needed = remainingShortfalls[currency]
				available := excess.Balance - MinCurrencyReserve

				// Simple conversion (CurrencyExchangeService handles rate lookups internally)
				// For now assume we can exchange enough from available balance
				sourceAmountNeeded := needed * 1.02 // 2% buffer for safety

				if available < sourceAmountNeeded {
					continue // Not enough in this currency
				}

				r.log.Info().
					Str("from", excess.Currency).
					Str("to", currency).
					Float64("amount", sourceAmountNeeded).
					Msg("Exchanging currency to cover shortfall")

				// Execute exchange
				err := r.currencyExchangeService.Exchange(excess.Currency, currency, sourceAmountNeeded)
				if err != nil {
					r.log.Warn().
						Err(err).
						Str("from", excess.Currency).
						Str("to", currency).
						Msg("Currency exchange failed")
					continue
				}

				r.log.Info().
					Str("from", excess.Currency).
					Str("to", currency).
					Msg("Currency exchange successful")
				progressMade = true

				// Refresh balances after successful exchange
				balancesRaw, err = r.tradernetClient.GetCashBalances()
				if err != nil {
					return remainingShortfalls, fmt.Errorf("failed to refresh balances: %w", err)
				}

				cashBalances = make(map[string]float64)
				for _, balance := range balancesRaw {
					cashBalances[balance.Currency] = balance.Amount
				}

				// Check if shortfall is resolved
				if cashBalances[currency] >= MinCurrencyReserve {
					delete(remainingShortfalls, currency)
					r.log.Info().
						Str("currency", currency).
						Msg("Shortfall resolved via currency exchange")
				}
			}
		}

		// If no progress was made in this iteration, break to avoid infinite loop
		if !progressMade {
			r.log.Info().
				Int("remaining_shortfalls", len(remainingShortfalls)).
				Msg("No progress made in currency exchange iteration")
			break
		}
	}

	if iteration >= maxIterations {
		r.log.Warn().
			Int("max_iterations", maxIterations).
			Int("remaining_shortfalls", len(remainingShortfalls)).
			Msg("Reached maximum iterations in currency exchange")
	}

	return remainingShortfalls, nil
}

// step2PositionSales sells positions to cover remaining shortfalls
func (r *NegativeBalanceRebalancer) step2PositionSales(
	remainingShortfalls map[string]float64,
	tradingMode string,
) error {
	if len(remainingShortfalls) == 0 {
		return nil
	}

	// Get positions with security info
	positions, err := r.positionRepo.GetWithSecurityInfo()
	if err != nil {
		return fmt.Errorf("failed to get positions: %w", err)
	}

	// Filter to sellable positions (allow_sell=true AND market is open for strict exchanges)
	var sellablePositions []portfolio.PositionWithSecurity
	for _, pos := range positions {
		if !pos.AllowSell {
			continue
		}

		// Check market hours for SELL orders
		// ShouldCheckMarketHours returns true for all SELL orders
		if r.marketHoursService != nil && r.marketHoursService.ShouldCheckMarketHours(pos.FullExchangeName, "SELL") {
			if !r.marketHoursService.IsMarketOpen(pos.FullExchangeName) {
				r.log.Debug().
					Str("symbol", pos.Symbol).
					Str("exchange", pos.FullExchangeName).
					Msg("Skipping position - market closed")
				continue
			}
		}

		sellablePositions = append(sellablePositions, pos)
	}

	if len(sellablePositions) == 0 {
		r.log.Warn().Msg("No sellable positions available")
		return nil
	}

	// Calculate total cash needed in EUR (convert all shortfalls to EUR using precise rates)
	totalNeededEUR := 0.0
	for currency, shortfall := range remainingShortfalls {
		if currency == "EUR" {
			totalNeededEUR += shortfall
			continue
		}

		// Get precise exchange rate
		rate, err := r.currencyExchangeService.GetRate(currency, "EUR")
		if err != nil {
			r.log.Warn().
				Err(err).
				Str("from", currency).
				Str("to", "EUR").
				Msg("Failed to get exchange rate, using fallback")

			// Fallback to rough conversion if rate lookup fails
			eurValue := shortfall
			switch currency {
			case "USD":
				eurValue = shortfall * 0.9 // Rough fallback
			case "GBP":
				eurValue = shortfall * 1.2 // Rough fallback
			case "HKD":
				eurValue = shortfall * 0.11 // Rough fallback
			default:
				eurValue = shortfall
			}
			totalNeededEUR += eurValue
		} else {
			totalNeededEUR += shortfall * rate
		}
	}

	// Sort positions by market_value_eur descending (largest first)
	sort.Slice(sellablePositions, func(i, j int) bool {
		return sellablePositions[i].MarketValueEUR > sellablePositions[j].MarketValueEUR
	})

	// Select positions to sell
	var sellRecommendations []services.TradeRecommendation
	totalSellValue := 0.0

	for _, pos := range sellablePositions {
		if totalSellValue >= totalNeededEUR*1.1 { // 10% buffer
			break
		}

		// Sell partial or full position
		positionValue := pos.MarketValueEUR
		sellValueEUR := positionValue
		if totalSellValue+positionValue > totalNeededEUR*1.1 {
			sellValueEUR = (totalNeededEUR * 1.1) - totalSellValue
		}

		sellQuantity := pos.Quantity
		if sellValueEUR < positionValue && pos.CurrentPrice > 0 {
			// Partial sell
			sellQuantity = sellValueEUR / (pos.CurrentPrice / pos.CurrencyRate)
		}

		if sellQuantity > 0 {
			rec := services.TradeRecommendation{
				Symbol:         pos.Symbol,
				Side:           "SELL",
				Quantity:       sellQuantity,
				EstimatedPrice: pos.CurrentPrice,
				Currency:       pos.Currency,
				Reason:         "Emergency rebalancing: negative cash balance",
			}
			sellRecommendations = append(sellRecommendations, rec)
			totalSellValue += sellValueEUR
		}
	}

	if len(sellRecommendations) == 0 {
		r.log.Warn().Msg("No sell recommendations generated")
		return nil
	}

	// Store emergency recommendations in database for UI visibility
	emergencyPortfolioHash := "EMERGENCY:negative_balance_rebalancing"
	for _, rec := range sellRecommendations {
		planningRec := planning.Recommendation{
			Symbol:         rec.Symbol,
			Name:           rec.Symbol, // Use symbol as name for now
			Side:           rec.Side,
			Quantity:       rec.Quantity,
			EstimatedPrice: rec.EstimatedPrice,
			Currency:       rec.Currency,
			Reason:         rec.Reason,
			Priority:       999.0, // High priority for emergency
			PortfolioHash:  emergencyPortfolioHash,
			Status:         "pending",
		}

		_, err := r.recommendationRepo.CreateOrUpdate(planningRec)
		if err != nil {
			r.log.Warn().Err(err).Msg("Failed to store emergency recommendation")
		}
	}

	r.log.Info().
		Int("recommendation_count", len(sellRecommendations)).
		Float64("total_value_eur", totalSellValue).
		Msg("Emergency sell recommendations created")

	// Research mode: create recommendations but don't execute
	if tradingMode == "research" {
		r.log.Info().Msg("Research mode: Emergency sales recommended but NOT executed (shown in UI only)")
		return nil
	}

	// Live mode: execute trades
	r.log.Info().
		Int("trade_count", len(sellRecommendations)).
		Msg("Executing emergency trades in live mode")

	results := r.tradeExecutionService.ExecuteTrades(sellRecommendations)

	// Mark successfully executed recommendations
	for i, result := range results {
		if result.Status == "success" && i < len(sellRecommendations) {
			rec := sellRecommendations[i]

			// Find matching recommendation and mark as executed
			matchingRecs, err := r.recommendationRepo.FindMatchingForExecution(
				rec.Symbol,
				rec.Side,
				emergencyPortfolioHash,
			)
			if err != nil {
				r.log.Warn().Err(err).Msg("Failed to find matching recommendation")
				continue
			}

			for _, matchingRec := range matchingRecs {
				if err := r.recommendationRepo.MarkExecuted(matchingRec.UUID); err != nil {
					r.log.Warn().Err(err).Msg("Failed to mark recommendation as executed")
				} else {
					r.log.Info().
						Str("uuid", matchingRec.UUID).
						Str("symbol", rec.Symbol).
						Msg("Marked emergency recommendation as executed")
				}
			}
		}
	}

	successCount := 0
	for _, result := range results {
		if result.Status == "success" {
			successCount++
		}
	}

	r.log.Info().
		Int("successful", successCount).
		Int("total", len(results)).
		Msg("Emergency sales completed")

	return nil
}

// step3FinalExchange performs final currency exchange after sales
func (r *NegativeBalanceRebalancer) step3FinalExchange(tradingMode string) error {
	// Research mode: skip execution
	if tradingMode == "research" {
		r.log.Info().Msg("Research mode: Final currency exchanges recommended but NOT executed")
		return nil
	}

	// Refresh balances after sales
	balancesRaw, err := r.tradernetClient.GetCashBalances()
	if err != nil {
		return fmt.Errorf("failed to refresh balances: %w", err)
	}

	cashBalances := make(map[string]float64)
	for _, balance := range balancesRaw {
		cashBalances[balance.Currency] = balance.Amount
	}

	// Check for remaining shortfalls
	shortfalls, err := r.CheckCurrencyMinimums(cashBalances)
	if err != nil {
		return fmt.Errorf("failed to check currency minimums: %w", err)
	}

	if len(shortfalls) == 0 {
		r.log.Info().Msg("All currencies now meet minimum reserve after rebalancing")
		return nil
	}

	// Try one more round of currency exchange
	finalShortfalls, err := r.step1CurrencyExchange(shortfalls, cashBalances, tradingMode)
	if err != nil {
		return fmt.Errorf("failed in final currency exchange: %w", err)
	}

	// Final check
	balancesRaw, err = r.tradernetClient.GetCashBalances()
	if err != nil {
		return fmt.Errorf("failed to refresh balances: %w", err)
	}

	cashBalances = make(map[string]float64)
	for _, balance := range balancesRaw {
		cashBalances[balance.Currency] = balance.Amount
	}

	finalShortfalls, err = r.CheckCurrencyMinimums(cashBalances)
	if err != nil {
		return fmt.Errorf("failed to check final currency minimums: %w", err)
	}

	if len(finalShortfalls) > 0 {
		r.log.Error().
			Int("remaining_shortfalls", len(finalShortfalls)).
			Msg("Some currencies still below minimum after rebalancing")
	} else {
		r.log.Info().Msg("Negative balance rebalancing completed successfully")
	}

	return nil
}

// CheckCurrencyMinimumsSafe is a safe wrapper for CheckCurrencyMinimums that handles errors
func (r *NegativeBalanceRebalancer) CheckCurrencyMinimumsSafe() (map[string]float64, error) {
	if !r.tradernetClient.IsConnected() {
		return make(map[string]float64), fmt.Errorf("tradernet not connected")
	}

	balances, err := r.tradernetClient.GetCashBalances()
	if err != nil {
		return make(map[string]float64), fmt.Errorf("failed to get cash balances: %w", err)
	}

	cashBalances := make(map[string]float64)
	for _, balance := range balances {
		cashBalances[balance.Currency] = balance.Amount
	}

	return r.CheckCurrencyMinimums(cashBalances)
}
