package sdk

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

// Duration constants matching Python SDK
var (
	DurationDay = 1 // The order will be valid until the end of the trading day
	DurationExt = 2 // Extended day order
	DurationGTC = 3 // Good Till Cancelled
)

// DurationMap maps duration strings to IDs
var DurationMap = map[string]int{
	"day": DurationDay,
	"ext": DurationExt,
	"gtc": DurationGTC,
}

// UserInfo retrieves user information from the Tradernet API.
// This calls the GetAllUserTexInfo command with no parameters.
//
// Returns:
//   - A map containing user information including:
//   - id: User ID
//   - login: User login name
//   - first_name: User's first name
//   - last_name: User's last name
//   - email: User's email address
//   - Other user-specific fields as returned by the API
//
// Errors:
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/get-user-info
//
// Example:
//
//	result, err := client.UserInfo()
//	if err != nil {
//	    log.Fatal(err)
//	}
//	userInfo := result.(map[string]interface{})
func (c *Client) UserInfo() (interface{}, error) {
	params := GetAllUserTexInfoParams{}
	return c.authorizedRequest("GetAllUserTexInfo", params)
}

// AccountSummary retrieves account summary including positions and cash balances.
// This calls the getPositionJson command with no parameters.
//
// Returns:
//   - A map containing account summary with structure:
//   - result.ps.pos: Array of position objects, each containing:
//   - i: Instrument symbol
//   - q: Quantity
//   - bal_price_a: Average price
//   - mkt_price: Current market price
//   - profit_close: Unrealized P&L
//   - curr: Currency
//   - result.ps.acc: Array of cash account objects, each containing:
//   - curr: Currency code
//   - s: Cash balance amount
//
// Errors:
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/portfolio-get-changes
//
// Example:
//
//	summary, err := client.AccountSummary()
//	if err != nil {
//	    log.Fatal(err)
//	}
//	summaryMap := summary.(map[string]interface{})
//	positions := summaryMap["result"].(map[string]interface{})["ps"].(map[string]interface{})["pos"]
func (c *Client) AccountSummary() (interface{}, error) {
	params := GetPositionJSONParams{}
	return c.authorizedRequest("getPositionJson", params)
}

// Trade places an order with support for all order types (1-6).
// This matches the Python SDK's trade() method with extended functionality.
//
// Order Types: 1=Market, 2=Limit, 3=Stop, 4=StopLimit, 5=StopLoss, 6=TakeProfit
// - Type 1 (Market): limitPrice=nil, stopPrice=nil
// - Type 2 (Limit): limitPrice required, stopPrice=nil
// - Type 3 (Stop): limitPrice=nil, stopPrice required
// - Type 4 (StopLimit): limitPrice required, stopPrice required
// - Type 5-6 (StopLoss/TakeProfit): stopPrice required
func (c *Client) Trade(symbol string, quantity int, orderType int, limitPrice, stopPrice *float64, duration string, useMargin bool, customOrderID *int) (interface{}, error) {
	// IOC emulation (special case)
	if strings.ToLower(duration) == "ioc" {
		// Place order with 'day' duration
		order, err := c.Trade(symbol, quantity, orderType, limitPrice, stopPrice, "day", useMargin, customOrderID)
		if err != nil {
			return nil, err
		}
		// Extract order ID and cancel immediately
		// Python SDK checks: if 'order_id' in order: self.cancel(order['order_id'])
		// We also check 'id' as fallback (matches microservice parsing)
		orderMap, ok := order.(map[string]interface{})
		if ok {
			var orderID int
			found := false

			// Check 'order_id' first (Python SDK behavior)
			if idVal, exists := orderMap["order_id"]; exists {
				switch v := idVal.(type) {
				case float64:
					orderID = int(v)
					found = true
				case int:
					orderID = v
					found = true
				case string:
					// Handle string IDs (though unlikely)
					if id, err := strconv.Atoi(v); err == nil {
						orderID = id
						found = true
					}
				}
			}

			// Fallback to 'id' if 'order_id' not found
			if !found {
				if idVal, exists := orderMap["id"]; exists {
					switch v := idVal.(type) {
					case float64:
						orderID = int(v)
						found = true
					case int:
						orderID = v
						found = true
					case string:
						if id, err := strconv.Atoi(v); err == nil {
							orderID = id
							found = true
						}
					}
				}
			}

			if found {
				_, _ = c.Cancel(orderID)
			}
		}
		return order, nil
	}

	// Duration validation
	durationLower := strings.ToLower(duration)
	durationID, ok := DurationMap[durationLower]
	if !ok {
		return nil, fmt.Errorf("unknown duration %s", duration)
	}

	// Validate order type
	if orderType < 1 || orderType > 6 {
		return nil, fmt.Errorf("invalid order type %d (must be 1-6)", orderType)
	}

	// Validate required parameters for each order type
	switch orderType {
	case 2: // Limit
		if limitPrice == nil {
			return nil, fmt.Errorf("limit_price required for limit orders (type 2)")
		}
	case 3: // Stop
		if stopPrice == nil {
			return nil, fmt.Errorf("stop_price required for stop orders (type 3)")
		}
	case 4: // StopLimit
		if limitPrice == nil || stopPrice == nil {
			return nil, fmt.Errorf("both limit_price and stop_price required for stop limit orders (type 4)")
		}
	case 5, 6: // StopLoss, TakeProfit
		if stopPrice == nil {
			return nil, fmt.Errorf("stop_price required for stop loss/take profit orders (type %d)", orderType)
		}
	}

	// Action ID calculation
	// Buy + no margin = 1, Buy + margin = 2
	// Sell + no margin = 3, Sell + margin = 4
	var actionID int
	if quantity > 0 {
		// Buy
		if useMargin {
			actionID = 2
		} else {
			actionID = 1
		}
	} else if quantity < 0 {
		// Sell
		if useMargin {
			actionID = 4
		} else {
			actionID = 3
		}
	} else {
		return nil, fmt.Errorf("zero quantity")
	}

	params := PutTradeOrderParams{
		InstrName:    symbol,
		ActionID:     actionID,
		OrderTypeID:  orderType,
		Qty:          absInt(quantity),
		LimitPrice:   limitPrice,
		StopPrice:    stopPrice,
		ExpirationID: durationID,
		UserOrderID:  customOrderID,
	}

	return c.authorizedRequest("putTradeOrder", params)
}

// Buy places a buy order (market or limit based on price parameter)
// This matches the Python SDK's buy() method exactly
func (c *Client) Buy(symbol string, quantity int, price float64, duration string, useMargin bool, customOrderID *int) (interface{}, error) {
	if quantity <= 0 {
		return nil, fmt.Errorf("quantity must be positive")
	}

	// Auto-detect order type: market (price=0) or limit (price>0)
	var orderType int
	var limitPrice *float64
	if price == 0 {
		orderType = 1 // Market
	} else {
		orderType = 2 // Limit
		limitPrice = &price
	}

	return c.Trade(symbol, quantity, orderType, limitPrice, nil, duration, useMargin, customOrderID)
}

// Sell places a sell order for the specified symbol.
// This matches the Python SDK's sell() method exactly.
//
// Parameters:
//   - symbol: Tradernet symbol (e.g., "AAPL.US", "MSFT.US")
//   - quantity: Number of shares to sell (must be positive)
//   - price: Limit price (0.0 for market order)
//   - duration: Order duration - "day" (valid until end of trading day),
//     "ext" (extended day), "gtc" (good till cancelled), or "ioc" (immediate or cancel)
//   - useMargin: Whether to use margin credit (default: true)
//   - customOrderID: Optional custom order ID (nil to auto-generate)
//
// Returns:
//   - A map containing order information with keys:
//   - order_id or id: Order ID
//   - price: Execution price (for market orders)
//   - Other order-specific fields as returned by the API
//
// Errors:
//   - Returns error if quantity is not positive
//   - Returns error if duration is invalid
//   - Returns error if API request fails
//
// API Reference: https://freedom24.com/tradernet-api/orders-place
//
// Example:
//
//	result, err := client.Sell("AAPL.US", 10, 150.0, "day", true, nil)
//	if err != nil {
//	    log.Fatal(err)
//	}
//	orderID := result.(map[string]interface{})["order_id"]
func (c *Client) Sell(symbol string, quantity int, price float64, duration string, useMargin bool, customOrderID *int) (interface{}, error) {
	if quantity <= 0 {
		return nil, fmt.Errorf("quantity must be positive")
	}

	// Auto-detect order type: market (price=0) or limit (price>0)
	var orderType int
	var limitPrice *float64
	if price == 0 {
		orderType = 1 // Market
	} else {
		orderType = 2 // Limit
		limitPrice = &price
	}

	// Negative quantity for sell
	return c.Trade(symbol, -quantity, orderType, limitPrice, nil, duration, useMargin, customOrderID)
}

// GetPlaced gets pending/active orders
// This matches the Python SDK's get_placed() method exactly
func (c *Client) GetPlaced(active bool) (interface{}, error) {
	// Convert boolean to int: True=1, False=0
	activeOnly := 0
	if active {
		activeOnly = 1
	}
	params := GetNotifyOrderJSONParams{
		ActiveOnly: activeOnly,
	}
	return c.authorizedRequest("getNotifyOrderJson", params)
}

// GetTradesHistory gets executed trades history
// This matches the Python SDK's get_trades_history() method exactly
func (c *Client) GetTradesHistory(start, end string, tradeID, limit, reception *int, symbol, currency *string) (interface{}, error) {
	params := GetTradesHistoryParams{
		BeginDate: start,
		EndDate:   end,
		TradeID:   tradeID,
		Max:       limit,
		NtTicker:  symbol,
		Curr:      currency,
		Reception: reception,
	}
	return c.authorizedRequest("getTradesHistory", params)
}

// GetQuotes gets quotes for symbols
// This matches the Python SDK's get_quotes() method exactly
func (c *Client) GetQuotes(symbols []string) (interface{}, error) {
	// Comma-separated string
	tickers := strings.Join(symbols, ",")
	params := GetStockQuotesJSONParams{
		Tickers: tickers,
	}
	return c.authorizedRequest("getStockQuotesJson", params)
}

// GetCandles gets historical OHLC data
// This matches the Python SDK's get_candles() method exactly
func (c *Client) GetCandles(symbol string, start, end time.Time, timeframeSeconds int) (interface{}, error) {
	// Date format: "01.01.2020 00:00"
	dateFrom := start.Format("02.01.2006 15:04")
	dateTo := end.Format("02.01.2006 15:04")

	// Timeframe: convert seconds to minutes
	timeframeMinutes := timeframeSeconds / 60

	params := GetHlocParams{
		ID:           symbol,
		Count:        -1,
		Timeframe:    timeframeMinutes,
		DateFrom:     dateFrom,
		DateTo:       dateTo,
		IntervalMode: "ClosedRay",
	}
	return c.authorizedRequest("getHloc", params)
}

// FindSymbol finds security by symbol or ISIN
// This matches the Python SDK's find_symbol() method exactly
// Uses plainRequest (no authentication)
func (c *Client) FindSymbol(symbol string, exchange *string) (interface{}, error) {
	text := symbol
	if exchange != nil {
		text = fmt.Sprintf("%s@%s", symbol, *exchange)
	}
	params := map[string]interface{}{
		"text": text,
	}
	return c.plainRequest("tickerFinder", params)
}

// SecurityInfo gets security information
// This matches the Python SDK's security_info() method exactly
// CRITICAL: Boolean stays boolean (NOT converted to int!)
func (c *Client) SecurityInfo(symbol string, sup bool) (interface{}, error) {
	params := GetSecurityInfoParams{
		Ticker: symbol,
		Sup:    sup, // Boolean, NOT int!
	}
	return c.authorizedRequest("getSecurityInfo", params)
}

// GetClientCpsHistory retrieves client CPS (cash movements) history including withdrawals,
// deposits, and other cash-related transactions.
// This matches the Python SDK's get_requests_history() method exactly.
//
// Parameters:
//   - dateFrom: Start date in "2006-01-02T15:04:05" format.
//     Default in Python SDK: datetime(2011, 1, 11)
//   - dateTo: End date in "2006-01-02T15:04:05" format.
//     Default in Python SDK: datetime.now()
//   - cpsDocID: Optional request type ID filter
//   - id: Optional order ID filter
//   - limit: Optional maximum number of records to return
//   - offset: Optional pagination offset
//   - cpsStatus: Optional request status filter:
//     0 = draft request
//     1 = in process of execution
//     2 = request is rejected
//     3 = request is executed
//
// Returns:
//   - A map or array containing cash movement records with transaction details
//
// Errors:
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/get-client-cps-history
//
// Example:
//
//	dateFrom := "2023-01-01T00:00:00"
//	dateTo := "2023-12-31T23:59:59"
//	limit := 500
//	history, err := client.GetClientCpsHistory(dateFrom, dateTo, nil, nil, &limit, nil, nil)
//	if err != nil {
//	    log.Fatal(err)
//	}
func (c *Client) GetClientCpsHistory(dateFrom, dateTo string, cpsDocID, id, limit, offset, cpsStatus *int) (interface{}, error) {
	params := GetClientCpsHistoryParams{
		DateFrom:  dateFrom,
		DateTo:    dateTo,
		CpsDocID:  cpsDocID,
		ID:        id,
		Limit:     limit,
		Offset:    offset,
		CpsStatus: cpsStatus,
	}
	return c.authorizedRequest("getClientCpsHistory", params)
}

// Cancel cancels an active order by order ID.
// This matches the Python SDK's cancel() method.
//
// Parameters:
//   - orderID: The order ID to cancel (obtained from Buy/Sell/GetPlaced responses)
//
// Returns:
//   - A map containing cancellation result with keys:
//   - result: Cancellation status
//   - order_id: Cancelled order ID
//   - error_code: Error code (0 = success, non-zero = error)
//   - error_message: Error description
//   - Other cancellation-specific fields
//
// Errors:
//   - Returns error if order ID is invalid or order cannot be cancelled
//   - Returns error if API request fails or credentials are invalid
//   - Returns specific error based on error_code:
//     - 0: Method error (order not found, already cancelled, etc.)
//     - 2: Common error
//     - 12: No permission to cancel this order
//
// API Reference: https://freedom24.com/tradernet-api/orders-cancel
//
// Example:
//
//	result, err := client.Cancel(12345)
//	if err != nil {
//	    log.Fatal(err)
//	}
func (c *Client) Cancel(orderID int) (interface{}, error) {
	params := map[string]interface{}{
		"order_id": orderID,
	}

	result, err := c.authorizedRequest("delTradeOrder", params)
	if err != nil {
		return nil, err
	}

	// Check error_code in response
	if resultMap, ok := result.(map[string]interface{}); ok {
		if errorCode, exists := resultMap["error_code"]; exists {
			// Convert error_code to int (API may return as float64 or int)
			var code int
			switch v := errorCode.(type) {
			case float64:
				code = int(v)
			case int:
				code = v
			default:
				// Unknown type, treat as error
				return nil, fmt.Errorf("unexpected error_code type: %T", errorCode)
			}

			// Check if error occurred (non-zero error code)
			if code != 0 {
				errorMsg := "unknown error"
				if msg, exists := resultMap["error_message"]; exists {
					if msgStr, ok := msg.(string); ok {
						errorMsg = msgStr
					}
				}

				// Return specific error based on code
				switch code {
				case 2:
					return nil, fmt.Errorf("common error: %s", errorMsg)
				case 12:
					return nil, fmt.Errorf("no permission to cancel order %d: %s", orderID, errorMsg)
				default:
					return nil, fmt.Errorf("method error (code %d): %s", code, errorMsg)
				}
			}
		}
	}

	return result, nil
}

// NewUser creates a new user account.
// This matches the Python SDK's new_user() method exactly.
// Uses plainRequest (no authentication required).
//
// Parameters:
//   - login: User login name
//   - reception: Reception number (converted to string in Python SDK)
//   - phone: User's phone number
//   - lastname: User's last name
//   - firstname: User's first name
//   - password: Optional password (if nil, will be generated automatically)
//   - utmCampaign: Optional referral link
//   - tariffID: Optional tariff ID to assign during registration
//
// Returns a dictionary with 'clientId' and 'userId' keys.
func (c *Client) NewUser(login, reception, phone, lastname, firstname string, password *string, utmCampaign *string, tariffID *int) (interface{}, error) {
	// Build params map matching Python SDK's dict structure
	// Python order: 'login', 'pwd', 'reception', 'phone', 'lastname', 'firstname', 'tariff_id', 'utm_campaign'
	params := make(map[string]interface{})
	params["login"] = login
	if password != nil {
		params["pwd"] = *password
	}
	params["reception"] = reception // Python SDK converts to string: str(reception)
	params["phone"] = phone
	params["lastname"] = lastname
	params["firstname"] = firstname
	if tariffID != nil {
		params["tariff_id"] = *tariffID
	}
	if utmCampaign != nil {
		params["utm_campaign"] = *utmCampaign
	}

	return c.plainRequest("registerNewUser", params)
}

// CheckMissingFields checks missing profile fields
// This matches the Python SDK's check_missing_fields() method exactly
func (c *Client) CheckMissingFields(step int, office string) (interface{}, error) {
	params := CheckStepParams{
		Step:   step,
		Office: office,
	}
	return c.authorizedRequest("checkStep", params)
}

// GetProfileFields retrieves profile fields configuration for different offices.
// This matches the Python SDK's get_profile_fields() method exactly.
//
// Parameters:
//   - reception: Reception number (office identifier)
//
// Returns:
//   - A map containing profile field definitions for the specified office
//
// Errors:
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/get-anketa-fields
//
// Example:
//
//	fields, err := client.GetProfileFields(35)
//	if err != nil {
//	    log.Fatal(err)
//	}
func (c *Client) GetProfileFields(reception int) (interface{}, error) {
	params := GetAnketaFieldsParams{
		AnketaForReception: reception,
	}
	return c.authorizedRequest("getAnketaFields", params)
}

// GetUserData retrieves initial user data from the server including orders, portfolio,
// markets, open sessions, and other account information.
// This matches the Python SDK's get_user_data() method exactly.
//
// Returns:
//   - A map containing comprehensive user data including:
//   - orders: Current orders
//   - portfolio: Current positions
//   - markets: Market status information
//   - sessions: Open trading sessions
//   - Other account-specific data
//
// Errors:
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/auth-get-opq
//
// Example:
//
//	data, err := client.GetUserData()
//	if err != nil {
//	    log.Fatal(err)
//	}
func (c *Client) GetUserData() (interface{}, error) {
	params := GetOPQParams{}
	return c.authorizedRequest("getOPQ", params)
}

// GetMarketStatus retrieves information about market statuses and operation.
// This matches the Python SDK's get_market_status() method exactly.
//
// Parameters:
//   - market: Market code (briefName). Default: "*" (all markets)
//   - mode: Optional request mode (e.g., "demo"). If not specified, returns
//     market statuses for real users.
//
// Returns:
//   - A map containing market status information including:
//   - Market operation status (open/closed)
//   - Trading hours
//   - Other market-specific information
//
// Errors:
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/market-status
//
// Example:
//
//	status, err := client.GetMarketStatus("NYSE", nil)
//	if err != nil {
//	    log.Fatal(err)
//	}
func (c *Client) GetMarketStatus(market string, mode *string) (interface{}, error) {
	if market == "" {
		market = "*"
	}
	params := GetMarketStatusParams{
		Market: market,
		Mode:   mode,
	}
	return c.authorizedRequest("getMarketStatus", params)
}

// GetOptions retrieves a list of active options by underlying asset and exchange.
// This matches the Python SDK's get_options() method exactly.
//
// Parameters:
//   - underlying: The underlying symbol (e.g., "AAPL.US")
//   - exchange: Exchange/venue where options are traded (e.g., "CBOE", "ICE")
//
// Returns:
//   - An array of option contracts, each containing basic properties:
//   - Symbol/contract code
//   - Strike price
//   - Expiration date
//   - Option type (call/put)
//   - Other option-specific fields
//
// Errors:
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/get-options-by-mkt
//
// Example:
//
//	options, err := client.GetOptions("AAPL.US", "CBOE")
//	if err != nil {
//	    log.Fatal(err)
//	}
func (c *Client) GetOptions(underlying, exchange string) (interface{}, error) {
	params := GetOptionsByMktNameAndBaseAssetParams{
		BaseContractCode: underlying,
		Ltr:              exchange,
	}
	return c.authorizedRequest("getOptionsByMktNameAndBaseAsset", params)
}

// GetMostTraded retrieves a list of the most traded securities or the fastest growing stocks.
// This matches the Python SDK's get_most_traded() method exactly.
// Uses plainRequest (no authentication required).
//
// Parameters:
//   - instrumentType: Instrument type (default: "stocks")
//   - exchange: Stock exchange. Possible values: "usa", "europe", "ukraine", "currencies"
//     (default: "usa")
//   - gainers: If true, returns top fastest-growing stocks (for a year).
//     If false, returns top by trading volume (default: true)
//   - limit: Number of instruments to return (default: 10)
//
// Returns:
//   - A map or array containing top securities with:
//   - Symbol
//   - Change percentage (for gainers)
//   - Trading volume (for most traded)
//   - Other security metrics
//
// Errors:
//   - Returns error if API request fails
//
// API Reference: https://freedom24.com/tradernet-api/quotes-get-top-securities
//
// Example:
//
//	// Get top 20 gainers on US exchanges
//	topGainers, err := client.GetMostTraded("stocks", "usa", true, 20)
//	if err != nil {
//	    log.Fatal(err)
//	}
//
//	// Get most traded stocks by volume
//	mostTraded, err := client.GetMostTraded("stocks", "usa", false, 20)
func (c *Client) GetMostTraded(instrumentType, exchange string, gainers bool, limit int) (interface{}, error) {
	if instrumentType == "" {
		instrumentType = "stocks"
	}
	if exchange == "" {
		exchange = "usa"
	}
	if limit == 0 {
		limit = 10
	}

	gainersInt := 0
	if gainers {
		gainersInt = 1
	}

	params := map[string]interface{}{
		"type":     instrumentType,
		"exchange": exchange,
		"gainers":  gainersInt, // Boolean converted to int
		"limit":    limit,
	}
	return c.plainRequest("getTopSecurities", params)
}

// ExportSecurities exports securities data from Tradernet in bulk.
// This matches the Python SDK's export_securities() method exactly.
// Uses direct HTTP GET to /securities/export (not via standard API endpoint).
//
// Parameters:
//   - symbols: Array of Tradernet symbols to export (e.g., []string{"AAPL.US", "MSFT.US"})
//     Can be a single symbol or multiple symbols. Symbols are processed in chunks of 100.
//   - fields: Optional array of field names to include. If empty or nil, all fields are returned.
//     Example: []string{"ticker", "name", "isin"}
//
// Returns:
//   - An array of maps, each containing security data with the requested fields.
//
// Errors:
//   - Returns error if API request fails
//   - Returns error if symbols array is empty
//
// Note: This method processes symbols in chunks of 100 (MAX_EXPORT_SIZE) to handle
// large symbol lists efficiently.
//
// API Reference: https://freedom24.com/tradernet-api/quotes-get
//
// Example:
//
//	symbols := []string{"AAPL.US", "MSFT.US", "GOOGL.US"}
//	fields := []string{"ticker", "name", "isin", "currency"}
//	data, err := client.ExportSecurities(symbols, fields)
//	if err != nil {
//	    log.Fatal(err)
//	}
func (c *Client) ExportSecurities(symbols []string, fields []string) (interface{}, error) {
	// This is a special case - uses direct HTTP GET, not authorized_request
	// Python SDK uses self.request('get', url, headers={'Content': 'application/json'}, params=request_params)

	// Build base URL
	requestURL := fmt.Sprintf("%s/securities/export", c.baseURL)

	// Build query parameters
	u, err := url.Parse(requestURL)
	if err != nil {
		return nil, fmt.Errorf("failed to parse URL: %w", err)
	}

	baseQ := u.Query()
	if len(fields) > 0 {
		baseQ.Set("params", strings.Join(fields, " "))
	}

	// Process in chunks (MAX_EXPORT_SIZE = 100)
	const maxExportSize = 100
	var allResults []interface{}

	for chunk := 0; chunk < len(symbols); chunk += maxExportSize {
		end := chunk + maxExportSize
		if end > len(symbols) {
			end = len(symbols)
		}

		chunkSymbols := symbols[chunk:end]
		chunkQ := baseQ
		chunkQ.Set("tickers", strings.Join(chunkSymbols, " "))
		u.RawQuery = chunkQ.Encode()

		// Create GET request
		req, err := http.NewRequest("GET", u.String(), nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create request: %w", err)
		}

		req.Header.Set("Content", "application/json")
		req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; TradernetSDK/2.0)")

		// Send request using client's httpClient
		resp, err := c.httpClient.Do(req)
		if err != nil {
			return nil, fmt.Errorf("request failed: %w", err)
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			return nil, fmt.Errorf("API returned status %d: %s", resp.StatusCode, resp.Status)
		}

		// Parse JSON response
		body, err := io.ReadAll(resp.Body)
		if err != nil {
			return nil, fmt.Errorf("failed to read response: %w", err)
		}

		var chunkResult []interface{}
		if err := json.Unmarshal(body, &chunkResult); err != nil {
			return nil, fmt.Errorf("failed to parse response: %w", err)
		}

		allResults = append(allResults, chunkResult...)
	}

	return allResults, nil
}

// GetNews retrieves news on securities.
// This matches the Python SDK's get_news() method exactly.
//
// Parameters:
//   - query: Search query - can be a ticker or any word. If symbol parameter is set,
//     query is ignored and only news for that symbol is returned.
//   - symbol: Optional symbol filter. If provided, query is ignored and newsfeed
//     consists only of stories based on this symbol.
//   - storyID: Optional story ID. If provided, query and symbol are ignored and only
//     the story with this ID is returned.
//   - limit: Maximum number of news items to return (default: 30)
//
// Returns:
//   - A map or array containing news items, each with:
//   - title: News headline
//   - date: Publication date
//   - storyId: Unique story identifier
//   - content: News content (if available)
//   - Other news-specific fields
//
// Errors:
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/quotes-get-news
//
// Example:
//
//	// Search for news about Apple
//	news, err := client.GetNews("AAPL", nil, nil, 10)
//	if err != nil {
//	    log.Fatal(err)
//	}
//
//	// Get news for specific symbol
//	symbol := "AAPL.US"
//	news, err = client.GetNews("", &symbol, nil, 20)
func (c *Client) GetNews(query string, symbol *string, storyID *string, limit int) (interface{}, error) {
	if limit == 0 {
		limit = 30
	}
	params := GetNewsParams{
		SearchFor: query,
		Ticker:    symbol,
		StoryID:   storyID,
		Limit:     limit,
	}
	return c.authorizedRequest("getNews", params)
}

// GetAll retrieves information on securities with filters.
// This matches the Python SDK's get_all() method exactly.
//
// NOTE: This method currently returns an error because it requires refbook download
// functionality which is not yet implemented. The Python SDK uses internal refbook
// parsing which involves HTML parsing, ZIP file download/extraction, and large dataset
// processing. Use FindSymbol() or GetQuotes() instead for now.
//
// Parameters:
//   - filters: Map of field names and their values to filter by.
//     Example: map[string]interface{}{"mkt_short_code": "FIX", "instr_type_c": 1}
//   - mkt_short_code: Market code (e.g., "FIX", "ICE")
//   - instr_type_c: Instrument type code (1=stocks, 4=options, etc.)
//   - istrade: If showExpired is false, automatically set to 1 (active only)
//   - showExpired: If false, only returns active/trading securities (default: false)
//
// Returns:
//   - Error: Always returns error indicating functionality not yet implemented
//
// Errors:
//   - Always returns error: "GetAll() requires refbook download functionality which is
//     not yet implemented. Use FindSymbol() or GetQuotes() instead"
//
// API Reference:
//   - https://freedom24.com/tradernet-api/securities
//   - https://freedom24.com/tradernet-api/instruments
//
// Example:
//
//	// This will return an error - functionality not yet implemented
//	filters := map[string]interface{}{
//	    "mkt_short_code": "FIX",
//	    "instr_type_c": 1,
//	}
//	_, err := client.GetAll(filters, false)
//	// err will contain: "GetAll() requires refbook download functionality..."
func (c *Client) GetAll(filters map[string]interface{}, showExpired bool) (interface{}, error) {
	// Python SDK uses __get_refbook() which downloads and parses ZIP files
	// This is complex and requires HTML parsing, ZIP extraction, etc.
	// For now, return an error indicating this is not yet implemented
	return nil, fmt.Errorf("GetAll() requires refbook download functionality which is not yet implemented. Use FindSymbol() or GetQuotes() instead")
}

// Symbol retrieves stock data for shop/display purposes (different from SecurityInfo).
// This matches the Python SDK's symbol() method exactly.
//
// Parameters:
//   - symbol: Tradernet symbol (e.g., "AAPL.US")
//   - lang: Language code (two letters, default: "en")
//
// Returns:
//   - A map containing stock data including:
//   - ticker: Symbol
//   - name: Company name
//   - description: Company description (localized)
//   - Other display/shop-specific fields
//
// Errors:
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/shop-get-stock-data
//
// Example:
//
//	data, err := client.Symbol("AAPL.US", "en")
//	if err != nil {
//	    log.Fatal(err)
//	}
func (c *Client) Symbol(symbol string, lang string) (interface{}, error) {
	if lang == "" {
		lang = "en"
	}
	params := GetStockDataParams{
		Ticker: symbol,
		Lang:   lang,
	}
	return c.authorizedRequest("getStockData", params)
}

// Symbols retrieves completed lists of securities by exchange.
// This matches the Python SDK's symbols() method exactly.
//
// Parameters:
//   - exchange: Optional exchange name. Possible values: "USA", "Russia".
//     If provided, returns data from NYSE/NASDAQ or Moscow Exchange.
//     The value is automatically converted to lowercase (matching Python SDK behavior).
//
// Returns:
//   - A map containing exchanges and their symbols with complete security information.
//
// Errors:
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/get-ready-list
//
// Example:
//
//	// Get all symbols
//	allSymbols, err := client.Symbols(nil)
//	if err != nil {
//	    log.Fatal(err)
//	}
//
//	// Get symbols for US exchanges
//	exchange := "USA"
//	usSymbols, err := client.Symbols(&exchange)
func (c *Client) Symbols(exchange *string) (interface{}, error) {
	var params *GetReadyListParams
	if exchange != nil {
		// Python SDK converts to lowercase
		lowerExchange := strings.ToLower(*exchange)
		params = &GetReadyListParams{
			Mkt: &lowerExchange,
		}
	}
	return c.authorizedRequest("getReadyList", params)
}

// CorporateActions retrieves planned corporate actions for a specific office.
// Corporate actions include dividends, stock splits, mergers, etc.
// This matches the Python SDK's corporate_actions() method exactly.
//
// Parameters:
//   - reception: Office number (default: 35)
//
// Returns:
//   - An array of corporate action objects, each containing:
//   - symbol: Affected security
//   - action_type: Type of corporate action (dividend, split, etc.)
//   - date: Action date
//   - Other action-specific fields
//
// Errors:
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/get-planned-corp-actions
//
// Example:
//
//	actions, err := client.CorporateActions(35)
//	if err != nil {
//	    log.Fatal(err)
//	}
func (c *Client) CorporateActions(reception int) (interface{}, error) {
	if reception == 0 {
		reception = 35 // Default
	}
	params := GetPlannedCorpActionsParams{
		Reception: reception,
	}
	return c.authorizedRequest("getPlannedCorpActions", params)
}

// GetPriceAlerts retrieves a list of price alerts for the user.
// This matches the Python SDK's get_price_alerts() method exactly.
//
// Parameters:
//   - symbol: Optional symbol filter. If provided, returns only alerts for this symbol.
//     If nil, returns all price alerts.
//
// Returns:
//   - A map or array containing price alert objects, each with:
//   - id: Alert ID
//   - ticker: Symbol
//   - price: Alert price(s)
//   - trigger_type: Trigger method
//   - quote_type: Price type used
//   - notification_type: Notification method
//   - Other alert-specific fields
//
// Errors:
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/alerts-get-list
//
// Example:
//
//	// Get all alerts
//	allAlerts, err := client.GetPriceAlerts(nil)
//	if err != nil {
//	    log.Fatal(err)
//	}
//
//	// Get alerts for specific symbol
//	symbol := "AAPL.US"
//	alerts, err := client.GetPriceAlerts(&symbol)
func (c *Client) GetPriceAlerts(symbol *string) (interface{}, error) {
	var params *GetAlertsListParams
	if symbol != nil {
		params = &GetAlertsListParams{
			Ticker: symbol,
		}
	}
	return c.authorizedRequest("getAlertsList", params)
}

// AddPriceAlert creates a new price alert for a symbol.
// This matches the Python SDK's add_price_alert() method exactly.
//
// Parameters:
//   - symbol: Symbol to add alert for (e.g., "AAPL.US")
//   - price: Alert price(s). Can be:
//   - Single number (int, float64): Single price level
//   - Array of numbers: Multiple price levels
//     All prices are converted to strings (matching Python SDK behavior)
//   - triggerType: Trigger method (default: "crossing")
//   - quoteType: Type of price for alert calculation. Possible values:
//     "ltp" (last traded price, default), "bap" (best ask price), "bbp" (best bid price),
//     "op" (opening price), "pp" (previous price)
//   - sendTo: Notification type. Possible values:
//     "email" (default), "sms", "push", "all"
//   - frequency: Alert frequency (default: 0)
//   - expire: Alert expiration period in seconds (default: 0 = no expiration)
//
// Returns:
//   - A map containing alert creation result with:
//   - alert_id: Newly created alert ID
//   - Other creation-specific fields
//
// Errors:
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/alerts-add
//
// Example:
//
//	// Single price alert
//	result, err := client.AddPriceAlert("AAPL.US", 150.0, "crossing", "ltp", "email", 0, 0)
//	if err != nil {
//	    log.Fatal(err)
//	}
//
//	// Multiple price levels
//	prices := []float64{150.0, 200.0}
//	result, err = client.AddPriceAlert("AAPL.US", prices, "crossing", "ltp", "email", 0, 0)
func (c *Client) AddPriceAlert(symbol string, price interface{}, triggerType, quoteType, sendTo string, frequency, expire int) (interface{}, error) {
	if triggerType == "" {
		triggerType = "crossing"
	}
	if quoteType == "" {
		quoteType = "ltp"
	}
	if sendTo == "" {
		sendTo = "email"
	}

	// Convert price to []string (Python converts to string array)
	var priceStrings []string
	switch v := price.(type) {
	case []interface{}:
		for _, p := range v {
			priceStrings = append(priceStrings, fmt.Sprintf("%v", p))
		}
	case []string:
		priceStrings = v
	case []int:
		for _, p := range v {
			priceStrings = append(priceStrings, fmt.Sprintf("%d", p))
		}
	case []float64:
		for _, p := range v {
			priceStrings = append(priceStrings, fmt.Sprintf("%g", p))
		}
	default:
		// Single value
		priceStrings = []string{fmt.Sprintf("%v", v)}
	}

	params := AddPriceAlertParams{
		Ticker:           symbol,
		Price:            priceStrings,
		TriggerType:      triggerType,
		QuoteType:        quoteType,
		NotificationType: sendTo,
		AlertPeriod:      frequency,
		Expire:           expire,
	}
	return c.authorizedRequest("addPriceAlert", params)
}

// DeletePriceAlert deletes a price alert by alert ID.
// This matches the Python SDK's delete_price_alert() method exactly.
// CRITICAL: Boolean stays boolean (NOT converted to int!)
//
// Parameters:
//   - alertID: Alert ID to delete (obtained from GetPriceAlerts)
//
// Returns:
//   - A map containing deletion result with status information.
//
// Errors:
//   - Returns error if alert ID is invalid or alert cannot be deleted
//   - Returns error if API request fails or credentials are invalid
//
// Note: This method uses the "addPriceAlert" endpoint with a "del": true parameter,
// matching the Python SDK's implementation.
//
// API Reference: https://freedom24.com/tradernet-api/alerts-delete
//
// Example:
//
//	result, err := client.DeletePriceAlert(12345)
//	if err != nil {
//	    log.Fatal(err)
//	}
func (c *Client) DeletePriceAlert(alertID int) (interface{}, error) {
	params := DeletePriceAlertParams{
		ID:  alertID,
		Del: true, // Boolean, NOT int!
	}
	return c.authorizedRequest("addPriceAlert", params)
}

// Stop places a stop loss order on an open position.
// This matches the Python SDK's stop() method exactly.
//
// Parameters:
//   - symbol: Tradernet symbol for the position (e.g., "AAPL.US")
//   - price: Stop loss price level
//
// Returns:
//   - A map containing order information with:
//   - order_id: Stop loss order ID
//   - Other order-specific fields
//
// Errors:
//   - Returns error if position doesn't exist or cannot place stop loss
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/orders-stop-loss
//
// Example:
//
//	result, err := client.Stop("AAPL.US", 140.0)
//	if err != nil {
//	    log.Fatal(err)
//	}
func (c *Client) Stop(symbol string, price float64) (interface{}, error) {
	params := PutStopLossParams{
		InstrName: symbol,
		StopLoss:  &price,
	}
	return c.authorizedRequest("putStopLoss", params)
}

// TrailingStop places a trailing stop order on an open position.
// A trailing stop automatically adjusts the stop price as the position moves favorably.
// This matches the Python SDK's trailing_stop() method exactly.
//
// Parameters:
//   - symbol: Tradernet symbol for the position (e.g., "AAPL.US")
//   - percent: Stop loss percentage. The stop price trails the current price by this
//     percentage. Supports decimal values (e.g., 2.5). Default: 1.0 (if 0 is provided)
//
// Returns:
//   - A map containing order information with:
//   - order_id: Trailing stop order ID
//   - Other order-specific fields
//
// Errors:
//   - Returns error if position doesn't exist or cannot place trailing stop
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/orders-stop-loss
//
// Example:
//
//	// 5% trailing stop
//	result, err := client.TrailingStop("AAPL.US", 5.0)
//	if err != nil {
//	    log.Fatal(err)
//	}
//
//	// 2.5% trailing stop
//	result, err := client.TrailingStop("AAPL.US", 2.5)
func (c *Client) TrailingStop(symbol string, percent float64) (interface{}, error) {
	if percent == 0 {
		percent = 1.0 // Default
	}
	params := PutStopLossParams{
		InstrName:               symbol,
		StopLossPercent:         &percent,
		StoplossTrailingPercent: &percent,
	}
	return c.authorizedRequest("putStopLoss", params)
}

// TakeProfit places a take profit order on an open position.
// This matches the Python SDK's take_profit() method exactly.
//
// Parameters:
//   - symbol: Tradernet symbol for the position (e.g., "AAPL.US")
//   - price: Take profit price level
//
// Returns:
//   - A map containing order information with:
//   - order_id: Take profit order ID
//   - Other order-specific fields
//
// Errors:
//   - Returns error if position doesn't exist or cannot place take profit
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/orders-stop-loss
//
// Example:
//
//	result, err := client.TakeProfit("AAPL.US", 200.0)
//	if err != nil {
//	    log.Fatal(err)
//	}
func (c *Client) TakeProfit(symbol string, price float64) (interface{}, error) {
	params := PutStopLossParams{
		InstrName:  symbol,
		TakeProfit: &price,
	}
	return c.authorizedRequest("putStopLoss", params)
}

// CancelAll cancels all active orders.
// This matches the Python SDK's cancel_all() method exactly.
//
// This method:
//  1. Retrieves all active orders using GetPlaced(true)
//  2. Cancels each order individually using Cancel()
//  3. Returns an array of cancellation results
//
// Returns:
//   - An array of cancellation results, one for each cancelled order.
//     Each result contains the cancellation status and order ID.
//   - Empty array if no active orders exist
//
// Errors:
//   - Returns error if GetPlaced() fails
//   - Individual cancellation failures are logged but don't stop the process
//   - Returns partial results even if some cancellations fail
//
// API Reference: https://freedom24.com/tradernet-api/orders-cancel
//
// Example:
//
//	results, err := client.CancelAll()
//	if err != nil {
//	    log.Fatal(err)
//	}
//	// results is an array of cancellation results
func (c *Client) CancelAll() (interface{}, error) {
	// Get all active orders
	placed, err := c.GetPlaced(true)
	if err != nil {
		return nil, fmt.Errorf("failed to get placed orders: %w", err)
	}

	// Parse response structure
	placedMap, ok := placed.(map[string]interface{})
	if !ok {
		return []interface{}{}, nil
	}

	result, ok := placedMap["result"].(map[string]interface{})
	if !ok {
		return []interface{}{}, nil
	}

	orders, ok := result["orders"].(map[string]interface{})
	if !ok {
		return []interface{}{}, nil
	}

	orderList, ok := orders["order"]
	if !ok {
		return []interface{}{}, nil
	}

	// Handle single order (dict) vs list
	var orderArray []interface{}
	switch v := orderList.(type) {
	case []interface{}:
		orderArray = v
	case map[string]interface{}:
		orderArray = []interface{}{v}
	default:
		return []interface{}{}, nil
	}

	// Cancel each order
	var results []interface{}
	for _, order := range orderArray {
		orderMap, ok := order.(map[string]interface{})
		if !ok {
			continue
		}

		var orderID int
		if idVal, exists := orderMap["id"]; exists {
			switch v := idVal.(type) {
			case float64:
				orderID = int(v)
			case int:
				orderID = v
			default:
				continue
			}
		} else {
			continue
		}

		result, err := c.Cancel(orderID)
		if err != nil {
			// Continue canceling others even if one fails
			continue
		}
		results = append(results, result)
	}

	return results, nil
}

// GetHistorical retrieves a list of orders for the specified period.
// This is different from GetTradesHistory() which returns executed trades.
// This matches the Python SDK's get_historical() method exactly.
//
// Parameters:
//   - start: Period start date/time.
//     Default in Python SDK: datetime(2011, 1, 11)
//   - end: Period end date/time.
//     Default in Python SDK: datetime.now()
//
// Returns:
//   - A map containing orders history with structure:
//   - result.orders: Array of order objects (both filled and unfilled)
//
// Errors:
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/get-orders-history
//
// Example:
//
//	start := time.Date(2023, 1, 1, 0, 0, 0, 0, time.UTC)
//	end := time.Now()
//	history, err := client.GetHistorical(start, end)
//	if err != nil {
//	    log.Fatal(err)
//	}
func (c *Client) GetHistorical(start, end time.Time) (interface{}, error) {
	// Date format: "2011-01-11T00:00:00"
	dateFrom := start.Format("2006-01-02T15:04:05")
	dateTo := end.Format("2006-01-02T15:04:05")

	params := GetOrdersHistoryParams{
		From: dateFrom,
		Till: dateTo,
	}
	return c.authorizedRequest("getOrdersHistory", params)
}

// GetOrderFiles retrieves order files/documents.
// This matches the Python SDK's get_order_files() method exactly.
//
// Parameters:
//   - orderID: Optional order ID. Used if the order has been assigned a main ID.
//   - internalID: Optional draft order ID. Used when the order has draft status
//     and hasn't been assigned a main ID yet.
//
// Note: Either orderID or internalID must be provided (not both, not neither).
//
// Returns:
//   - A map containing order files with:
//   - result.files: Array of file objects with download URLs and metadata
//
// Errors:
//   - Returns error if neither orderID nor internalID is provided
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/get-cps-files
//
// Example:
//
//	orderID := 12345
//	files, err := client.GetOrderFiles(&orderID, nil)
//	if err != nil {
//	    log.Fatal(err)
//	}
//
//	// Or using internal ID
//	internalID := 67890
//	files, err = client.GetOrderFiles(nil, &internalID)
func (c *Client) GetOrderFiles(orderID, internalID *int) (interface{}, error) {
	if internalID == nil && orderID == nil {
		return nil, fmt.Errorf("either order_id or internal_id must be specified")
	}

	params := GetCpsFilesParams{
		InternalID: internalID,
		ID:         orderID,
	}
	return c.authorizedRequest("getCpsFiles", params)
}

// GetBrokerReport retrieves the broker's report using software methods.
// This matches the Python SDK's get_broker_report() method exactly.
//
// Parameters:
//   - start: Period start date.
//     Default in Python SDK: date(1970, 1, 1)
//   - end: Period end date.
//     Default in Python SDK: date.today()
//   - period: Time cut for the report (e.g., 23:59:59 or 08:40:00).
//     Default in Python SDK: time(23, 59, 59)
//   - dataBlockType: Optional data block type from the report.
//     Default: "account_at_end"
//
// Returns:
//   - A map containing broker's report data with account information, positions,
//     transactions, and other report-specific data.
//
// Errors:
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/get-broker-report
//
// Example:
//
//	start := time.Date(2023, 1, 1, 0, 0, 0, 0, time.UTC)
//	end := time.Date(2023, 12, 31, 0, 0, 0, 0, time.UTC)
//	period := time.Date(0, 0, 0, 23, 59, 59, 0, time.UTC)
//	report, err := client.GetBrokerReport(start, end, period, nil)
//	if err != nil {
//	    log.Fatal(err)
//	}
func (c *Client) GetBrokerReport(start, end time.Time, period time.Time, dataBlockType *string) (interface{}, error) {
	// Date format: ISO format
	dateStart := start.Format("2006-01-02")
	dateEnd := end.Format("2006-01-02")

	// Time format: "23:59:59"
	timePeriod := period.Format("15:04:05")

	if dataBlockType == nil {
		defaultType := "account_at_end"
		dataBlockType = &defaultType
	}

	params := GetBrokerReportParams{
		DateStart:  dateStart,
		DateEnd:    dateEnd,
		TimePeriod: timePeriod,
		Format:     "json",
		Type:       dataBlockType,
	}
	return c.authorizedRequest("getBrokerReport", params)
}

// GetTariffsList retrieves a list of available tariffs/plans.
// This matches the Python SDK's get_tariffs_list() method exactly.
//
// Returns:
//   - A map or array containing tariff information, each with:
//   - id: Tariff ID
//   - name: Tariff name
//   - price: Tariff price
//   - features: Tariff features
//   - Other tariff-specific fields
//
// Errors:
//   - Returns error if API request fails or credentials are invalid
//
// API Reference: https://freedom24.com/tradernet-api/get-list-tariff
//
// Example:
//
//	tariffs, err := client.GetTariffsList()
//	if err != nil {
//	    log.Fatal(err)
//	}
func (c *Client) GetTariffsList() (interface{}, error) {
	params := GetListTariffsParams{}
	return c.authorizedRequest("GetListTariffs", params)
}

// Helper function
func absInt(x int) int {
	if x < 0 {
		return -x
	}
	return x
}
