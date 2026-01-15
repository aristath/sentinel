package universe

import (
	"database/sql"
	"errors"
	"testing"
	"time"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

// Mock implementations for testing

type mockSecurityRepoForDeletion struct {
	security  *Security
	getErr    error
	deleteErr error
	deleted   bool
}

func (m *mockSecurityRepoForDeletion) GetByISIN(isin string) (*Security, error) {
	return m.security, m.getErr
}

func (m *mockSecurityRepoForDeletion) HardDelete(isin string) error {
	if m.deleteErr != nil {
		return m.deleteErr
	}
	m.deleted = true
	return nil
}

// Implement remaining SecurityRepositoryInterface methods as no-ops
func (m *mockSecurityRepoForDeletion) GetBySymbol(symbol string) (*Security, error) {
	return nil, nil
}
func (m *mockSecurityRepoForDeletion) GetByIdentifier(identifier string) (*Security, error) {
	return nil, nil
}
func (m *mockSecurityRepoForDeletion) GetAllActive() ([]Security, error)         { return nil, nil }
func (m *mockSecurityRepoForDeletion) GetDistinctExchanges() ([]string, error)   { return nil, nil }
func (m *mockSecurityRepoForDeletion) GetAllActiveTradable() ([]Security, error) { return nil, nil }
func (m *mockSecurityRepoForDeletion) GetAll() ([]Security, error)               { return nil, nil }
func (m *mockSecurityRepoForDeletion) Create(security Security) error            { return nil }
func (m *mockSecurityRepoForDeletion) Update(isin string, updates map[string]interface{}) error {
	return nil
}
func (m *mockSecurityRepoForDeletion) Delete(isin string) error { return nil }
func (m *mockSecurityRepoForDeletion) GetWithScores(portfolioDB *sql.DB) ([]SecurityWithScore, error) {
	return nil, nil
}
func (m *mockSecurityRepoForDeletion) SetTagsForSecurity(symbol string, tagIDs []string) error {
	return nil
}
func (m *mockSecurityRepoForDeletion) GetTagsForSecurity(symbol string) ([]string, error) {
	return nil, nil
}
func (m *mockSecurityRepoForDeletion) GetTagsWithUpdateTimes(symbol string) (map[string]time.Time, error) {
	return nil, nil
}
func (m *mockSecurityRepoForDeletion) UpdateSpecificTags(symbol string, tagIDs []string) error {
	return nil
}
func (m *mockSecurityRepoForDeletion) GetByTags(tagIDs []string) ([]Security, error) { return nil, nil }
func (m *mockSecurityRepoForDeletion) GetPositionsByTags(positionSymbols []string, tagIDs []string) ([]Security, error) {
	return nil, nil
}

type mockPositionRepoForDeletion struct {
	position  *portfolio.Position
	getErr    error
	deleteErr error
	deleted   bool
}

func (m *mockPositionRepoForDeletion) GetByISIN(isin string) (*portfolio.Position, error) {
	return m.position, m.getErr
}

func (m *mockPositionRepoForDeletion) Delete(isin string) error {
	if m.deleteErr != nil {
		return m.deleteErr
	}
	m.deleted = true
	return nil
}

// Implement remaining PositionRepositoryInterface methods as no-ops
func (m *mockPositionRepoForDeletion) GetAll() ([]portfolio.Position, error) { return nil, nil }
func (m *mockPositionRepoForDeletion) GetWithSecurityInfo() ([]portfolio.PositionWithSecurity, error) {
	return nil, nil
}
func (m *mockPositionRepoForDeletion) GetBySymbol(symbol string) (*portfolio.Position, error) {
	return nil, nil
}
func (m *mockPositionRepoForDeletion) GetByIdentifier(identifier string) (*portfolio.Position, error) {
	return nil, nil
}
func (m *mockPositionRepoForDeletion) GetCount() (int, error)          { return 0, nil }
func (m *mockPositionRepoForDeletion) GetTotalValue() (float64, error) { return 0, nil }
func (m *mockPositionRepoForDeletion) Upsert(position portfolio.Position) error {
	return nil
}
func (m *mockPositionRepoForDeletion) DeleteAll() error { return nil }
func (m *mockPositionRepoForDeletion) UpdatePrice(isin string, price float64, currencyRate float64) error {
	return nil
}
func (m *mockPositionRepoForDeletion) UpdateLastSoldAt(isin string) error { return nil }

type mockScoreRepoForDeletion struct {
	deleteErr error
	deleted   bool
}

func (m *mockScoreRepoForDeletion) Delete(isin string) error {
	if m.deleteErr != nil {
		return m.deleteErr
	}
	m.deleted = true
	return nil
}

// Implement remaining ScoreRepositoryInterface methods as no-ops
func (m *mockScoreRepoForDeletion) GetByISIN(isin string) (*SecurityScore, error) { return nil, nil }
func (m *mockScoreRepoForDeletion) GetBySymbol(symbol string) (*SecurityScore, error) {
	return nil, nil
}
func (m *mockScoreRepoForDeletion) GetByIdentifier(identifier string) (*SecurityScore, error) {
	return nil, nil
}
func (m *mockScoreRepoForDeletion) GetAll() ([]SecurityScore, error)          { return nil, nil }
func (m *mockScoreRepoForDeletion) GetTop(limit int) ([]SecurityScore, error) { return nil, nil }
func (m *mockScoreRepoForDeletion) Upsert(score SecurityScore) error          { return nil }
func (m *mockScoreRepoForDeletion) DeleteAll() error                          { return nil }

type mockHistoryDBForDeletion struct {
	deleteErr error
	deleted   bool
}

func (m *mockHistoryDBForDeletion) DeletePricesForSecurity(isin string) error {
	if m.deleteErr != nil {
		return m.deleteErr
	}
	m.deleted = true
	return nil
}

// Implement remaining HistoryDBInterface methods as no-ops
func (m *mockHistoryDBForDeletion) GetDailyPrices(isin string, limit int) ([]DailyPrice, error) {
	return nil, nil
}
func (m *mockHistoryDBForDeletion) GetRecentPrices(isin string, days int) ([]DailyPrice, error) {
	return nil, nil
}
func (m *mockHistoryDBForDeletion) GetMonthlyPrices(isin string, limit int) ([]MonthlyPrice, error) {
	return nil, nil
}
func (m *mockHistoryDBForDeletion) HasMonthlyData(isin string) (bool, error) { return false, nil }
func (m *mockHistoryDBForDeletion) SyncHistoricalPrices(isin string, prices []DailyPrice) error {
	return nil
}
func (m *mockHistoryDBForDeletion) UpsertExchangeRate(fromCurrency, toCurrency string, rate float64) error {
	return nil
}
func (m *mockHistoryDBForDeletion) GetLatestExchangeRate(fromCurrency, toCurrency string) (*ExchangeRate, error) {
	return nil, nil
}
func (m *mockHistoryDBForDeletion) InvalidateCache(isin string) {}
func (m *mockHistoryDBForDeletion) InvalidateAllCaches()        {}

// Removed mockDismissedFilterRepoForDeletion - dismissed filter functionality removed

type mockBrokerClientForDeletion struct {
	pendingOrders []domain.BrokerPendingOrder
	pendingErr    error
}

func (m *mockBrokerClientForDeletion) GetPendingOrders() ([]domain.BrokerPendingOrder, error) {
	return m.pendingOrders, m.pendingErr
}

// Implement remaining BrokerClient methods as no-ops
func (m *mockBrokerClientForDeletion) GetPortfolio() ([]domain.BrokerPosition, error) {
	return nil, nil
}
func (m *mockBrokerClientForDeletion) GetCashBalances() ([]domain.BrokerCashBalance, error) {
	return nil, nil
}
func (m *mockBrokerClientForDeletion) PlaceOrder(symbol, side string, quantity, limitPrice float64) (*domain.BrokerOrderResult, error) {
	return nil, nil
}
func (m *mockBrokerClientForDeletion) GetExecutedTrades(limit int) ([]domain.BrokerTrade, error) {
	return nil, nil
}
func (m *mockBrokerClientForDeletion) GetQuote(symbol string) (*domain.BrokerQuote, error) {
	return nil, nil
}
func (m *mockBrokerClientForDeletion) GetQuotes(symbols []string) (map[string]*domain.BrokerQuote, error) {
	return nil, nil
}
func (m *mockBrokerClientForDeletion) GetLevel1Quote(symbol string) (*domain.BrokerOrderBook, error) {
	return nil, nil
}
func (m *mockBrokerClientForDeletion) GetHistoricalPrices(symbol string, start, end int64, timeframeSeconds int) ([]domain.BrokerOHLCV, error) {
	return nil, nil
}
func (m *mockBrokerClientForDeletion) FindSymbol(symbol string, exchange *string) ([]domain.BrokerSecurityInfo, error) {
	return nil, nil
}
func (m *mockBrokerClientForDeletion) GetFXRates(baseCurrency string, currencies []string) (map[string]float64, error) {
	return nil, nil
}
func (m *mockBrokerClientForDeletion) GetAllCashFlows(limit int) ([]domain.BrokerCashFlow, error) {
	return nil, nil
}
func (m *mockBrokerClientForDeletion) GetCashMovements() (*domain.BrokerCashMovement, error) {
	return nil, nil
}
func (m *mockBrokerClientForDeletion) IsConnected() bool { return true }
func (m *mockBrokerClientForDeletion) HealthCheck() (*domain.BrokerHealthResult, error) {
	return nil, nil
}
func (m *mockBrokerClientForDeletion) SetCredentials(apiKey, apiSecret string) {}
func (m *mockBrokerClientForDeletion) GetSecurityMetadata(symbol string) (*domain.BrokerSecurityInfo, error) {
	return nil, nil
}

func TestSecurityDeletionService_HardDelete(t *testing.T) {
	log := zerolog.Nop()

	t.Run("fails if security does not exist", func(t *testing.T) {
		securityRepo := &mockSecurityRepoForDeletion{security: nil}
		positionRepo := &mockPositionRepoForDeletion{}
		scoreRepo := &mockScoreRepoForDeletion{}
		historyDB := &mockHistoryDBForDeletion{}
		brokerClient := &mockBrokerClientForDeletion{}

		service := NewSecurityDeletionService(
			securityRepo, positionRepo, scoreRepo, historyDB, brokerClient, log,
		)

		err := service.HardDelete("NONEXISTENT")

		assert.Error(t, err)
		assert.Contains(t, err.Error(), "not found")
		assert.False(t, securityRepo.deleted)
	})

	t.Run("fails if security has open positions", func(t *testing.T) {
		securityRepo := &mockSecurityRepoForDeletion{
			security: &Security{ISIN: "US0378331005", Symbol: "AAPL"},
		}
		positionRepo := &mockPositionRepoForDeletion{
			position: &portfolio.Position{ISIN: "US0378331005", Quantity: 100.0},
		}
		scoreRepo := &mockScoreRepoForDeletion{}
		historyDB := &mockHistoryDBForDeletion{}
		brokerClient := &mockBrokerClientForDeletion{}

		service := NewSecurityDeletionService(
			securityRepo, positionRepo, scoreRepo, historyDB, brokerClient, log,
		)

		err := service.HardDelete("US0378331005")

		assert.Error(t, err)
		assert.Contains(t, err.Error(), "open position")
		assert.False(t, securityRepo.deleted)
	})

	t.Run("fails if security has pending orders", func(t *testing.T) {
		securityRepo := &mockSecurityRepoForDeletion{
			security: &Security{ISIN: "US0378331005", Symbol: "AAPL"},
		}
		positionRepo := &mockPositionRepoForDeletion{
			position: &portfolio.Position{ISIN: "US0378331005", Quantity: 0},
		}
		scoreRepo := &mockScoreRepoForDeletion{}
		historyDB := &mockHistoryDBForDeletion{}
		brokerClient := &mockBrokerClientForDeletion{
			pendingOrders: []domain.BrokerPendingOrder{
				{Symbol: "AAPL", Side: "BUY", Quantity: 10},
			},
		}

		service := NewSecurityDeletionService(
			securityRepo, positionRepo, scoreRepo, historyDB, brokerClient, log,
		)

		err := service.HardDelete("US0378331005")

		assert.Error(t, err)
		assert.Contains(t, err.Error(), "pending order")
		assert.False(t, securityRepo.deleted)
	})

	t.Run("successfully deletes security with no positions and no pending orders", func(t *testing.T) {
		securityRepo := &mockSecurityRepoForDeletion{
			security: &Security{ISIN: "US0378331005", Symbol: "AAPL"},
		}
		positionRepo := &mockPositionRepoForDeletion{
			position: &portfolio.Position{ISIN: "US0378331005", Quantity: 0},
		}
		scoreRepo := &mockScoreRepoForDeletion{}
		historyDB := &mockHistoryDBForDeletion{}
		brokerClient := &mockBrokerClientForDeletion{pendingOrders: []domain.BrokerPendingOrder{}}

		service := NewSecurityDeletionService(
			securityRepo, positionRepo, scoreRepo, historyDB, brokerClient, log,
		)

		err := service.HardDelete("US0378331005")

		assert.NoError(t, err)
		assert.True(t, securityRepo.deleted, "Security should be deleted from universe")
		assert.True(t, positionRepo.deleted, "Position should be deleted")
		assert.True(t, scoreRepo.deleted, "Scores should be deleted")
		assert.True(t, historyDB.deleted, "Price history should be deleted")
	})

	t.Run("successfully deletes security when no position record exists", func(t *testing.T) {
		securityRepo := &mockSecurityRepoForDeletion{
			security: &Security{ISIN: "US0378331005", Symbol: "AAPL"},
		}
		positionRepo := &mockPositionRepoForDeletion{position: nil} // No position record
		scoreRepo := &mockScoreRepoForDeletion{}
		historyDB := &mockHistoryDBForDeletion{}
		brokerClient := &mockBrokerClientForDeletion{pendingOrders: []domain.BrokerPendingOrder{}}

		service := NewSecurityDeletionService(
			securityRepo, positionRepo, scoreRepo, historyDB, brokerClient, log,
		)

		err := service.HardDelete("US0378331005")

		assert.NoError(t, err)
		assert.True(t, securityRepo.deleted, "Security should be deleted from universe")
		assert.False(t, positionRepo.deleted, "No position to delete")
	})

	t.Run("fails if broker client returns error when checking pending orders", func(t *testing.T) {
		securityRepo := &mockSecurityRepoForDeletion{
			security: &Security{ISIN: "US0378331005", Symbol: "AAPL"},
		}
		positionRepo := &mockPositionRepoForDeletion{position: nil}
		scoreRepo := &mockScoreRepoForDeletion{}
		historyDB := &mockHistoryDBForDeletion{}
		brokerClient := &mockBrokerClientForDeletion{
			pendingErr: errors.New("broker connection failed"),
		}

		service := NewSecurityDeletionService(
			securityRepo, positionRepo, scoreRepo, historyDB, brokerClient, log,
		)

		err := service.HardDelete("US0378331005")

		assert.Error(t, err)
		assert.Contains(t, err.Error(), "pending orders")
		assert.False(t, securityRepo.deleted, "Security should not be deleted on broker error")
	})

	t.Run("continues cleanup even if secondary deletions fail", func(t *testing.T) {
		securityRepo := &mockSecurityRepoForDeletion{
			security: &Security{ISIN: "US0378331005", Symbol: "AAPL"},
		}
		positionRepo := &mockPositionRepoForDeletion{
			position:  &portfolio.Position{ISIN: "US0378331005", Quantity: 0},
			deleteErr: errors.New("position delete failed"),
		}
		scoreRepo := &mockScoreRepoForDeletion{deleteErr: errors.New("score delete failed")}
		historyDB := &mockHistoryDBForDeletion{deleteErr: errors.New("history delete failed")}
		brokerClient := &mockBrokerClientForDeletion{pendingOrders: []domain.BrokerPendingOrder{}}

		service := NewSecurityDeletionService(
			securityRepo, positionRepo, scoreRepo, historyDB, brokerClient, log,
		)

		err := service.HardDelete("US0378331005")

		// Should still succeed - universe deletion is the critical part
		assert.NoError(t, err)
		assert.True(t, securityRepo.deleted, "Security should be deleted from universe")
	})

	t.Run("fails if universe deletion fails", func(t *testing.T) {
		securityRepo := &mockSecurityRepoForDeletion{
			security:  &Security{ISIN: "US0378331005", Symbol: "AAPL"},
			deleteErr: errors.New("universe delete failed"),
		}
		positionRepo := &mockPositionRepoForDeletion{position: nil}
		scoreRepo := &mockScoreRepoForDeletion{}
		historyDB := &mockHistoryDBForDeletion{}
		brokerClient := &mockBrokerClientForDeletion{pendingOrders: []domain.BrokerPendingOrder{}}

		service := NewSecurityDeletionService(
			securityRepo, positionRepo, scoreRepo, historyDB, brokerClient, log,
		)

		err := service.HardDelete("US0378331005")

		assert.Error(t, err)
		assert.Contains(t, err.Error(), "failed to delete security from universe")
		// Secondary cleanups should not have run
		assert.False(t, scoreRepo.deleted)
		assert.False(t, historyDB.deleted)
	})

	t.Run("fails if security lookup returns error", func(t *testing.T) {
		securityRepo := &mockSecurityRepoForDeletion{
			security: nil,
			getErr:   errors.New("database connection failed"),
		}
		positionRepo := &mockPositionRepoForDeletion{}
		scoreRepo := &mockScoreRepoForDeletion{}
		historyDB := &mockHistoryDBForDeletion{}
		brokerClient := &mockBrokerClientForDeletion{}

		service := NewSecurityDeletionService(
			securityRepo, positionRepo, scoreRepo, historyDB, brokerClient, log,
		)

		err := service.HardDelete("US0378331005")

		assert.Error(t, err)
		assert.Contains(t, err.Error(), "failed to lookup security")
		assert.False(t, securityRepo.deleted)
	})

	t.Run("fails if position lookup returns error", func(t *testing.T) {
		securityRepo := &mockSecurityRepoForDeletion{
			security: &Security{ISIN: "US0378331005", Symbol: "AAPL"},
		}
		positionRepo := &mockPositionRepoForDeletion{
			position: nil,
			getErr:   errors.New("database connection failed"),
		}
		scoreRepo := &mockScoreRepoForDeletion{}
		historyDB := &mockHistoryDBForDeletion{}
		brokerClient := &mockBrokerClientForDeletion{}

		service := NewSecurityDeletionService(
			securityRepo, positionRepo, scoreRepo, historyDB, brokerClient, log,
		)

		err := service.HardDelete("US0378331005")

		assert.Error(t, err)
		assert.Contains(t, err.Error(), "failed to check positions")
		assert.False(t, securityRepo.deleted)
	})

	t.Run("handles case-insensitive symbol matching for pending orders", func(t *testing.T) {
		securityRepo := &mockSecurityRepoForDeletion{
			security: &Security{ISIN: "US0378331005", Symbol: "AAPL"},
		}
		positionRepo := &mockPositionRepoForDeletion{position: nil}
		scoreRepo := &mockScoreRepoForDeletion{}
		historyDB := &mockHistoryDBForDeletion{}
		brokerClient := &mockBrokerClientForDeletion{
			pendingOrders: []domain.BrokerPendingOrder{
				{Symbol: "aapl", Side: "BUY", Quantity: 10}, // lowercase symbol
			},
		}

		service := NewSecurityDeletionService(
			securityRepo, positionRepo, scoreRepo, historyDB, brokerClient, log,
		)

		err := service.HardDelete("US0378331005")

		assert.Error(t, err)
		assert.Contains(t, err.Error(), "pending order")
		assert.False(t, securityRepo.deleted)
	})
}
