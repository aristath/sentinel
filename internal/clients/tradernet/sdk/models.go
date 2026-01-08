package sdk

// GetAllUserTexInfoParams represents parameters for GetAllUserTexInfo command
// This command requires no parameters, but we use a struct for consistency
type GetAllUserTexInfoParams struct {
	// Empty - no params needed
}

// GetPositionJSONParams represents parameters for getPositionJSON command
// This command requires no parameters
type GetPositionJSONParams struct {
	// Empty - no params needed
}

// PutTradeOrderParams represents parameters for putTradeOrder command
// CRITICAL: Field order MUST match Python's dict insertion order exactly!
// Python order: 'instr_name', 'action_id', 'order_type_id', 'qty', 'limit_price', 'stop_price', 'expiration_id', 'user_order_id'
type PutTradeOrderParams struct {
	InstrName    string   `json:"instr_name"`              // Field 1
	ActionID     int      `json:"action_id"`               // Field 2
	OrderTypeID  int      `json:"order_type_id"`           // Field 3
	Qty          int      `json:"qty"`                     // Field 4
	LimitPrice   *float64 `json:"limit_price,omitempty"`   // Field 5 - Nullable for market orders
	StopPrice    *float64 `json:"stop_price,omitempty"`    // Field 6 - Required for stop orders (types 3-6)
	ExpirationID int      `json:"expiration_id"`           // Field 7
	UserOrderID  *int     `json:"user_order_id,omitempty"` // Field 8
}

// GetNotifyOrderJSONParams represents parameters for getNotifyOrderJSON command
// CRITICAL: Field order MUST match Python's dict insertion order exactly!
type GetNotifyOrderJSONParams struct {
	ActiveOnly int `json:"active_only"` // Boolean converted to int: True=1, False=0
}

// GetTradesHistoryParams represents parameters for getTradesHistory command
// CRITICAL: Field order MUST match Python's dict insertion order exactly!
// Python order: 'beginDate', 'endDate', 'tradeId', 'max', 'nt_ticker', 'curr', 'reception'
type GetTradesHistoryParams struct {
	BeginDate string  `json:"beginDate"`           // Field 1 - ISO format YYYY-MM-DD
	EndDate   string  `json:"endDate"`             // Field 2 - ISO format YYYY-MM-DD
	TradeID   *int    `json:"tradeId,omitempty"`   // Field 3 - optional
	Max       *int    `json:"max,omitempty"`       // Field 4 - optional
	NtTicker  *string `json:"nt_ticker,omitempty"` // Field 5 - optional
	Curr      *string `json:"curr,omitempty"`      // Field 6 - optional
	Reception *int    `json:"reception,omitempty"` // Field 7 - optional (office/reception filter)
}

// GetStockQuotesJSONParams represents parameters for getStockQuotesJSON command
// CRITICAL: Field order MUST match Python's dict insertion order exactly!
type GetStockQuotesJSONParams struct {
	Tickers string `json:"tickers"` // Comma-separated string: "AAPL.US,MSFT.US"
}

// GetHlocParams represents parameters for getHloc command
// CRITICAL: Field order MUST match Python's dict insertion order exactly!
// Python order: 'id', 'count', 'timeframe', 'date_from', 'date_to', 'intervalMode'
type GetHlocParams struct {
	ID           string `json:"id"`           // Field 1 - Symbol
	Count        int    `json:"count"`        // Field 2 - -1 for all
	Timeframe    int    `json:"timeframe"`    // Field 3 - Minutes (seconds / 60)
	DateFrom     string `json:"date_from"`    // Field 4 - Format: "01.01.2020 00:00"
	DateTo       string `json:"date_to"`      // Field 5 - Format: "01.01.2020 00:00"
	IntervalMode string `json:"intervalMode"` // Field 6 - "OpenRay"
}

// GetSecurityInfoParams represents parameters for getSecurityInfo command
// CRITICAL: Field order MUST match Python's dict insertion order exactly!
// CRITICAL: Boolean stays boolean (NOT converted to int!)
type GetSecurityInfoParams struct {
	Ticker string `json:"ticker"` // Field 1
	Sup    bool   `json:"sup"`    // Field 2 - Boolean (NOT int!)
}

// GetClientCpsHistoryParams represents parameters for getClientCpsHistory command
// CRITICAL: Field order MUST match Python's dict insertion order exactly!
// Python order: 'date_from', 'date_to', 'cpsDocId', 'id', 'limit', 'offset', 'cps_status'
type GetClientCpsHistoryParams struct {
	DateFrom string `json:"date_from"` // Field 1 - Format: "2011-01-11T00:00:00"
	DateTo   string `json:"date_to"`   // Field 2 - Format: "2024-01-01T00:00:00"
	// Optional fields (omitempty)
	CpsDocID  *int `json:"cpsDocId,omitempty"`   // Field 3
	ID        *int `json:"id,omitempty"`         // Field 4
	Limit     *int `json:"limit,omitempty"`      // Field 5
	Offset    *int `json:"offset,omitempty"`     // Field 6
	CpsStatus *int `json:"cps_status,omitempty"` // Field 7
}

// RegisterNewUserParams represents parameters for registerNewUser command (plain_request)
// Python order: 'login', 'pwd', 'reception', 'phone', 'lastname', 'firstname', 'tariff_id', 'utm_campaign'
type RegisterNewUserParams struct {
	Login       string  `json:"login"`                  // Field 1
	Pwd         *string `json:"pwd,omitempty"`          // Field 2 - optional
	Reception   string  `json:"reception"`              // Field 3 - converted to string
	Phone       string  `json:"phone"`                  // Field 4
	Lastname    string  `json:"lastname"`               // Field 5
	Firstname   string  `json:"firstname"`              // Field 6
	TariffID    *int    `json:"tariff_id,omitempty"`    // Field 7 - optional
	UtmCampaign *string `json:"utm_campaign,omitempty"` // Field 8 - optional
}

// CheckStepParams represents parameters for checkStep command
// Python order: 'step', 'office'
type CheckStepParams struct {
	Step   int    `json:"step"`   // Field 1
	Office string `json:"office"` // Field 2
}

// GetAnketaFieldsParams represents parameters for getAnketaFields command
type GetAnketaFieldsParams struct {
	AnketaForReception int `json:"anketa_for_reception"`
}

// GetOPQParams represents parameters for getOPQ command (no params)
type GetOPQParams struct {
	// Empty - no params needed
}

// GetMarketStatusParams represents parameters for getMarketStatus command
// Python order: 'market', 'mode' (optional)
type GetMarketStatusParams struct {
	Market string  `json:"market"`         // Field 1 - default: '*'
	Mode   *string `json:"mode,omitempty"` // Field 2 - optional
}

// GetOptionsByMktNameAndBaseAssetParams represents parameters for getOptionsByMktNameAndBaseAsset command
// Python order: 'base_contract_code', 'ltr'
type GetOptionsByMktNameAndBaseAssetParams struct {
	BaseContractCode string `json:"base_contract_code"` // Field 1
	Ltr              string `json:"ltr"`                // Field 2
}

// GetTopSecuritiesParams represents parameters for getTopSecurities command (plain_request)
// Python order: 'type', 'exchange', 'gainers', 'limit'
type GetTopSecuritiesParams struct {
	Type     string `json:"type"`     // Field 1 - default: 'stocks'
	Exchange string `json:"exchange"` // Field 2 - default: 'usa'
	Gainers  int    `json:"gainers"`  // Field 3 - boolean converted to int
	Limit    int    `json:"limit"`    // Field 4 - default: 10
}

// GetNewsParams represents parameters for getNews command
// Python order: 'searchFor', 'ticker', 'storyId', 'limit'
type GetNewsParams struct {
	SearchFor string  `json:"searchFor"`         // Field 1
	Ticker    *string `json:"ticker,omitempty"`  // Field 2 - optional
	StoryID   *string `json:"storyId,omitempty"` // Field 3 - optional
	Limit     int     `json:"limit"`             // Field 4 - default: 30
}

// GetStockDataParams represents parameters for getStockData command
// Python order: 'ticker', 'lang'
type GetStockDataParams struct {
	Ticker string `json:"ticker"` // Field 1
	Lang   string `json:"lang"`   // Field 2 - default: 'en'
}

// GetReadyListParams represents parameters for getReadyList command
// Python order: 'mkt' (optional)
type GetReadyListParams struct {
	Mkt *string `json:"mkt,omitempty"` // Optional - converted to lowercase if provided
}

// GetPlannedCorpActionsParams represents parameters for getPlannedCorpActions command
type GetPlannedCorpActionsParams struct {
	Reception int `json:"reception"` // default: 35
}

// GetAlertsListParams represents parameters for getAlertsList command
// Python order: 'ticker' (optional)
type GetAlertsListParams struct {
	Ticker *string `json:"ticker,omitempty"` // Optional
}

// AddPriceAlertParams represents parameters for addPriceAlert command
// Python order: 'ticker', 'price', 'trigger_type', 'quote_type', 'notification_type', 'alert_period', 'expire'
type AddPriceAlertParams struct {
	Ticker           string   `json:"ticker"`            // Field 1
	Price            []string `json:"price"`             // Field 2 - array of strings
	TriggerType      string   `json:"trigger_type"`      // Field 3 - default: 'crossing'
	QuoteType        string   `json:"quote_type"`        // Field 4 - default: 'ltp'
	NotificationType string   `json:"notification_type"` // Field 5 - default: 'email'
	AlertPeriod      int      `json:"alert_period"`      // Field 6 - default: 0
	Expire           int      `json:"expire"`            // Field 7 - default: 0
}

// DeletePriceAlertParams represents parameters for addPriceAlert with delete flag
// Python order: 'id', 'del'
type DeletePriceAlertParams struct {
	ID  int  `json:"id"`  // Field 1
	Del bool `json:"del"` // Field 2 - boolean stays boolean!
}

// PutStopLossParams represents parameters for putStopLoss command
// Used by stop(), trailing_stop(), and take_profit()
// Python order varies by method - we'll use separate structs for clarity
type PutStopLossParams struct {
	InstrName               string   `json:"instr_name"`                          // Field 1 - always present
	StopLoss                *float64 `json:"stop_loss,omitempty"`                 // Field 2 - for stop()
	StopLossPercent         *float64 `json:"stop_loss_percent,omitempty"`         // Field 3 - for trailing_stop() - supports decimals
	StoplossTrailingPercent *float64 `json:"stoploss_trailing_percent,omitempty"` // Field 4 - for trailing_stop() - supports decimals
	TakeProfit              *float64 `json:"take_profit,omitempty"`               // Field 5 - for take_profit()
}

// GetOrdersHistoryParams represents parameters for getOrdersHistory command
// Python order: 'from', 'till'
type GetOrdersHistoryParams struct {
	From string `json:"from"` // Field 1 - Format: "2011-01-11T00:00:00"
	Till string `json:"till"` // Field 2 - Format: "2024-01-01T00:00:00"
}

// GetCpsFilesParams represents parameters for getCpsFiles command
// Python order: 'internal_id' or 'id' (mutually exclusive)
type GetCpsFilesParams struct {
	InternalID *int `json:"internal_id,omitempty"` // Field 1 - optional
	ID         *int `json:"id,omitempty"`          // Field 2 - optional
}

// GetBrokerReportParams represents parameters for getBrokerReport command
// Python order: 'date_start', 'date_end', 'time_period', 'format', 'type'
type GetBrokerReportParams struct {
	DateStart  string  `json:"date_start"`     // Field 1 - ISO format
	DateEnd    string  `json:"date_end"`       // Field 2 - ISO format
	TimePeriod string  `json:"time_period"`    // Field 3 - Format: "23:59:59"
	Format     string  `json:"format"`         // Field 4 - default: 'json'
	Type       *string `json:"type,omitempty"` // Field 5 - optional, default: 'account_at_end'
}

// GetListTariffsParams represents parameters for GetListTariffs command (no params)
type GetListTariffsParams struct {
	// Empty - no params needed
}
