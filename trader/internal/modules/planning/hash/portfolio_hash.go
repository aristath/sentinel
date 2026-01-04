package hash

import (
	"crypto/md5"
	"fmt"
	"math"
	"sort"
	"strings"

	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/rs/zerolog/log"
)

// Position represents a portfolio position for hashing
type Position struct {
	Symbol   string
	Quantity int
}

// PendingOrder represents a pending order for hashing
type PendingOrder struct {
	Symbol   string
	Side     string // "buy" or "sell"
	Quantity int
	Price    float64
	Currency string
}

// ApplyPendingOrdersToPortfolio applies pending orders to positions and cash balances
// to get hypothetical future state.
//
// For pending BUY orders: reduces cash balance by quantity * price in the order's currency.
// For pending SELL orders: reduces position quantity by the order quantity.
//
// Args:
//   - positions: List of positions with symbol and quantity
//   - cashBalances: Map of currency -> amount (e.g., {"EUR": 1500.0, "USD": 200.0})
//   - pendingOrders: List of pending orders
//   - allowNegativeCash: If true, allows cash to go negative for hypothetical planning.
//     If false (default), clamps cash at 0 for safety.
//
// Returns:
//   - Adjusted positions and cash balances
func ApplyPendingOrdersToPortfolio(
	positions []Position,
	cashBalances map[string]float64,
	pendingOrders []PendingOrder,
	allowNegativeCash bool,
) ([]Position, map[string]float64) {
	// Create a copy of positions as a map for easier manipulation
	positionMap := make(map[string]int)
	for _, p := range positions {
		symbol := strings.ToUpper(p.Symbol)
		if p.Quantity > 0 {
			positionMap[symbol] = p.Quantity
		}
	}

	// Create a copy of cash balances
	adjustedCash := make(map[string]float64)
	for currency, amount := range cashBalances {
		adjustedCash[currency] = amount
	}

	// Process each pending order
	for _, order := range pendingOrders {
		symbol := strings.ToUpper(order.Symbol)
		side := strings.ToLower(order.Side)
		quantity := order.Quantity
		price := order.Price
		currency := order.Currency
		if currency == "" {
			currency = "EUR"
		}

		if symbol == "" || quantity <= 0 || price <= 0 {
			log.Warn().
				Str("symbol", symbol).
				Int("quantity", quantity).
				Float64("price", price).
				Msg("Skipping invalid pending order")
			continue
		}

		if side == "buy" {
			// Reduce cash by the order value
			orderValue := float64(quantity) * price
			currentCash := adjustedCash[currency]
			newCash := currentCash - orderValue

			// Clamp to zero unless negative cash is explicitly allowed
			if allowNegativeCash {
				adjustedCash[currency] = newCash
			} else {
				adjustedCash[currency] = math.Max(0.0, newCash)
			}

			// Increase position quantity (assuming order will execute)
			currentQuantity := positionMap[symbol]
			positionMap[symbol] = currentQuantity + quantity

			log.Debug().
				Str("symbol", symbol).
				Int("quantity", quantity).
				Str("currency", currency).
				Float64("order_value", orderValue).
				Msg("Applied pending BUY")

		} else if side == "sell" {
			// Reduce position quantity
			currentQuantity := positionMap[symbol]
			newQuantity := int(math.Max(0.0, float64(currentQuantity-quantity)))
			if newQuantity > 0 {
				positionMap[symbol] = newQuantity
			} else {
				delete(positionMap, symbol)
			}

			// Note: Cash is not increased here because SELL orders don't generate cash until executed
			// The planner should account for this when calculating available cash

			log.Debug().
				Str("symbol", symbol).
				Int("quantity", quantity).
				Int("from", currentQuantity).
				Int("to", newQuantity).
				Msg("Applied pending SELL")

		} else {
			log.Warn().Str("side", side).Str("symbol", symbol).Msg("Unknown order side")
		}
	}

	// Convert position_map back to list
	adjustedPositions := make([]Position, 0, len(positionMap))
	for symbol, qty := range positionMap {
		if qty > 0 {
			adjustedPositions = append(adjustedPositions, Position{
				Symbol:   symbol,
				Quantity: qty,
			})
		}
	}

	return adjustedPositions, adjustedCash
}

// GeneratePortfolioHash generates a deterministic hash from current portfolio state.
//
// The hash includes:
//   - All positions (including zero quantities for securities in universe)
//   - Cash balances as pseudo-positions (CASH.EUR, CASH.USD, etc.)
//   - The full securities universe to detect when new securities are added
//   - Per-symbol configuration: allow_buy, allow_sell, min_portfolio_target, max_portfolio_target, country, industry
//
// Args:
//   - positions: List of positions with symbol and quantity
//   - securities: Optional list of Security objects in universe (to detect new securities and include config)
//   - cashBalances: Optional map of currency -> amount (e.g., {"EUR": 1500.0})
//   - pendingOrders: Optional list of pending orders
//
// Returns:
//   - 8-character hex hash (first 8 chars of MD5)
func GeneratePortfolioHash(
	positions []Position,
	securities []*universe.Security,
	cashBalances map[string]float64,
	pendingOrders []PendingOrder,
) string {
	// Apply pending orders to get hypothetical future state
	if len(pendingOrders) > 0 {
		// Allow negative cash for hypothetical portfolio state
		positions, cashBalances = ApplyPendingOrdersToPortfolio(
			positions,
			cashBalances,
			pendingOrders,
			true, // allow_negative_cash
		)
	}

	// Build a map of symbol -> quantity from positions
	positionMap := make(map[string]interface{})
	for _, p := range positions {
		symbol := strings.ToUpper(p.Symbol)
		positionMap[symbol] = p.Quantity
	}

	// Build a map of symbol -> security config data
	stockConfigMap := make(map[string]map[string]interface{})

	if securities != nil {
		for _, security := range securities {
			symbolUpper := strings.ToUpper(security.Symbol)
			// Ensure security is in position_map (with 0 if not held)
			if _, exists := positionMap[symbolUpper]; !exists {
				positionMap[symbolUpper] = 0
			}

			// Extract config fields
			country := security.Country
			industry := security.Industry

			minTarget := ""
			if security.MinPortfolioTarget > 0 {
				minTarget = fmt.Sprintf("%v", security.MinPortfolioTarget)
			}
			maxTarget := ""
			if security.MaxPortfolioTarget > 0 {
				maxTarget = fmt.Sprintf("%v", security.MaxPortfolioTarget)
			}

			stockConfigMap[symbolUpper] = map[string]interface{}{
				"allow_buy":            security.AllowBuy,
				"allow_sell":           security.AllowSell,
				"min_portfolio_target": minTarget,
				"max_portfolio_target": maxTarget,
				"country":              country,
				"industry":             industry,
			}
		}
	}

	// Add cash balances as pseudo-positions (filter out zero balances)
	if cashBalances != nil {
		for currency, amount := range cashBalances {
			if amount > 0 {
				// Round to 2 decimal places for stability
				rounded := math.Round(amount*100) / 100
				positionMap[fmt.Sprintf("CASH.%s", strings.ToUpper(currency))] = rounded
			}
		}
	}

	// Sort by symbol for deterministic ordering
	sortedSymbols := make([]string, 0, len(positionMap))
	for symbol := range positionMap {
		sortedSymbols = append(sortedSymbols, symbol)
	}
	sort.Strings(sortedSymbols)

	// Build canonical string: "SYMBOL:QUANTITY:allow_buy:allow_sell:min_target:max_target:country:industry"
	parts := make([]string, 0, len(sortedSymbols))
	for _, symbol := range sortedSymbols {
		quantity := positionMap[symbol]

		// Use different format for cash vs securities
		if strings.HasPrefix(symbol, "CASH.") {
			parts = append(parts, fmt.Sprintf("%s:%v", symbol, quantity))
		} else {
			// Get config for this symbol (use defaults if not in securities list)
			config := stockConfigMap[symbol]
			if config == nil {
				config = map[string]interface{}{
					"allow_buy":            true,
					"allow_sell":           false,
					"min_portfolio_target": "",
					"max_portfolio_target": "",
					"country":              "",
					"industry":             "",
				}
			}

			part := fmt.Sprintf("%s:%d:%v:%v:%s:%s:%s:%s",
				symbol,
				quantity,
				config["allow_buy"],
				config["allow_sell"],
				config["min_portfolio_target"],
				config["max_portfolio_target"],
				config["country"],
				config["industry"],
			)
			parts = append(parts, part)
		}
	}

	canonical := strings.Join(parts, ",")

	// Generate hash and return first 8 characters
	hash := md5.Sum([]byte(canonical))
	fullHash := fmt.Sprintf("%x", hash)
	return fullHash[:8]
}

// GenerateSettingsHash generates a deterministic hash from settings that affect recommendations.
//
// Args:
//   - settings: Map of settings values
//
// Returns:
//   - 8-character hex hash (first 8 chars of MD5)
func GenerateSettingsHash(settings map[string]interface{}) string {
	// Settings that affect recommendation calculations
	relevantKeys := []string{
		"min_security_score",
		"min_hold_days",
		"sell_cooldown_days",
		"max_loss_threshold",
		"target_annual_return",
		"optimizer_blend",
		"optimizer_target_return",
		"transaction_cost_fixed",
		"transaction_cost_percent",
		"min_cash_reserve",
		"max_plan_depth",
	}
	sort.Strings(relevantKeys)

	// Build canonical string: "key:value,key:value,..."
	parts := make([]string, 0, len(relevantKeys))
	for _, k := range relevantKeys {
		value := ""
		if v, exists := settings[k]; exists && v != nil {
			value = fmt.Sprintf("%v", v)
		}
		parts = append(parts, fmt.Sprintf("%s:%s", k, value))
	}
	canonical := strings.Join(parts, ",")

	// Generate hash and return first 8 characters
	hash := md5.Sum([]byte(canonical))
	fullHash := fmt.Sprintf("%x", hash)
	return fullHash[:8]
}

// GenerateAllocationsHash generates a deterministic hash from allocation targets.
//
// Args:
//   - allocations: Map of allocation targets with keys like "country:United States"
//     or "industry:Technology" and values as target percentages
//
// Returns:
//   - 8-character hex hash (first 8 chars of MD5)
func GenerateAllocationsHash(allocations map[string]float64) string {
	if len(allocations) == 0 {
		return "00000000" // Empty allocations
	}

	// Sort by key for deterministic ordering
	sortedKeys := make([]string, 0, len(allocations))
	for k := range allocations {
		sortedKeys = append(sortedKeys, k)
	}
	sort.Strings(sortedKeys)

	// Build canonical string: "key:value,key:value,..."
	// Round values to 4 decimal places for stability
	parts := make([]string, 0, len(sortedKeys))
	for _, k := range sortedKeys {
		rounded := math.Round(allocations[k]*10000) / 10000
		parts = append(parts, fmt.Sprintf("%s:%.4f", k, rounded))
	}
	canonical := strings.Join(parts, ",")

	// Generate hash and return first 8 characters
	hash := md5.Sum([]byte(canonical))
	fullHash := fmt.Sprintf("%x", hash)
	return fullHash[:8]
}

// GenerateRecommendationCacheKey generates a cache key from portfolio state, settings, and allocations.
//
// This ensures that cache is invalidated when positions, settings,
// securities universe, cash balances, per-symbol configuration, allocation targets,
// or pending orders change.
//
// Args:
//   - positions: List of positions with symbol and quantity
//   - settings: Map of settings values
//   - securities: Optional list of Security objects in universe
//   - cashBalances: Optional map of currency -> amount
//   - allocations: Optional map of allocation targets (e.g., {"country:US": 0.6})
//   - pendingOrders: Optional list of pending orders
//
// Returns:
//   - 26-character combined hash (portfolio_hash:settings_hash:allocations_hash)
func GenerateRecommendationCacheKey(
	positions []Position,
	settings map[string]interface{},
	securities []*universe.Security,
	cashBalances map[string]float64,
	allocations map[string]float64,
	pendingOrders []PendingOrder,
) string {
	portfolioHash := GeneratePortfolioHash(positions, securities, cashBalances, pendingOrders)
	settingsHash := GenerateSettingsHash(settings)
	allocationsHash := GenerateAllocationsHash(allocations)
	return fmt.Sprintf("%s:%s:%s", portfolioHash, settingsHash, allocationsHash)
}
