package tradernet

import (
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// transformPositions transforms SDK AccountSummary positions to []Position
func transformPositions(sdkResult interface{}, log zerolog.Logger) ([]Position, error) {
	resultMap, ok := sdkResult.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: expected map[string]interface{}")
	}

	result, ok := resultMap["result"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: missing 'result' field")
	}

	ps, ok := result["ps"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: missing 'ps' field")
	}

	posArray, ok := ps["pos"].([]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: missing or invalid 'pos' array")
	}

	positions := make([]Position, 0, len(posArray))
	for _, posItem := range posArray {
		posMap, ok := posItem.(map[string]interface{})
		if !ok {
			continue
		}

		symbol := getString(posMap, "i")

		// DEBUG: Log all raw fields for each position, especially TSM.US
		// Convert posMap to JSON for readable logging
		rawJSON, _ := json.Marshal(posMap)
		log.Debug().
			Str("symbol", symbol).
			RawJSON("raw_position", rawJSON).
			Msg("transformPositions: raw position data from API")

		// Extract all quantity-related fields for analysis
		fieldQ := getFloat64(posMap, "q")
		fieldS := getFloat64(posMap, "s")
		fieldFV := getFloat64(posMap, "fv")
		fieldMarketValue := getFloat64(posMap, "market_value")
		fieldMktPrice := getFloat64(posMap, "mkt_price")
		fieldBalPriceA := getFloat64(posMap, "bal_price_a")

		// DEBUG: Log comparison of fields for investigation
		log.Debug().
			Str("symbol", symbol).
			Float64("field_q", fieldQ).
			Float64("field_s", fieldS).
			Float64("field_fv", fieldFV).
			Float64("api_market_value", fieldMarketValue).
			Float64("mkt_price", fieldMktPrice).
			Float64("bal_price_a", fieldBalPriceA).
			Float64("calculated_from_q", fieldQ*fieldMktPrice).
			Float64("calculated_from_s", fieldS*fieldMktPrice).
			Msg("transformPositions: field comparison for quantity analysis")

		position := Position{
			Symbol:        symbol,
			Quantity:      fieldQ, // SUSPECTED BUG: This might be wrong field
			AvgPrice:      fieldBalPriceA,
			CurrentPrice:  fieldMktPrice,
			UnrealizedPnL: getFloat64(posMap, "profit_close"),
			Currency:      getString(posMap, "curr"),
			CurrencyRate:  0.0, // Will be set during portfolio sync from cache
		}

		// Calculate MarketValue in native currency (USD/HKD/GBP/etc)
		position.MarketValue = position.Quantity * position.CurrentPrice

		// CURRENCY CONVERSION BOUNDARY:
		// MarketValueEUR is intentionally NOT converted here. Broker layer returns raw data.
		// Currency conversion to EUR happens at the input boundary BEFORE planning:
		//   - Portfolio sync (portfolio.PortfolioService) converts when storing to DB
		//   - Planner input (buildOpportunityContext) converts via PriceConversionService
		// This ensures the planner receives EUR-normalized values for holistic decisions.
		// The broker only provides native currency data; downstream layers handle conversion.
		position.MarketValueEUR = position.MarketValue

		positions = append(positions, position)
	}

	return positions, nil
}

// transformCashBalances transforms SDK AccountSummary cash accounts to []CashBalance
func transformCashBalances(sdkResult interface{}) ([]CashBalance, error) {
	resultMap, ok := sdkResult.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: expected map[string]interface{}")
	}

	result, ok := resultMap["result"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: missing 'result' field")
	}

	ps, ok := result["ps"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: missing 'ps' field")
	}

	accArray, ok := ps["acc"].([]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: missing or invalid 'acc' array")
	}

	balances := make([]CashBalance, 0, len(accArray))
	for _, accItem := range accArray {
		accMap, ok := accItem.(map[string]interface{})
		if !ok {
			continue
		}

		balance := CashBalance{
			Currency: getString(accMap, "curr"),
			Amount:   getFloat64(accMap, "s"),
		}

		balances = append(balances, balance)
	}

	return balances, nil
}

// transformOrderResult transforms SDK Buy/Sell response to OrderResult
func transformOrderResult(sdkResult interface{}, symbol, side string, quantity float64) (*OrderResult, error) {
	resultMap, ok := sdkResult.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: expected map[string]interface{}")
	}

	// Extract order ID - check both 'id' and 'order_id' fields
	var orderID string
	if idVal, exists := resultMap["order_id"]; exists {
		orderID = fmt.Sprintf("%v", idVal)
	} else if idVal, exists := resultMap["id"]; exists {
		orderID = fmt.Sprintf("%v", idVal)
	} else {
		return nil, fmt.Errorf("invalid SDK result format: missing 'id' or 'order_id' field")
	}

	// Extract price - check both 'price' and 'p' fields
	var price float64
	if pVal, exists := resultMap["price"]; exists {
		price = getFloat64FromValue(pVal)
	} else if pVal, exists := resultMap["p"]; exists {
		price = getFloat64FromValue(pVal)
	} else {
		price = 0.0
	}

	return &OrderResult{
		OrderID:  orderID,
		Symbol:   symbol,
		Side:     side,
		Quantity: quantity,
		Price:    price,
	}, nil
}

// extractPendingOrder extracts a single pending order from a map
func extractPendingOrder(orderMap map[string]interface{}) *PendingOrder {
	// Extract order ID - check both 'id' and 'orderId' fields
	var orderID string
	if idVal, exists := orderMap["orderId"]; exists {
		orderID = fmt.Sprintf("%v", idVal)
	} else if idVal, exists := orderMap["id"]; exists {
		orderID = fmt.Sprintf("%v", idVal)
	} else {
		return nil // Skip orders without ID
	}

	order := &PendingOrder{
		OrderID:  orderID,
		Symbol:   getSymbol(orderMap),   // Use helper with fallback
		Side:     convertSide(orderMap), // Extract side (was missing)
		Quantity: getFloat64(orderMap, "q"),
		Price:    getFloat64(orderMap, "p"),
		Currency: getString(orderMap, "curr"),
	}

	return order
}

// transformPendingOrders transforms SDK GetPlaced response to []PendingOrder
// Handles both array format ({"result": [...]}) and map format ({"result": {...}})
func transformPendingOrders(sdkResult interface{}) ([]PendingOrder, error) {
	resultMap, ok := sdkResult.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: expected map[string]interface{}")
	}

	// Handle empty or null result
	result, ok := resultMap["result"]
	if !ok || result == nil {
		// Empty result - return empty array
		return []PendingOrder{}, nil
	}

	orders := make([]PendingOrder, 0)

	// Handle array format: {"result": [{...}, {...}]}
	if resultArray, ok := result.([]interface{}); ok {
		for _, orderItem := range resultArray {
			orderMap, ok := orderItem.(map[string]interface{})
			if !ok {
				continue
			}

			order := extractPendingOrder(orderMap)
			if order != nil {
				orders = append(orders, *order)
			}
		}
	} else if resultMapData, ok := result.(map[string]interface{}); ok {
		// Handle map format: {"result": {...}} (single order as map)
		order := extractPendingOrder(resultMapData)
		if order != nil {
			orders = append(orders, *order)
		}
	} else {
		return nil, fmt.Errorf("invalid SDK result format: 'result' must be array or map, got %T", result)
	}

	return orders, nil
}

// transformCashMovements transforms SDK GetClientCpsHistory to CashMovementsResponse
func transformCashMovements(sdkResult interface{}) (*CashMovementsResponse, error) {
	resultMap, ok := sdkResult.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: expected map[string]interface{}")
	}

	// Handle empty or null result
	result, ok := resultMap["result"]
	if !ok || result == nil {
		// Empty result - return empty response
		return &CashMovementsResponse{
			Withdrawals: []map[string]interface{}{},
		}, nil
	}

	resultArray, ok := result.([]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: 'result' must be array, got %T", result)
	}

	withdrawals := make([]map[string]interface{}, 0, len(resultArray))
	var totalWithdrawals float64

	for _, item := range resultArray {
		itemMap, ok := item.(map[string]interface{})
		if !ok {
			continue
		}

		withdrawals = append(withdrawals, itemMap)

		// Sum up withdrawal amounts if available
		if amount, exists := itemMap["amount"]; exists {
			if amtFloat, ok := amount.(float64); ok {
				totalWithdrawals += amtFloat
			}
		}
	}

	return &CashMovementsResponse{
		TotalWithdrawals: totalWithdrawals,
		Withdrawals:      withdrawals,
		Note:             "",
	}, nil
}

// transformCashFlows transforms SDK responses to []CashFlowTransaction
func transformCashFlows(sdkResult interface{}) ([]CashFlowTransaction, error) {
	resultMap, ok := sdkResult.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: expected map[string]interface{}")
	}

	// Handle API response structure: {"cps": [...], "total": ...}
	cpsArray, ok := resultMap["cps"].([]interface{})
	if !ok || cpsArray == nil {
		// Empty result - return empty array
		return []CashFlowTransaction{}, nil
	}

	transactions := make([]CashFlowTransaction, 0, len(cpsArray))
	for _, item := range cpsArray {
		itemMap, ok := item.(map[string]interface{})
		if !ok {
			continue
		}

		tx := CashFlowTransaction{
			ID:              getString(itemMap, "id"),
			TransactionID:   getString(itemMap, "transaction_id"),
			TypeDocID:       int(getFloat64(itemMap, "type_doc_id")),
			Type:            getString(itemMap, "type"),
			TransactionType: getString(itemMap, "transaction_type"),
			DT:              getString(itemMap, "dt"),
			Date:            getString(itemMap, "date"),
			SM:              getFloat64(itemMap, "sm"),
			Amount:          getFloat64(itemMap, "amount"),
			Curr:            getString(itemMap, "curr"),
			Currency:        getString(itemMap, "currency"),
			SMEUR:           getFloat64(itemMap, "sm_eur"),
			AmountEUR:       getFloat64(itemMap, "amount_eur"),
			Status:          getString(itemMap, "status"),
			StatusC:         int(getFloat64(itemMap, "status_c")),
			Description:     getString(itemMap, "description"),
		}

		// Handle params field
		if params, exists := itemMap["params"]; exists {
			if paramsMap, ok := params.(map[string]interface{}); ok {
				tx.Params = paramsMap
			} else {
				tx.Params = make(map[string]interface{})
			}
		} else {
			tx.Params = make(map[string]interface{})
		}

		transactions = append(transactions, tx)
	}

	return transactions, nil
}

// transformTrades transforms SDK GetTradesHistory to []Trade
func transformTrades(sdkResult interface{}) ([]Trade, error) {
	resultMap, ok := sdkResult.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: expected map[string]interface{}, got %T", sdkResult)
	}

	// DEBUG: Log the raw response structure for diagnostics
	responseKeys := make([]string, 0)
	for key := range resultMap {
		responseKeys = append(responseKeys, key)
	}

	// Log all available keys in response
	rawJSON, _ := json.Marshal(resultMap)
	_ = fmt.Sprintf("DEBUG transformTrades response keys: %v, full response: %s", responseKeys, string(rawJSON))

	// Check if API returned an error
	if errMsg, ok := resultMap["errMsg"].(string); ok && errMsg != "" {
		return nil, fmt.Errorf("API error: %s", errMsg)
	}
	if errMsg, ok := resultMap["error"].(string); ok && errMsg != "" {
		return nil, fmt.Errorf("API error: %s", errMsg)
	}

	// Handle API response structure: {"trades": {"trade": [...], "max_trade_id": [...]}}
	tradesObj, ok := resultMap["trades"]
	if !ok || tradesObj == nil {
		// Empty result - return empty array
		return []Trade{}, nil
	}

	tradesMap, ok := tradesObj.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: 'trades' must be object, got %T", tradesObj)
	}

	// Extract trade array
	tradeArray, ok := tradesMap["trade"].([]interface{})
	if !ok {
		// No trades in response - return empty array
		return []Trade{}, nil
	}

	trades := make([]Trade, 0, len(tradeArray))
	for _, item := range tradeArray {
		itemMap, ok := item.(map[string]interface{})
		if !ok {
			continue
		}

		// Extract order ID - check both 'order_id' and 'id' fields
		var orderID string
		if idVal, exists := itemMap["order_id"]; exists {
			orderID = fmt.Sprintf("%v", idVal)
		} else if idVal, exists := itemMap["id"]; exists {
			orderID = fmt.Sprintf("%v", idVal)
		} else {
			continue // Skip trades without ID
		}

		price := getFloat64(itemMap, "p")
		symbol := getSymbol(itemMap)

		trade := Trade{
			OrderID:    orderID,
			Symbol:     symbol,
			Side:       convertSide(itemMap), // Convert type field
			Quantity:   getFloat64(itemMap, "q"),
			Price:      price,
			ExecutedAt: getExecutedAt(itemMap), // Use helper with fallback
		}

		trades = append(trades, trade)
	}

	return trades, nil
}

// transformSecurityInfo transforms SDK FindSymbol to []SecurityInfo
// Handles both normalized format ({"result": [...]}) and raw API format ({"found": [...]})
// Maps short field names from API ("t", "nm", "x_curr", etc.) to expected field names
func transformSecurityInfo(sdkResult interface{}) ([]SecurityInfo, error) {
	resultMap, ok := sdkResult.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: expected map[string]interface{}")
	}

	// Handle both "result" (normalized) and "found" (raw API response from tickerFinder)
	var result interface{}
	var okResult bool
	if result, okResult = resultMap["found"]; !okResult || result == nil {
		// Fallback to "result" for normalized responses
		result, okResult = resultMap["result"]
	}
	if !okResult || result == nil {
		// Empty result - return empty array
		return []SecurityInfo{}, nil
	}

	resultArray, ok := result.([]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: 'found'/'result' must be array, got %T", result)
	}

	securities := make([]SecurityInfo, 0, len(resultArray))
	for _, item := range resultArray {
		itemMap, ok := item.(map[string]interface{})
		if !ok {
			continue
		}

		// Map field names: API uses short names ("t", "nm", "x_curr") but also supports full names
		// Try short names first (raw API format), fallback to full names (normalized format)
		symbol := getString(itemMap, "t") // Short form
		if symbol == "" {
			symbol = getString(itemMap, "symbol") // Full form (normalized)
		}

		if symbol == "" {
			continue // Skip items without symbol
		}

		sec := SecurityInfo{
			Symbol: symbol,
		}

		// Name: "nm" (short) or "name" (full)
		if nameVal, exists := itemMap["nm"]; exists && nameVal != nil {
			if nameStr, ok := nameVal.(string); ok && nameStr != "" {
				sec.Name = &nameStr
			}
		}
		if sec.Name == nil {
			if nameVal, exists := itemMap["name"]; exists && nameVal != nil {
				if nameStr, ok := nameVal.(string); ok && nameStr != "" {
					sec.Name = &nameStr
				}
			}
		}

		// ISIN: same in both formats
		if isin, exists := itemMap["isin"]; exists && isin != nil {
			if isinStr, ok := isin.(string); ok && isinStr != "" {
				sec.ISIN = &isinStr
			}
		}

		// Currency: "x_curr" (short) or "currency" (full)
		if currVal, exists := itemMap["x_curr"]; exists && currVal != nil {
			if currStr, ok := currVal.(string); ok && currStr != "" {
				sec.Currency = &currStr
			}
		}
		if sec.Currency == nil {
			if currVal, exists := itemMap["currency"]; exists && currVal != nil {
				if currStr, ok := currVal.(string); ok && currStr != "" {
					sec.Currency = &currStr
				}
			}
		}

		// Market: "mkt" (short) or "market" (full)
		if mktVal, exists := itemMap["mkt"]; exists && mktVal != nil {
			if mktStr, ok := mktVal.(string); ok && mktStr != "" {
				sec.Market = &mktStr
			}
		}
		if sec.Market == nil {
			if mktVal, exists := itemMap["market"]; exists && mktVal != nil {
				if mktStr, ok := mktVal.(string); ok && mktStr != "" {
					sec.Market = &mktStr
				}
			}
		}

		// Exchange code: "codesub" (short) or "exchange_code" (full)
		if exVal, exists := itemMap["codesub"]; exists && exVal != nil {
			if exStr, ok := exVal.(string); ok && exStr != "" {
				sec.ExchangeCode = &exStr
			}
		}
		if sec.ExchangeCode == nil {
			if exVal, exists := itemMap["exchange_code"]; exists && exVal != nil {
				if exStr, ok := exVal.(string); ok && exStr != "" {
					sec.ExchangeCode = &exStr
				}
			}
		}

		securities = append(securities, sec)
	}

	return securities, nil
}

// transformQuote transforms SDK GetQuotes to Quote
// Handles both array and map response formats from getStockQuotesJson
func transformQuote(sdkResult interface{}, symbol string) (*Quote, error) {
	resultMap, ok := sdkResult.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: expected map[string]interface{}")
	}

	result, ok := resultMap["result"]
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: missing 'result' field")
	}

	var symbolData map[string]interface{}

	// Handle array format: result is an array of quote objects
	if resultArray, ok := result.([]interface{}); ok {
		// Search for the quote with matching symbol
		found := false
		for _, item := range resultArray {
			itemMap, ok := item.(map[string]interface{})
			if !ok {
				continue
			}
			// Check if this item matches the symbol
			// The symbol might be in different fields: "symbol", "i", "ticker", etc.
			itemSymbol := getString(itemMap, "symbol")
			if itemSymbol == "" {
				itemSymbol = getString(itemMap, "i")
			}
			if itemSymbol == "" {
				itemSymbol = getString(itemMap, "ticker")
			}
			if itemSymbol == symbol {
				symbolData = itemMap
				found = true
				break
			}
		}
		if !found {
			return nil, fmt.Errorf("quote not found for symbol: %s", symbol)
		}
	} else if resultMapData, ok := result.(map[string]interface{}); ok {
		// Handle map format: result is a map keyed by symbol
		var found bool
		symbolData, found = resultMapData[symbol].(map[string]interface{})
		if !found {
			return nil, fmt.Errorf("quote not found for symbol: %s", symbol)
		}
	} else {
		return nil, fmt.Errorf("invalid SDK result format: 'result' must be array or map, got %T", result)
	}

	quote := &Quote{
		Symbol:    symbol,
		Price:     getFloat64(symbolData, "p"),
		Change:    getFloat64(symbolData, "change"),
		ChangePct: getFloat64(symbolData, "change_pct"),
		Volume:    int64(getFloat64(symbolData, "volume")),
		Timestamp: getString(symbolData, "timestamp"),
	}

	// Handle alternative field names (fallback)
	if quote.Price == 0 {
		quote.Price = getFloat64(symbolData, "ltp")
	}
	if quote.Price == 0 {
		quote.Price = getFloat64(symbolData, "last_price")
	}
	if quote.Change == 0 {
		quote.Change = getFloat64(symbolData, "chg")
	}
	if quote.ChangePct == 0 {
		quote.ChangePct = getFloat64(symbolData, "chg_pc")
	}
	if quote.Volume == 0 {
		quote.Volume = int64(getFloat64(symbolData, "v"))
	}

	return quote, nil
}

// Helper functions

// getString safely extracts a string value from a map
func getString(m map[string]interface{}, key string) string {
	if val, exists := m[key]; exists {
		if str, ok := val.(string); ok {
			return str
		}
		// Try to convert other types to string
		return fmt.Sprintf("%v", val)
	}
	return ""
}

// getFloat64 safely extracts a float64 value from a map
// transformCrossRates transforms SDK getCrossRatesForDate response to map[string]float64
func transformCrossRates(sdkResult interface{}) (map[string]float64, error) {
	resultMap, ok := sdkResult.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: expected map[string]interface{}")
	}

	ratesMap, ok := resultMap["rates"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: missing or invalid 'rates' key")
	}

	rates := make(map[string]float64, len(ratesMap))
	for currency, rateVal := range ratesMap {
		rate := getFloat64FromValue(rateVal)
		rates[currency] = rate
	}

	return rates, nil
}

func getFloat64(m map[string]interface{}, key string) float64 {
	if val, exists := m[key]; exists {
		return getFloat64FromValue(val)
	}
	return 0.0
}

// getFloat64FromValue safely converts a value to float64
func getFloat64FromValue(val interface{}) float64 {
	switch v := val.(type) {
	case float64:
		return v
	case float32:
		return float64(v)
	case int:
		return float64(v)
	case int64:
		return float64(v)
	case int32:
		return float64(v)
	case string:
		// Tradernet API returns some numeric fields as strings (e.g., "p": "141.4")
		if floatVal, err := strconv.ParseFloat(v, 64); err == nil {
			return floatVal
		}
		return 0.0
	default:
		return 0.0
	}
}

// getSymbol extracts symbol with fallback (instr_nm → i → instr_name)
func getSymbol(m map[string]interface{}) string {
	// Try instr_nm first (most trades use this)
	if val := getString(m, "instr_nm"); val != "" {
		return val
	}
	// Try instr_name (pending orders use this)
	if val := getString(m, "instr_name"); val != "" {
		return val
	}
	// Fallback to i (older format)
	return getString(m, "i")
}

// getExecutedAt extracts date with fallback (date → d → executed_at)
func getExecutedAt(m map[string]interface{}) string {
	if val := getString(m, "date"); val != "" {
		return val
	}
	if val := getString(m, "d"); val != "" {
		return val
	}
	return getString(m, "executed_at")
}

// convertSide converts API type field to BUY/SELL
// Handles: type="1" → BUY, type="2" → SELL, buy_sell="buy"/"BUY" → BUY, etc.
func convertSide(m map[string]interface{}) string {
	// Try "type" field first (trades use numeric codes)
	if typeVal := getString(m, "type"); typeVal != "" {
		switch typeVal {
		case TradernetOrderTypeBuy:
			return OrderSideBuy
		case TradernetOrderTypeSell:
			return OrderSideSell
		}
	}

	// Try "buy_sell" field (pending orders use this, can be lowercase or uppercase)
	if sideVal := getString(m, "buy_sell"); sideVal != "" {
		// Normalize to uppercase to handle "buy"/"BUY" and "sell"/"SELL"
		upper := strings.ToUpper(sideVal)
		if upper == OrderSideBuy || upper == OrderSideSell {
			return upper
		}
	}

	// Try "side" field as fallback (normalize to uppercase)
	if sideVal := getString(m, "side"); sideVal != "" {
		upper := strings.ToUpper(sideVal)
		if upper == OrderSideBuy || upper == OrderSideSell {
			return upper
		}
	}

	return ""
}

// transformOrderBook transforms Tradernet quotes response to simplified order book
// Note: Full order book requires WebSocket. This creates simplified version from quote data.
// Extracts best bid/ask from quote fields: bbp (bid price), bbs (bid size), bap (ask price), bas (ask size)
func transformOrderBook(result interface{}, symbol string) (*OrderBook, error) {
	data, ok := result.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("unexpected response type: %T", result)
	}

	// Extract result array (getStockQuotesJson returns {"result": {"q": [...]}}
	resultData, ok := data["result"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid quotes response: missing result map")
	}

	quotes, ok := resultData["q"].([]interface{})
	if !ok || len(quotes) == 0 {
		return nil, fmt.Errorf("invalid quotes response: missing or empty q array")
	}

	// Get first quote (we only request one symbol)
	quoteData, ok := quotes[0].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid quote data type: %T", quotes[0])
	}

	orderBook := &OrderBook{
		Symbol:    symbol,
		Bids:      []OrderBookLevel{},
		Asks:      []OrderBookLevel{},
		Timestamp: time.Now().Format(time.RFC3339),
		Count:     2, // Simplified: just best bid and ask
	}

	// Extract best bid (bbp = best bid price, bbs = best bid size)
	bidPrice := parsePrice(getString(quoteData, "bbp"))
	bidSize := parseSize(getString(quoteData, "bbs"))
	if bidPrice > 0 && bidSize > 0 {
		orderBook.Bids = append(orderBook.Bids, OrderBookLevel{
			Price:    bidPrice,
			Quantity: bidSize,
			Position: 1,
			Side:     "B",
		})
	}

	// Extract best ask (bap = best ask price, bas = best ask size)
	askPrice := parsePrice(getString(quoteData, "bap"))
	askSize := parseSize(getString(quoteData, "bas"))
	if askPrice > 0 && askSize > 0 {
		orderBook.Asks = append(orderBook.Asks, OrderBookLevel{
			Price:    askPrice,
			Quantity: askSize,
			Position: 1,
			Side:     "S",
		})
	}

	if len(orderBook.Bids) == 0 && len(orderBook.Asks) == 0 {
		return nil, fmt.Errorf("no bid/ask data in quote for %s", symbol)
	}

	return orderBook, nil
}

// parsePrice parses price string (e.g., "147,39" or "147.39") to float64
func parsePrice(s string) float64 {
	if s == "" {
		return 0
	}
	// Replace comma with dot for decimal separator
	s = strings.Replace(s, ",", ".", 1)
	val, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return 0
	}
	return val
}

// parseSize parses size string (e.g., "89170") to float64
func parseSize(s string) float64 {
	if s == "" {
		return 0
	}
	val, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return 0
	}
	return val
}
