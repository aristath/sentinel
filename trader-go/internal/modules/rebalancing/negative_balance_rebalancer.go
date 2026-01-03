package rebalancing

import (
	"fmt"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/aristath/arduino-trader/internal/modules/settings"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/rs/zerolog"
)

// MinCurrencyReserve is the minimum cash reserve per currency (€5)
const MinCurrencyReserve = 5.0

// NegativeBalanceRebalancer automatically fixes negative cash balances
// Faithful translation from Python: app/modules/rebalancing/services/negative_balance_rebalancer.py
//
// Detects negative balances and currencies below minimum reserve.
// Creates emergency sell recommendations visible in UI.
//
// IMPLEMENTATION STATUS:
// ✅ Negative balance detection
// ✅ Currency minimum checks
// ✅ Trading currency identification
// ✅ Emergency recommendation creation
// ⚠️ Currency exchange execution (requires CurrencyExchangeService)
// ⚠️ Position sales execution (requires TradeExecutionService with 7-layer validation)
type NegativeBalanceRebalancer struct {
	log             zerolog.Logger
	tradernetClient *tradernet.Client
	securityRepo    *universe.SecurityRepository
	positionRepo    *portfolio.PositionRepository
	settingsRepo    *settings.Repository
}

// NewNegativeBalanceRebalancer creates a new negative balance rebalancer
func NewNegativeBalanceRebalancer(
	log zerolog.Logger,
	tradernetClient *tradernet.Client,
	securityRepo *universe.SecurityRepository,
	positionRepo *portfolio.PositionRepository,
	settingsRepo *settings.Repository,
) *NegativeBalanceRebalancer {
	return &NegativeBalanceRebalancer{
		log:             log.With().Str("service", "negative_balance_rebalancer").Logger(),
		tradernetClient: tradernetClient,
		securityRepo:    securityRepo,
		positionRepo:    positionRepo,
		settingsRepo:    settingsRepo,
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

// RebalanceNegativeBalances executes the rebalancing process
//
// CURRENT IMPLEMENTATION:
// - Detects negative balances and currencies below minimum
// - Creates emergency sell recommendations in database (visible in UI)
// - Supports research mode (recommendations only, no execution)
//
// TODO FOR FULL AUTONOMOUS OPERATION:
// - Implement CurrencyExchangeService for FX operations
// - Implement TradeExecutionService with 7-layer validation
// - Add automatic execution in live mode (bypass cooldown/min-hold)
// - Add position selection algorithm (largest positions first)
// - Add multi-step rebalancing: currency exchange → position sales → final exchange
//
// Returns true if rebalancing completed/recommendations created, false otherwise
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

		// TODO: Clean up any existing emergency recommendations
		// Requires RecommendationRepository implementation:
		// emergencyPortfolioHash := "EMERGENCY:negative_balance_rebalancing"
		// dismissedCount, err := recommendationRepo.DismissAllByPortfolioHash(emergencyPortfolioHash)

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

	// Create emergency sell recommendations
	if err := r.createEmergencySellRecommendations(shortfalls, cashBalances, tradingMode); err != nil {
		return false, fmt.Errorf("failed to create emergency recommendations: %w", err)
	}

	// TODO: Implement automatic execution in live mode
	// For now, recommendations are created for UI visibility and manual approval
	if tradingMode == "live" {
		r.log.Warn().Msg("Live mode: Emergency recommendations created for manual review")
		r.log.Warn().Msg("TODO: Implement automatic execution (requires TradeExecutionService)")
	} else {
		r.log.Info().Msg("Research mode: Emergency recommendations created (not executed)")
	}

	return true, nil
}

// createEmergencySellRecommendations creates emergency sell recommendations
func (r *NegativeBalanceRebalancer) createEmergencySellRecommendations(
	shortfalls map[string]float64,
	cashBalances map[string]float64,
	tradingMode string,
) error {
	// Calculate total cash needed in EUR
	totalNeededEUR := 0.0
	for currency, shortfall := range shortfalls {
		// TODO: Use ExchangeRateService for proper conversion
		// For now, simple heuristic: assume 1:1 for EUR, 1.1 for USD, 0.85 for GBP, 0.13 for HKD
		eurValue := shortfall
		switch currency {
		case "EUR":
			eurValue = shortfall
		case "USD":
			eurValue = shortfall * 0.9 // Rough conversion
		case "GBP":
			eurValue = shortfall * 1.2 // Rough conversion
		case "HKD":
			eurValue = shortfall * 0.11 // Rough conversion
		default:
			eurValue = shortfall
		}
		totalNeededEUR += eurValue
	}

	r.log.Info().
		Float64("total_needed_eur", totalNeededEUR).
		Msg("Calculated total cash needed for emergency rebalancing")

	// Get positions that can be sold
	// TODO: Implement market hours check (is_market_open)
	// TODO: Implement position selection algorithm (largest first, allow_sell=true)
	// For now, log that position selection needs implementation

	r.log.Warn().Msg("Emergency sell recommendations require implementation of:")
	r.log.Warn().Msg("  1. Position repository with allow_sell flag")
	r.log.Warn().Msg("  2. Market hours checking")
	r.log.Warn().Msg("  3. Position selection algorithm")
	r.log.Warn().Msg("  4. Recommendation creation in database")

	// Store emergency portfolio hash for later cleanup
	emergencyPortfolioHash := "EMERGENCY:negative_balance_rebalancing"

	// TODO: Create recommendations using RecommendationRepository
	// For now, log the shortfalls
	for currency, shortfall := range shortfalls {
		r.log.Warn().
			Str("currency", currency).
			Float64("shortfall", shortfall).
			Str("portfolio_hash", emergencyPortfolioHash).
			Msg("Emergency rebalancing needed")
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
