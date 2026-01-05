package opportunities

import (
	"database/sql"
	"testing"
	"time"

	"github.com/aristath/arduino-trader/internal/domain"
	planningdomain "github.com/aristath/arduino-trader/internal/modules/planning/domain"
	scoringdomain "github.com/aristath/arduino-trader/internal/modules/scoring/domain"
	"github.com/aristath/arduino-trader/internal/modules/universe"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	_ "github.com/mattn/go-sqlite3"
)

func setupTagFilterTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)

	// Create securities table
	_, err = db.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT,
			yahoo_symbol TEXT,
			name TEXT NOT NULL,
			product_type TEXT,
			industry TEXT,
			country TEXT,
			fullExchangeName TEXT,
			priority_multiplier REAL DEFAULT 1.0,
			min_lot INTEGER DEFAULT 1,
			active INTEGER DEFAULT 1,
			allow_buy INTEGER DEFAULT 1,
			allow_sell INTEGER DEFAULT 1,
			currency TEXT,
			last_synced TEXT,
			min_portfolio_target REAL,
			max_portfolio_target REAL,
			created_at TEXT,
			updated_at TEXT
		)
	`)
	require.NoError(t, err)

	// Create tags table
	_, err = db.Exec(`
		CREATE TABLE tags (
			id TEXT PRIMARY KEY,
			name TEXT NOT NULL,
			created_at TEXT NOT NULL,
			updated_at TEXT NOT NULL
		)
	`)
	require.NoError(t, err)

	// Create security_tags table
	_, err = db.Exec(`
		CREATE TABLE security_tags (
			symbol TEXT NOT NULL,
			tag_id TEXT NOT NULL,
			created_at TEXT NOT NULL,
			updated_at TEXT NOT NULL,
			PRIMARY KEY (symbol, tag_id),
			FOREIGN KEY (symbol) REFERENCES securities(symbol) ON DELETE CASCADE,
			FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
		)
	`)
	require.NoError(t, err)

	// Create indexes
	_, err = db.Exec(`
		CREATE INDEX IF NOT EXISTS idx_security_tags_symbol ON security_tags(symbol);
		CREATE INDEX IF NOT EXISTS idx_security_tags_tag_id ON security_tags(tag_id);
	`)
	require.NoError(t, err)

	return db
}

func TestTagBasedFilter_GetOpportunityCandidates_WithCash(t *testing.T) {
	// Setup
	db := setupTagFilterTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityRepo := universe.NewSecurityRepository(db, log)
	filter := NewTagBasedFilter(securityRepo, log)

	now := time.Now().Format(time.RFC3339)

	// Insert test securities
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, name, active, created_at, updated_at)
		VALUES
			('US0378331005', 'AAPL', 'Apple Inc', 1, ?, ?),
			('US5949181045', 'MSFT', 'Microsoft Corp', 1, ?, ?),
			('US02079K3059', 'GOOGL', 'Alphabet Inc', 1, ?, ?)
	`, now, now, now, now, now, now)
	require.NoError(t, err)

	// Insert tags
	_, err = db.Exec(`
		INSERT INTO tags (id, name, created_at, updated_at)
		VALUES
			('quality-gate-pass', 'Quality Gate Pass', ?, ?),
			('high-quality', 'High Quality', ?, ?),
			('value-opportunity', 'Value Opportunity', ?, ?),
			('high-total-return', 'High Total Return', ?, ?)
	`, now, now, now, now, now, now, now, now)
	require.NoError(t, err)

	// Insert security tags
	_, err = db.Exec(`
		INSERT INTO security_tags (symbol, tag_id, created_at, updated_at)
		VALUES
			('AAPL', 'quality-gate-pass', ?, ?),
			('AAPL', 'high-quality', ?, ?),
			('AAPL', 'value-opportunity', ?, ?),
			('MSFT', 'quality-gate-pass', ?, ?),
			('MSFT', 'high-total-return', ?, ?)
	`, now, now, now, now, now, now, now, now, now, now)
	require.NoError(t, err)

	// Create opportunity context with cash
	ctx := planningdomain.NewOpportunityContext(
		&scoringdomain.PortfolioContext{},
		[]domain.Position{},
		[]domain.Security{},
		2000.0, // Available cash > 1000
		10000.0,
		map[string]float64{},
	)

	// Execute
	candidates, err := filter.GetOpportunityCandidates(ctx)

	// Assert
	assert.NoError(t, err)
	assert.NotEmpty(t, candidates)
	// Should include securities with quality-gate-pass, high-quality, value-opportunity, or high-total-return
	assert.Contains(t, candidates, "AAPL")
	assert.Contains(t, candidates, "MSFT")
}

func TestTagBasedFilter_GetOpportunityCandidates_NoCash(t *testing.T) {
	// Setup
	db := setupTagFilterTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityRepo := universe.NewSecurityRepository(db, log)
	filter := NewTagBasedFilter(securityRepo, log)

	now := time.Now().Format(time.RFC3339)

	// Insert test securities
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, name, active, created_at, updated_at)
		VALUES
			('US0378331005', 'AAPL', 'Apple Inc', 1, ?, ?),
			('US5949181045', 'MSFT', 'Microsoft Corp', 1, ?, ?)
	`, now, now, now, now)
	require.NoError(t, err)

	// Insert tags
	_, err = db.Exec(`
		INSERT INTO tags (id, name, created_at, updated_at)
		VALUES
			('quality-gate-pass', 'Quality Gate Pass', ?, ?),
			('high-quality', 'High Quality', ?, ?)
	`, now, now, now, now)
	require.NoError(t, err)

	// Insert security tags (only quality tags, no value tags)
	_, err = db.Exec(`
		INSERT INTO security_tags (symbol, tag_id, created_at, updated_at)
		VALUES
			('AAPL', 'quality-gate-pass', ?, ?),
			('AAPL', 'high-quality', ?, ?),
			('MSFT', 'quality-gate-pass', ?, ?)
	`, now, now, now, now, now, now)
	require.NoError(t, err)

	// Create opportunity context with low cash
	ctx := planningdomain.NewOpportunityContext(
		&scoringdomain.PortfolioContext{},
		[]domain.Position{},
		[]domain.Security{},
		500.0, // Available cash < 1000 (no value opportunities)
		10000.0,
		map[string]float64{},
	)

	// Execute
	candidates, err := filter.GetOpportunityCandidates(ctx)

	// Assert
	assert.NoError(t, err)
	// Should still find quality candidates
	assert.Contains(t, candidates, "AAPL")
	assert.Contains(t, candidates, "MSFT")
}

func TestTagBasedFilter_GetSellCandidates(t *testing.T) {
	// Setup
	db := setupTagFilterTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityRepo := universe.NewSecurityRepository(db, log)
	filter := NewTagBasedFilter(securityRepo, log)

	now := time.Now().Format(time.RFC3339)

	// Insert test securities
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, name, active, created_at, updated_at)
		VALUES
			('US0378331005', 'AAPL', 'Apple Inc', 1, ?, ?),
			('US5949181045', 'MSFT', 'Microsoft Corp', 1, ?, ?),
			('US02079K3059', 'GOOGL', 'Alphabet Inc', 1, ?, ?)
	`, now, now, now, now, now, now)
	require.NoError(t, err)

	// Insert tags
	_, err = db.Exec(`
		INSERT INTO tags (id, name, created_at, updated_at)
		VALUES
			('overvalued', 'Overvalued', ?, ?),
			('needs-rebalance', 'Needs Rebalance', ?, ?),
			('bubble-risk', 'Bubble Risk', ?, ?)
	`, now, now, now, now, now, now)
	require.NoError(t, err)

	// Insert security tags
	_, err = db.Exec(`
		INSERT INTO security_tags (symbol, tag_id, created_at, updated_at)
		VALUES
			('AAPL', 'overvalued', ?, ?),
			('AAPL', 'needs-rebalance', ?, ?),
			('MSFT', 'bubble-risk', ?, ?)
	`, now, now, now, now, now, now)
	require.NoError(t, err)

	// Create opportunity context with positions
	ctx := planningdomain.NewOpportunityContext(
		&scoringdomain.PortfolioContext{},
		[]domain.Position{
			{Symbol: "AAPL", Quantity: 10},
			{Symbol: "MSFT", Quantity: 5},
			{Symbol: "GOOGL", Quantity: 3}, // No sell tags
		},
		[]domain.Security{},
		1000.0,
		10000.0,
		map[string]float64{},
	)

	// Execute
	candidates, err := filter.GetSellCandidates(ctx)

	// Assert
	assert.NoError(t, err)
	assert.NotEmpty(t, candidates)
	// Should include positions with sell tags
	assert.Contains(t, candidates, "AAPL") // Has overvalued and needs-rebalance
	assert.Contains(t, candidates, "MSFT") // Has bubble-risk
	assert.NotContains(t, candidates, "GOOGL") // No sell tags
}

func TestTagBasedFilter_GetSellCandidates_NoPositions(t *testing.T) {
	// Setup
	db := setupTagFilterTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityRepo := universe.NewSecurityRepository(db, log)
	filter := NewTagBasedFilter(securityRepo, log)

	// Create opportunity context with no positions
	ctx := planningdomain.NewOpportunityContext(
		&scoringdomain.PortfolioContext{},
		[]domain.Position{},
		[]domain.Security{},
		1000.0,
		10000.0,
		map[string]float64{},
	)

	// Execute
	candidates, err := filter.GetSellCandidates(ctx)

	// Assert
	assert.NoError(t, err)
	assert.Empty(t, candidates)
}

func TestTagBasedFilter_isMarketVolatile(t *testing.T) {
	// Setup
	db := setupTagFilterTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityRepo := universe.NewSecurityRepository(db, log)
	filter := NewTagBasedFilter(securityRepo, log)

	now := time.Now().Format(time.RFC3339)

	// Insert test securities
	symbols := []string{"AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"}
	placeholders := ""
	args := []interface{}{}
	for i, symbol := range symbols {
		if i > 0 {
			placeholders += ", "
		}
		placeholders += "(?, ?, ?, ?, ?, ?)"
		args = append(args, "ISIN"+symbol, symbol, symbol+" Inc", 1, now, now)
	}

	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, name, active, created_at, updated_at)
		VALUES `+placeholders, args...)
	require.NoError(t, err)

	// Insert volatility-spike tag
	_, err = db.Exec(`
		INSERT INTO tags (id, name, created_at, updated_at)
		VALUES ('volatility-spike', 'Volatility Spike', ?, ?)
	`, now, now)
	require.NoError(t, err)

	// Insert security tags - 6 securities with volatility-spike (above threshold of 5)
	tagArgs := []interface{}{}
	for _, symbol := range symbols {
		tagArgs = append(tagArgs, symbol, "volatility-spike", now, now)
	}
	placeholders = ""
	for i := 0; i < len(symbols); i++ {
		if i > 0 {
			placeholders += ", "
		}
		placeholders += "(?, ?, ?, ?)"
	}

	_, err = db.Exec(`
		INSERT INTO security_tags (symbol, tag_id, created_at, updated_at)
		VALUES `+placeholders, tagArgs...)
	require.NoError(t, err)

	// Create opportunity context
	ctx := planningdomain.NewOpportunityContext(
		&scoringdomain.PortfolioContext{},
		[]domain.Position{},
		[]domain.Security{},
		1000.0,
		10000.0,
		map[string]float64{},
	)

	// Execute
	isVolatile := filter.isMarketVolatile(ctx)

	// Assert
	assert.True(t, isVolatile, "Market should be volatile with 6 securities having volatility-spike tag")
}

func TestTagBasedFilter_isMarketVolatile_NotVolatile(t *testing.T) {
	// Setup
	db := setupTagFilterTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityRepo := universe.NewSecurityRepository(db, log)
	filter := NewTagBasedFilter(securityRepo, log)

	now := time.Now().Format(time.RFC3339)

	// Insert test securities
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, name, active, created_at, updated_at)
		VALUES
			('US0378331005', 'AAPL', 'Apple Inc', 1, ?, ?),
			('US5949181045', 'MSFT', 'Microsoft Corp', 1, ?, ?)
	`, now, now, now, now)
	require.NoError(t, err)

	// Insert volatility-spike tag
	_, err = db.Exec(`
		INSERT INTO tags (id, name, created_at, updated_at)
		VALUES ('volatility-spike', 'Volatility Spike', ?, ?)
	`, now, now)
	require.NoError(t, err)

	// Insert security tags - only 2 securities with volatility-spike (below threshold of 5)
	_, err = db.Exec(`
		INSERT INTO security_tags (symbol, tag_id, created_at, updated_at)
		VALUES
			('AAPL', 'volatility-spike', ?, ?),
			('MSFT', 'volatility-spike', ?, ?)
	`, now, now, now, now)
	require.NoError(t, err)

	// Create opportunity context
	ctx := planningdomain.NewOpportunityContext(
		&scoringdomain.PortfolioContext{},
		[]domain.Position{},
		[]domain.Security{},
		1000.0,
		10000.0,
		map[string]float64{},
	)

	// Execute
	isVolatile := filter.isMarketVolatile(ctx)

	// Assert
	assert.False(t, isVolatile, "Market should not be volatile with only 2 securities having volatility-spike tag")
}

