package tradernet

import "github.com/aristath/sentinel/internal/domain"

// Tradernet API Field Name Mappings
//
// Tradernet uses cryptic, abbreviated field names in their API responses.
// This document maps their names to our domain model for reference.
//
// Position Fields:
//   "i"            → Symbol           (instrument ticker)
//   "q"            → Quantity         (quantity held)
//   "bal_price_a"  → AvgPrice         (average purchase price)
//   "mkt_price"    → CurrentPrice     (current market price)
//   "profit_close" → UnrealizedPnL    (unrealized profit/loss)
//   "curr"         → Currency         (currency code)
//
// Cash Flow Fields (multiple variants for same concept):
//   "dt"           → Date             (transaction date - cryptic abbreviation)
//   "date"         → Date             (clear variant)
//   "sm"           → Amount           (сумма = amount in Russian - cryptic)
//   "amount"       → Amount           (clear variant)
//   "curr"         → Currency         (currency code - abbreviated)
//   "currency"     → Currency         (clear variant)
//   "sm_eur"       → AmountEUR        (amount in EUR - cryptic)
//   "amount_eur"   → AmountEUR        (clear variant)
//   "type"         → Type             (transaction type - ambiguous)
//   "transaction_type" → Type         (clear variant)
//
// Trade Fields:
//   "i"/"instr_nm"/"instr_name" → Symbol  (three variants!)
//   "side"/"d"/"type"           → Side    (BUY/SELL - three variants!)
//   "q"/"qty"/"quantity"        → Quantity
//   "p"/"price"                 → Price
//   "executed_at"/"date"/"d"    → ExecutedAt
//
// Security Search Fields:
//   "t"/"symbol"     → Symbol
//   "nm"/"name"      → Name
//   "x_curr"/"currency" → Currency (why "x_"? unclear)
//   "mkt"/"market"   → Market
//   "codesub"/"exchange_code" → ExchangeCode
//
// Order Type Codes (magic numbers):
//   "1" → BUY
//   "2" → SELL
//
// Note: Tradernet's API is inconsistent - different endpoints use different
// field names for the same concept. Transformers handle all variants with
// priority-based fallback logic (clear names preferred over cryptic ones).
//
// Constants are defined in constants.go

// transformPositionsToDomain converts Tradernet positions to domain broker positions
func transformPositionsToDomain(tnPositions []Position) []domain.BrokerPosition {
	result := make([]domain.BrokerPosition, len(tnPositions))
	for i, tn := range tnPositions {
		result[i] = domain.BrokerPosition{
			Symbol:         tn.Symbol,
			Quantity:       tn.Quantity,
			AvgPrice:       tn.AvgPrice,
			CurrentPrice:   tn.CurrentPrice,
			MarketValue:    tn.MarketValue,
			MarketValueEUR: tn.MarketValueEUR,
			UnrealizedPnL:  tn.UnrealizedPnL,
			Currency:       tn.Currency,
			CurrencyRate:   tn.CurrencyRate,
		}
	}
	return result
}

// transformCashBalancesToDomain converts Tradernet cash balances to domain broker cash balances
func transformCashBalancesToDomain(tnBalances []CashBalance) []domain.BrokerCashBalance {
	result := make([]domain.BrokerCashBalance, len(tnBalances))
	for i, tn := range tnBalances {
		result[i] = domain.BrokerCashBalance{
			Currency: tn.Currency,
			Amount:   tn.Amount,
		}
	}
	return result
}

// transformOrderResultToDomain converts Tradernet order result to domain broker order result
func transformOrderResultToDomain(tnResult *OrderResult) *domain.BrokerOrderResult {
	if tnResult == nil {
		return nil
	}
	return &domain.BrokerOrderResult{
		OrderID:  tnResult.OrderID,
		Symbol:   tnResult.Symbol,
		Side:     tnResult.Side,
		Quantity: tnResult.Quantity,
		Price:    tnResult.Price,
	}
}

// transformTradesToDomain converts Tradernet trades to domain broker trades
func transformTradesToDomain(tnTrades []Trade) []domain.BrokerTrade {
	result := make([]domain.BrokerTrade, len(tnTrades))
	for i, tn := range tnTrades {
		result[i] = domain.BrokerTrade{
			OrderID:    tn.OrderID,
			Symbol:     tn.Symbol,
			Side:       tn.Side,
			Quantity:   tn.Quantity,
			Price:      tn.Price,
			ExecutedAt: tn.ExecutedAt,
		}
	}
	return result
}

// transformQuoteToDomain converts Tradernet quote to domain broker quote
func transformQuoteToDomain(tnQuote *Quote) *domain.BrokerQuote {
	if tnQuote == nil {
		return nil
	}
	return &domain.BrokerQuote{
		Symbol:    tnQuote.Symbol,
		Price:     tnQuote.Price,
		Change:    tnQuote.Change,
		ChangePct: tnQuote.ChangePct,
		Volume:    tnQuote.Volume,
		Timestamp: tnQuote.Timestamp,
	}
}

// transformQuotesToDomain converts a map of Tradernet quotes to domain broker quotes
func transformQuotesToDomain(tnQuotes map[string]*Quote) map[string]*domain.BrokerQuote {
	if tnQuotes == nil {
		return nil
	}
	result := make(map[string]*domain.BrokerQuote, len(tnQuotes))
	for symbol, quote := range tnQuotes {
		result[symbol] = transformQuoteToDomain(quote)
	}
	return result
}

// transformOHLCVToDomain converts Tradernet OHLCV data to domain broker OHLCV
func transformOHLCVToDomain(tnCandles []OHLCV) []domain.BrokerOHLCV {
	if tnCandles == nil {
		return nil
	}
	result := make([]domain.BrokerOHLCV, len(tnCandles))
	for i, candle := range tnCandles {
		result[i] = domain.BrokerOHLCV{
			Timestamp: candle.Timestamp,
			Open:      candle.Open,
			High:      candle.High,
			Low:       candle.Low,
			Close:     candle.Close,
			Volume:    candle.Volume,
		}
	}
	return result
}

// transformPendingOrdersToDomain converts Tradernet pending orders to domain broker pending orders
func transformPendingOrdersToDomain(tnOrders []PendingOrder) []domain.BrokerPendingOrder {
	result := make([]domain.BrokerPendingOrder, len(tnOrders))
	for i, tn := range tnOrders {
		result[i] = domain.BrokerPendingOrder{
			OrderID:  tn.OrderID,
			Symbol:   tn.Symbol,
			Side:     tn.Side,
			Quantity: tn.Quantity,
			Price:    tn.Price,
			Currency: tn.Currency,
		}
	}
	return result
}

// transformSecurityInfoToDomain converts Tradernet security info to domain broker security info
func transformSecurityInfoToDomain(tnSecurities []SecurityInfo) []domain.BrokerSecurityInfo {
	result := make([]domain.BrokerSecurityInfo, len(tnSecurities))
	for i, tn := range tnSecurities {
		result[i] = domain.BrokerSecurityInfo{
			Symbol:        tn.Symbol,
			Name:          tn.Name,
			ISIN:          tn.ISIN,
			Currency:      tn.Currency,
			Market:        tn.Market,
			ExchangeCode:  tn.ExchangeCode,
			Country:       tn.Country,
			CountryOfRisk: tn.CountryOfRisk,
			Sector:        tn.Sector,
			ExchangeName:  tn.ExchangeName,
		}
	}
	return result
}

// transformCashFlowsToDomain converts Tradernet cash flows to domain broker cash flows
func transformCashFlowsToDomain(tnFlows []CashFlowTransaction) []domain.BrokerCashFlow {
	result := make([]domain.BrokerCashFlow, len(tnFlows))
	for i, tn := range tnFlows {
		// Preserve Tradernet-specific metadata in params
		params := tn.Params
		if params == nil {
			params = make(map[string]interface{})
		}
		// Store TypeDocID for preservation (Tradernet-specific, not in broker-agnostic domain)
		params["tradernet_type_doc_id"] = tn.TypeDocID

		result[i] = domain.BrokerCashFlow{
			ID:            tn.ID,
			TransactionID: tn.TransactionID,
			Type:          getTransactionTypeField(tn.TransactionType, tn.Type),
			Date:          getDateField(tn.Date, tn.DT),
			Amount:        getAmountField(tn.Amount, tn.SM),
			Currency:      getCurrencyField(tn.Currency, tn.Curr),
			AmountEUR:     getAmountEURField(tn.AmountEUR, tn.SMEUR),
			Status:        tn.Status,
			StatusC:       tn.StatusC,
			Description:   tn.Description,
			Params:        params,
		}
	}
	return result
}

// transformCashMovementsToDomain converts Tradernet cash movements to domain broker cash movements
func transformCashMovementsToDomain(tnMovements *CashMovementsResponse) *domain.BrokerCashMovement {
	if tnMovements == nil {
		return nil
	}
	return &domain.BrokerCashMovement{
		TotalWithdrawals: tnMovements.TotalWithdrawals,
		Withdrawals:      tnMovements.Withdrawals,
		Note:             tnMovements.Note,
	}
}

// transformHealthResultToDomain converts Tradernet health result to domain broker health result
func transformHealthResultToDomain(tnHealth *HealthCheckResult) *domain.BrokerHealthResult {
	if tnHealth == nil {
		return nil
	}
	return &domain.BrokerHealthResult{
		Connected: tnHealth.Connected,
		Timestamp: tnHealth.Timestamp,
	}
}

// Field extraction helpers - encapsulate Tradernet's inconsistent naming

// getDateField extracts date from Tradernet response, handling multiple field names.
//
// Priority: "date" (clear) > "dt" (cryptic)
//
// Tradernet API behavior:
// - Modern responses populate both fields with same value
// - Legacy responses may only populate "dt"
// - If both are populated, "date" typically has more precision (includes time)
//
// Returns: The date value, preferring "date" over "dt"
func getDateField(date, dt string) string {
	if date != "" {
		return date
	}
	return dt
}

// getAmountField extracts transaction amount, handling multiple field names.
//
// Priority: "amount" (clear) > "sm" (Russian "сумма")
//
// Tradernet API behavior:
// - Modern responses populate both fields with the same value
// - Legacy responses may only populate "sm"
// - Zero is a valid amount (e.g., $0 fee adjustments)
//
// Logic: Always prefer "amount" unless it's 0 AND "sm" is non-zero (legacy edge case)
// Returns: The amount value, handling legitimate zero amounts correctly
func getAmountField(amount, sm float64) float64 {
	// If amount is non-zero, use it (clear field has data)
	// If amount is zero and sm is also zero, use amount (legitimate $0)
	// Only use sm if amount is zero but sm is non-zero (rare legacy case)
	if amount != 0 || sm == 0 {
		return amount
	}
	return sm
}

// getCurrencyField extracts currency code, handling multiple field names.
//
// Priority: "currency" (clear) > "curr" (abbreviated)
//
// Tradernet API behavior:
// - Modern responses populate both fields with same value
// - Legacy responses may only populate "curr"
//
// Returns: The currency code, preferring "currency" over "curr"
func getCurrencyField(currency, curr string) string {
	if currency != "" {
		return currency
	}
	return curr
}

// getAmountEURField extracts EUR amount, handling multiple field names.
//
// Priority: "amount_eur" (clear) > "sm_eur" (Russian "сумма")
//
// Tradernet API behavior:
// - Modern responses populate both fields with same value
// - Legacy responses may only populate "sm_eur"
// - Zero is a valid EUR amount
//
// Logic: Always prefer "amount_eur" unless it's 0 AND "sm_eur" is non-zero (legacy edge case)
// Returns: The EUR amount, handling legitimate zero amounts correctly
func getAmountEURField(amountEUR, smEUR float64) float64 {
	// Same logic as getAmountField - zero is valid
	if amountEUR != 0 || smEUR == 0 {
		return amountEUR
	}
	return smEUR
}

// getTransactionTypeField extracts transaction type, handling multiple field names.
//
// Priority: "transaction_type" (clear) > "type" (ambiguous)
//
// Tradernet API behavior:
// - Modern responses populate both fields
// - "transaction_type" is more specific (e.g., "wire_transfer")
// - "type" is more generic (e.g., "deposit")
//
// Returns: The transaction type, preferring "transaction_type" over "type"
func getTransactionTypeField(transactionType, typeField string) string {
	if transactionType != "" {
		return transactionType
	}
	return typeField
}

// transformOrderBookToDomain converts Tradernet order book to domain BrokerOrderBook
func transformOrderBookToDomain(tn *OrderBook) *domain.BrokerOrderBook {
	if tn == nil {
		return nil
	}

	domainBids := make([]domain.OrderBookLevel, len(tn.Bids))
	for i, level := range tn.Bids {
		domainBids[i] = domain.OrderBookLevel{
			Price:    level.Price,
			Quantity: level.Quantity,
			Position: level.Position,
		}
	}

	domainAsks := make([]domain.OrderBookLevel, len(tn.Asks))
	for i, level := range tn.Asks {
		domainAsks[i] = domain.OrderBookLevel{
			Price:    level.Price,
			Quantity: level.Quantity,
			Position: level.Position,
		}
	}

	return &domain.BrokerOrderBook{
		Symbol:    tn.Symbol,
		Bids:      domainBids,
		Asks:      domainAsks,
		Timestamp: tn.Timestamp,
	}
}
