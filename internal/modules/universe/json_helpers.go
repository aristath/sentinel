package universe

import (
	"encoding/json"
	"fmt"
)

// SecurityData represents structured data in JSON column
type SecurityData struct {
	Name               string                 `json:"name"`
	ProductType        string                 `json:"product_type"`
	Industry           string                 `json:"industry"`
	Geography          string                 `json:"geography"`
	FullExchangeName   string                 `json:"fullExchangeName"`
	MarketCode         string                 `json:"market_code"`
	Currency           string                 `json:"currency"`
	MinLot             int                    `json:"min_lot"`
	MinPortfolioTarget float64                `json:"min_portfolio_target"`
	MaxPortfolioTarget float64                `json:"max_portfolio_target"`
	TradernetRaw       map[string]interface{} `json:"tradernet_raw"`
}

// ParseSecurityJSON parses JSON string to SecurityData
func ParseSecurityJSON(jsonStr string) (*SecurityData, error) {
	if jsonStr == "" {
		return nil, fmt.Errorf("empty JSON string")
	}

	// Handle "null" JSON string
	if jsonStr == "null" {
		return nil, fmt.Errorf("null JSON string")
	}

	var data SecurityData
	if err := json.Unmarshal([]byte(jsonStr), &data); err != nil {
		return nil, fmt.Errorf("failed to parse JSON: %w", err)
	}

	// Validate critical fields are present
	// Note: Name is always required; Currency may be empty for indices or test data
	if data.Name == "" {
		return nil, fmt.Errorf("security name is required in JSON data")
	}

	return &data, nil
}

// SerializeSecurityJSON converts SecurityData to JSON string
func SerializeSecurityJSON(data *SecurityData) (string, error) {
	jsonBytes, err := json.Marshal(data)
	if err != nil {
		return "", fmt.Errorf("failed to serialize JSON: %w", err)
	}
	return string(jsonBytes), nil
}

// SecurityFromJSON creates Security struct from JSON data
func SecurityFromJSON(isin, symbol, jsonData string, lastSynced *int64) (*Security, error) {
	data, err := ParseSecurityJSON(jsonData)
	if err != nil {
		return nil, err
	}

	return &Security{
		ISIN:               isin,
		Symbol:             symbol,
		Name:               data.Name,
		ProductType:        data.ProductType,
		Industry:           data.Industry,
		Geography:          data.Geography,
		FullExchangeName:   data.FullExchangeName,
		MarketCode:         data.MarketCode,
		Currency:           data.Currency,
		MinLot:             data.MinLot,
		MinPortfolioTarget: data.MinPortfolioTarget,
		MaxPortfolioTarget: data.MaxPortfolioTarget,
		LastSynced:         lastSynced,
	}, nil
}

// SecurityToJSON converts Security struct to JSON string
func SecurityToJSON(security *Security) (string, error) {
	data := SecurityData{
		Name:               security.Name,
		ProductType:        security.ProductType,
		Industry:           security.Industry,
		Geography:          security.Geography,
		FullExchangeName:   security.FullExchangeName,
		MarketCode:         security.MarketCode,
		Currency:           security.Currency,
		MinLot:             security.MinLot,
		MinPortfolioTarget: security.MinPortfolioTarget,
		MaxPortfolioTarget: security.MaxPortfolioTarget,
		TradernetRaw:       make(map[string]interface{}),
	}

	return SerializeSecurityJSON(&data)
}
