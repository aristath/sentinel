package tradernet

import (
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// transformPositions transforms SDK AccountSummary positions to []Position
func transformPositions(sdkResult interface{}, _ zerolog.Logger) ([]Position, error) {
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

		// Extract position fields per API documentation:
		// - q: Number of securities in the position (quantity)
		// - mkt_price: Current market price
		// - bal_price_a: Book value (average cost basis)
		quantity := getFloat64(posMap, "q")
		currentPrice := getFloat64(posMap, "mkt_price")
		avgPrice := getFloat64(posMap, "bal_price_a")

		position := Position{
			Symbol:        symbol,
			Quantity:      quantity,
			AvgPrice:      avgPrice,
			CurrentPrice:  currentPrice,
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

		// Country: "issuer_country_code" or "country"
		if countryVal, exists := itemMap["issuer_country_code"]; exists && countryVal != nil {
			if countryStr, ok := countryVal.(string); ok && countryStr != "" {
				sec.Country = &countryStr
			}
		}
		if sec.Country == nil {
			if countryVal, exists := itemMap["country"]; exists && countryVal != nil {
				if countryStr, ok := countryVal.(string); ok && countryStr != "" {
					sec.Country = &countryStr
				}
			}
		}

		// Sector: "sector_code" or "sector"
		if sectorVal, exists := itemMap["sector_code"]; exists && sectorVal != nil {
			if sectorStr, ok := sectorVal.(string); ok && sectorStr != "" {
				sec.Sector = &sectorStr
			}
		}
		if sec.Sector == nil {
			if sectorVal, exists := itemMap["sector"]; exists && sectorVal != nil {
				if sectorStr, ok := sectorVal.(string); ok && sectorStr != "" {
					sec.Sector = &sectorStr
				}
			}
		}

		// Exchange name: "codesub_nm" or "exchange_name"
		if exNameVal, exists := itemMap["codesub_nm"]; exists && exNameVal != nil {
			if exNameStr, ok := exNameVal.(string); ok && exNameStr != "" {
				sec.ExchangeName = &exNameStr
			}
		}
		if sec.ExchangeName == nil {
			if exNameVal, exists := itemMap["exchange_name"]; exists && exNameVal != nil {
				if exNameStr, ok := exNameVal.(string); ok && exNameStr != "" {
					sec.ExchangeName = &exNameStr
				}
			}
		}

		securities = append(securities, sec)
	}

	return securities, nil
}

// transformAllSecuritiesResponse transforms getAllSecurities API response to []SecurityInfo
// This response format is different from tickerFinder - it uses "securities" array
// and includes issuer_country_code and sector_code fields
func transformAllSecuritiesResponse(sdkResult interface{}) ([]SecurityInfo, error) {
	resultMap, ok := sdkResult.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: expected map[string]interface{}")
	}

	// getAllSecurities returns {"securities": [...], "total": N}
	securitiesRaw, ok := resultMap["securities"]
	if !ok || securitiesRaw == nil {
		return []SecurityInfo{}, nil
	}

	securitiesArray, ok := securitiesRaw.([]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid securities format: expected array, got %T", securitiesRaw)
	}

	securities := make([]SecurityInfo, 0, len(securitiesArray))
	for _, item := range securitiesArray {
		itemMap, ok := item.(map[string]interface{})
		if !ok {
			continue
		}

		// getAllSecurities uses "ticker" field for symbol
		symbol := getString(itemMap, "ticker")
		if symbol == "" {
			continue
		}

		sec := SecurityInfo{
			Symbol: symbol,
		}

		// Name
		if nameVal, exists := itemMap["name"]; exists && nameVal != nil {
			if nameStr, ok := nameVal.(string); ok && nameStr != "" {
				sec.Name = &nameStr
			}
		}

		// ISIN: "issue_nb" in getAllSecurities response
		if isinVal, exists := itemMap["issue_nb"]; exists && isinVal != nil {
			if isinStr, ok := isinVal.(string); ok && isinStr != "" {
				sec.ISIN = &isinStr
			}
		}

		// Currency: "face_curr_c" in getAllSecurities response
		if currVal, exists := itemMap["face_curr_c"]; exists && currVal != nil {
			if currStr, ok := currVal.(string); ok && currStr != "" {
				sec.Currency = &currStr
			}
		}

		// Market: "mkt_name" in getAllSecurities response
		if mktVal, exists := itemMap["mkt_name"]; exists && mktVal != nil {
			if mktStr, ok := mktVal.(string); ok && mktStr != "" {
				sec.Market = &mktStr
			}
		}

		// Exchange code: "code_nm" in getAllSecurities response
		if exVal, exists := itemMap["code_nm"]; exists && exVal != nil {
			if exStr, ok := exVal.(string); ok && exStr != "" {
				sec.ExchangeCode = &exStr
			}
		}

		// Country: "issuer_country_code" - the key field we need!
		if countryVal, exists := itemMap["issuer_country_code"]; exists && countryVal != nil {
			if countryStr, ok := countryVal.(string); ok && countryStr != "" {
				sec.Country = &countryStr
			}
		}

		// Sector: "sector_code" - the key field we need!
		if sectorVal, exists := itemMap["sector_code"]; exists && sectorVal != nil {
			if sectorStr, ok := sectorVal.(string); ok && sectorStr != "" {
				sec.Sector = &sectorStr
			}
		}

		// Exchange name: "codesub_nm" in getAllSecurities response
		if exNameVal, exists := itemMap["codesub_nm"]; exists && exNameVal != nil {
			if exNameStr, ok := exNameVal.(string); ok && exNameStr != "" {
				sec.ExchangeName = &exNameStr
			}
		}

		// CountryOfRisk: from nested "attributes.CntryOfRisk" - fallback when issuer_country_code is "0"
		if attrsVal, exists := itemMap["attributes"]; exists && attrsVal != nil {
			if attrsMap, ok := attrsVal.(map[string]interface{}); ok {
				if countryRiskVal, exists := attrsMap["CntryOfRisk"]; exists && countryRiskVal != nil {
					if countryRiskStr, ok := countryRiskVal.(string); ok && countryRiskStr != "" {
						sec.CountryOfRisk = &countryRiskStr
					}
				}
			}
		}

		// LotSize: from nested "quotes.x_lot"
		if quotesVal, exists := itemMap["quotes"]; exists && quotesVal != nil {
			if quotesMap, ok := quotesVal.(map[string]interface{}); ok {
				if lotVal, exists := quotesMap["x_lot"]; exists && lotVal != nil {
					// x_lot can be int or float64 depending on JSON unmarshaling
					switch v := lotVal.(type) {
					case float64:
						lot := int(v)
						sec.LotSize = &lot
					case int:
						sec.LotSize = &v
					}
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

// transformQuotes transforms SDK GetQuotes response to map[symbol]*Quote
// Handles the getStockQuotesJson response format with "q" array
func transformQuotes(sdkResult interface{}) (map[string]*Quote, error) {
	resultMap, ok := sdkResult.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: expected map[string]interface{}")
	}

	result, ok := resultMap["result"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: missing or invalid 'result' field")
	}

	quotesArray, ok := result["q"].([]interface{})
	if !ok {
		// Empty result - return empty map
		return make(map[string]*Quote), nil
	}

	quotes := make(map[string]*Quote, len(quotesArray))
	for _, item := range quotesArray {
		itemMap, ok := item.(map[string]interface{})
		if !ok {
			continue
		}

		// Get symbol from "c" field (Tradernet uses "c" for ticker in getStockQuotesJson)
		symbol := getString(itemMap, "c")
		if symbol == "" {
			continue
		}

		quote := &Quote{
			Symbol:    symbol,
			Price:     getFloat64(itemMap, "ltp"), // last trade price
			Change:    getFloat64(itemMap, "chg"), // change
			ChangePct: getFloat64(itemMap, "pcp"), // change percent
			Volume:    int64(getFloat64(itemMap, "vol")),
			Timestamp: time.Now().Format(time.RFC3339),
		}

		quotes[symbol] = quote
	}

	return quotes, nil
}

// transformCandles transforms SDK GetCandles (getHloc) response to []OHLCV
// Response format: {hloc: {symbol: [[h,l,o,c], ...]}, vl: {symbol: [vol, ...]}, xSeries: {symbol: [ts, ...]}}
func transformCandles(sdkResult interface{}, symbol string) ([]OHLCV, error) {
	resultMap, ok := sdkResult.(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("invalid SDK result format: expected map[string]interface{}")
	}

	// Extract hloc data
	hlocMap, ok := resultMap["hloc"].(map[string]interface{})
	if !ok {
		return []OHLCV{}, nil // Empty result
	}

	symbolHloc, ok := hlocMap[symbol].([]interface{})
	if !ok {
		return []OHLCV{}, nil // No data for this symbol
	}

	// Extract volumes
	vlMap, _ := resultMap["vl"].(map[string]interface{})
	symbolVol, _ := vlMap[symbol].([]interface{})

	// Extract timestamps
	xSeriesMap, _ := resultMap["xSeries"].(map[string]interface{})
	symbolTimestamps, _ := xSeriesMap[symbol].([]interface{})

	// Build OHLCV slice
	candles := make([]OHLCV, 0, len(symbolHloc))
	for i, hlocItem := range symbolHloc {
		hlocArr, ok := hlocItem.([]interface{})
		if !ok || len(hlocArr) < 4 {
			continue
		}

		candle := OHLCV{
			High:  getFloat64FromValue(hlocArr[0]),
			Low:   getFloat64FromValue(hlocArr[1]),
			Open:  getFloat64FromValue(hlocArr[2]),
			Close: getFloat64FromValue(hlocArr[3]),
		}

		// Get volume if available
		if i < len(symbolVol) {
			candle.Volume = int64(getFloat64FromValue(symbolVol[i]))
		}

		// Get timestamp if available
		if i < len(symbolTimestamps) {
			candle.Timestamp = int64(getFloat64FromValue(symbolTimestamps[i]))
		}

		candles = append(candles, candle)
	}

	// Validate and interpolate abnormal prices
	validatedCandles := validateAndInterpolateCandles(candles)

	return validatedCandles, nil
}

// Validation thresholds for Layer 1 (API response validation)
// Note: No absolute price bounds - only relative checks. This system must work for 15+ years
// and absolute bounds like "Close > 10,000" are arbitrary and will break over time.
const (
	highCloseMaxRatioL1 = 100.0  // High ≤ Close × 100
	lowCloseMinRatioL1  = 0.01   // Low ≥ Close × 0.01
	maxPriceChangePctL1 = 1000.0 // >1000% spike detection
	minPriceChangePctL1 = -90.0  // <-90% crash detection
)

// OHLCValidation tracks validity of each OHLC component
type OHLCValidation struct {
	OpenValid  bool
	HighValid  bool
	LowValid   bool
	CloseValid bool
	Reason     string
}

// NeedsFullInterpolation returns true when Close is invalid (Close is the anchor)
func (v OHLCValidation) NeedsFullInterpolation() bool {
	return !v.CloseValid
}

// NeedsInterpolation returns true when any component is invalid
func (v OHLCValidation) NeedsInterpolation() bool {
	return !v.OpenValid || !v.HighValid || !v.LowValid || !v.CloseValid
}

// AllValid returns true when all components are valid
func (v OHLCValidation) AllValid() bool {
	return v.OpenValid && v.HighValid && v.LowValid && v.CloseValid
}

// validateOHLCComponents validates each OHLC component independently
// Note: No absolute price bounds - only relative checks. This system must work for 15+ years
// and absolute bounds like "Close > 10,000" are arbitrary and will break over time.
// However, zero/negative prices are clearly invalid (missing data) regardless of time horizon.
func validateOHLCComponents(candle OHLCV, prev, next *OHLCV) OHLCValidation {
	result := OHLCValidation{
		OpenValid: true, HighValid: true, LowValid: true, CloseValid: true,
	}

	// Zero/negative Close indicates missing or invalid data
	if candle.Close <= 0 {
		result.CloseValid = false
		result.OpenValid = false
		result.HighValid = false
		result.LowValid = false
		result.Reason = "close_zero_or_negative"
		return result
	}

	// High validation - relative to Close (100x threshold)
	if candle.Close > 0 && candle.High > candle.Close*highCloseMaxRatioL1 {
		result.HighValid = false
		result.Reason = "high_extreme_relative_to_close"
	}

	// Low validation - relative to Close (0.01x threshold)
	if candle.Close > 0 && candle.Low > 0 && candle.Low < candle.Close*lowCloseMinRatioL1 {
		result.LowValid = false
		if result.Reason == "" {
			result.Reason = "low_extreme_relative_to_close"
		}
	}

	// OHLC consistency checks
	if candle.High < candle.Low {
		result.HighValid = false
		result.LowValid = false
		if result.Reason == "" {
			result.Reason = "ohlc_inconsistent_high_below_low"
		}
	}
	if candle.High < candle.Open {
		result.HighValid = false
		if result.Reason == "" {
			result.Reason = "ohlc_inconsistent_high_below_open"
		}
	}
	if candle.High < candle.Close {
		result.HighValid = false
		if result.Reason == "" {
			result.Reason = "ohlc_inconsistent_high_below_close"
		}
	}
	if candle.Low > candle.Open {
		result.LowValid = false
		if result.Reason == "" {
			result.Reason = "ohlc_inconsistent_low_above_open"
		}
	}
	if candle.Low > candle.Close {
		result.LowValid = false
		if result.Reason == "" {
			result.Reason = "ohlc_inconsistent_low_above_close"
		}
	}

	// Spike/crash detection for Close (requires neighbors)
	if prev != nil && prev.Close > 0 {
		changePercent := ((candle.Close - prev.Close) / prev.Close) * 100.0
		if changePercent > maxPriceChangePctL1 || changePercent < minPriceChangePctL1 {
			// Check if next confirms it's anomalous
			if next != nil && next.Close > 0 {
				nextChange := ((next.Close - prev.Close) / prev.Close) * 100.0
				if nextChange <= maxPriceChangePctL1 && nextChange >= minPriceChangePctL1 {
					// Next is normal, so current is spike/crash
					result.CloseValid = false
					result.OpenValid = false
					result.HighValid = false
					result.LowValid = false
					result.Reason = "close_spike_or_crash"
				}
			}
		}
	}

	return result
}

// interpolateOHLCVSelective interpolates only invalid components
func interpolateOHLCVSelective(candle OHLCV, index int, allCandles []OHLCV, validation OHLCValidation) OHLCV {
	if validation.NeedsFullInterpolation() {
		return interpolateOHLCVFull(candle, index, allCandles)
	}

	interpolated := candle // Preserve valid values

	before, after := findValidNeighborsL1(index, allCandles)

	if !validation.HighValid {
		ratio := getTypicalHighCloseRatioL1(before, after)
		interpolated.High = interpolated.Close * ratio
	}

	if !validation.LowValid {
		ratio := getTypicalLowCloseRatioL1(before, after)
		interpolated.Low = interpolated.Close * ratio
	}

	if !validation.OpenValid {
		if before != nil {
			interpolated.Open = before.Close
		} else if after != nil {
			interpolated.Open = after.Open
		}
	}

	ensureOHLCConsistencyL1(&interpolated)
	return interpolated
}

// interpolateOHLCVFull performs full interpolation when Close is invalid
func interpolateOHLCVFull(candle OHLCV, index int, allCandles []OHLCV) OHLCV {
	interpolated := candle // Preserve timestamp and volume

	before, after := findValidNeighborsL1(index, allCandles)

	// Linear interpolation if both available
	if before != nil && after != nil {
		interpolated.Close = (before.Close + after.Close) / 2.0
		interpolated.Open = (before.Open + after.Open) / 2.0
		interpolated.High = (before.High + after.High) / 2.0
		interpolated.Low = (before.Low + after.Low) / 2.0
	} else if before != nil {
		// Forward fill
		interpolated.Close = before.Close
		interpolated.Open = before.Open
		interpolated.High = before.High
		interpolated.Low = before.Low
	} else if after != nil {
		// Backward fill
		interpolated.Close = after.Close
		interpolated.Open = after.Open
		interpolated.High = after.High
		interpolated.Low = after.Low
	}

	ensureOHLCConsistencyL1(&interpolated)
	return interpolated
}

// findValidNeighborsL1 finds valid candles before and after given index
func findValidNeighborsL1(index int, candles []OHLCV) (*OHLCV, *OHLCV) {
	var before, after *OHLCV

	for i := index - 1; i >= 0; i-- {
		v := validateOHLCComponents(candles[i], nil, nil)
		if v.CloseValid {
			before = &candles[i]
			break
		}
	}

	for i := index + 1; i < len(candles); i++ {
		v := validateOHLCComponents(candles[i], nil, nil)
		if v.CloseValid {
			after = &candles[i]
			break
		}
	}

	return before, after
}

// getTypicalHighCloseRatioL1 calculates average High/Close ratio from neighbors
func getTypicalHighCloseRatioL1(before, after *OHLCV) float64 {
	var sum float64
	var count int

	if before != nil && before.Close > 0 {
		sum += before.High / before.Close
		count++
	}
	if after != nil && after.Close > 0 {
		sum += after.High / after.Close
		count++
	}

	if count == 0 {
		return 1.02 // Default: High is 2% above Close
	}
	return sum / float64(count)
}

// getTypicalLowCloseRatioL1 calculates average Low/Close ratio from neighbors
func getTypicalLowCloseRatioL1(before, after *OHLCV) float64 {
	var sum float64
	var count int

	if before != nil && before.Close > 0 {
		sum += before.Low / before.Close
		count++
	}
	if after != nil && after.Close > 0 {
		sum += after.Low / after.Close
		count++
	}

	if count == 0 {
		return 0.98 // Default: Low is 2% below Close
	}
	return sum / float64(count)
}

// ensureOHLCConsistencyL1 ensures OHLC consistency for OHLCV type
func ensureOHLCConsistencyL1(candle *OHLCV) {
	// Ensure High >= all
	if candle.High < candle.Close {
		candle.High = candle.Close
	}
	if candle.High < candle.Open {
		candle.High = candle.Open
	}

	// Ensure Low <= all
	if candle.Low > candle.Close {
		candle.Low = candle.Close
	}
	if candle.Low > candle.Open {
		candle.Low = candle.Open
	}

	// Ensure High >= Low
	if candle.High < candle.Low {
		candle.High = candle.Low
	}
}

// validateAndInterpolateCandles validates OHLCV candles and interpolates abnormal ones
// Uses component-level validation to preserve valid data while fixing invalid components
func validateAndInterpolateCandles(candles []OHLCV) []OHLCV {
	if len(candles) == 0 {
		return candles
	}

	validated := make([]OHLCV, 0, len(candles))

	for i, candle := range candles {
		var prev, next *OHLCV
		if i > 0 {
			prev = &candles[i-1]
		}
		if i < len(candles)-1 {
			next = &candles[i+1]
		}

		validation := validateOHLCComponents(candle, prev, next)

		if validation.AllValid() {
			validated = append(validated, candle)
			continue
		}

		interpolated := interpolateOHLCVSelective(candle, i, candles, validation)
		validated = append(validated, interpolated)
	}

	return validated
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
