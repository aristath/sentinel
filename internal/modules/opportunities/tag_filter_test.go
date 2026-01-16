package opportunities

import (
	"database/sql"
	"testing"
	"time"

	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	scoringdomain "github.com/aristath/sentinel/internal/modules/scoring/domain"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	_ "github.com/mattn/go-sqlite3"
)

func setupTagFilterTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)

	// Create securities table (JSON storage - migration 038)
	_, err = db.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			data TEXT NOT NULL,
			last_synced INTEGER
		) STRICT
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

	// Create security_tags table (after migration 030: uses isin, not symbol)
	_, err = db.Exec(`
		CREATE TABLE security_tags (
			isin TEXT NOT NULL,
			tag_id TEXT NOT NULL,
			created_at TEXT NOT NULL,
			updated_at TEXT NOT NULL,
			PRIMARY KEY (isin, tag_id),
			FOREIGN KEY (isin) REFERENCES securities(isin) ON DELETE CASCADE,
			FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
		)
	`)
	require.NoError(t, err)

	// Create indexes (migration 038: removed idx_securities_active)
	_, err = db.Exec(`
		CREATE INDEX IF NOT EXISTS idx_securities_symbol ON securities(symbol);
		CREATE INDEX IF NOT EXISTS idx_security_tags_isin ON security_tags(isin);
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
	universeRepo := universe.NewSecurityRepository(db, log)
	filter := NewTagBasedFilter(universeRepo, log)

	now := time.Now().Unix()

	// Insert test securities
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES
			('US0378331005', 'AAPL', json_object('name', 'Apple Inc'), NULL),
			('US5949181045', 'MSFT', json_object('name', 'Microsoft Corp'), NULL),
			('US02079K3059', 'GOOGL', json_object('name', 'Alphabet Inc'), NULL)
	`)
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

	// Insert security tags using ISINs
	_, err = db.Exec(`
		INSERT INTO security_tags (isin, tag_id, created_at, updated_at)
		VALUES
			('US0378331005', 'quality-gate-pass', ?, ?),
			('US0378331005', 'high-quality', ?, ?),
			('US0378331005', 'value-opportunity', ?, ?),
			('US5949181045', 'quality-gate-pass', ?, ?),
			('US5949181045', 'high-total-return', ?, ?)
	`, now, now, now, now, now, now, now, now, now, now)
	require.NoError(t, err)

	// Create opportunity context with cash
	ctx := planningdomain.NewOpportunityContext(
		&scoringdomain.PortfolioContext{},
		[]planningdomain.EnrichedPosition{},
		[]universe.Security{},
		2000.0, // Available cash > 1000
		10000.0,
		map[string]float64{},
	)

	// Execute
	candidates, err := filter.GetOpportunityCandidates(ctx, nil)

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
	universeRepo := universe.NewSecurityRepository(db, log)
	filter := NewTagBasedFilter(universeRepo, log)

	now := time.Now().Unix()

	// Insert test securities
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES
			('US0378331005', 'AAPL', json_object('name', 'Apple Inc'), NULL),
			('US5949181045', 'MSFT', json_object('name', 'Microsoft Corp'), NULL)
	`)
	require.NoError(t, err)

	// Insert tags
	_, err = db.Exec(`
		INSERT INTO tags (id, name, created_at, updated_at)
		VALUES
			('quality-gate-pass', 'Quality Gate Pass', ?, ?),
			('high-quality', 'High Quality', ?, ?)
	`, now, now, now, now)
	require.NoError(t, err)

	// Insert security tags using ISINs (only quality tags, no value tags)
	_, err = db.Exec(`
		INSERT INTO security_tags (isin, tag_id, created_at, updated_at)
		VALUES
			('US0378331005', 'high-quality', ?, ?),
			('US5949181045', 'high-quality', ?, ?)
	`, now, now, now, now)
	require.NoError(t, err)

	// Create opportunity context with low cash
	ctx := planningdomain.NewOpportunityContext(
		&scoringdomain.PortfolioContext{},
		[]planningdomain.EnrichedPosition{},
		[]universe.Security{},
		500.0, // Available cash < 1000 (no value opportunities)
		10000.0,
		map[string]float64{},
	)

	// Execute
	candidates, err := filter.GetOpportunityCandidates(ctx, nil)

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
	universeRepo := universe.NewSecurityRepository(db, log)
	filter := NewTagBasedFilter(universeRepo, log)

	now := time.Now().Unix()

	// Insert test securities
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES
			('US0378331005', 'AAPL', json_object('name', 'Apple Inc'), NULL),
			('US5949181045', 'MSFT', json_object('name', 'Microsoft Corp'), NULL),
			('US02079K3059', 'GOOGL', json_object('name', 'Alphabet Inc'), NULL)
	`)
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

	// Insert security tags using ISINs
	_, err = db.Exec(`
		INSERT INTO security_tags (isin, tag_id, created_at, updated_at)
		VALUES
			('US0378331005', 'overvalued', ?, ?),
			('US0378331005', 'needs-rebalance', ?, ?),
			('US5949181045', 'bubble-risk', ?, ?)
	`, now, now, now, now, now, now)
	require.NoError(t, err)

	// Create opportunity context with positions
	ctx := planningdomain.NewOpportunityContext(
		&scoringdomain.PortfolioContext{},
		[]planningdomain.EnrichedPosition{
			{Symbol: "AAPL", Quantity: 10},
			{Symbol: "MSFT", Quantity: 5},
			{Symbol: "GOOGL", Quantity: 3}, // No sell tags
		},
		[]universe.Security{},
		1000.0,
		10000.0,
		map[string]float64{},
	)

	// Execute
	candidates, err := filter.GetSellCandidates(ctx, nil)

	// Assert
	assert.NoError(t, err)
	assert.NotEmpty(t, candidates)
	// Should include positions with sell tags
	assert.Contains(t, candidates, "AAPL")     // Has overvalued and needs-rebalance
	assert.Contains(t, candidates, "MSFT")     // Has bubble-risk
	assert.NotContains(t, candidates, "GOOGL") // No sell tags
}

func TestTagBasedFilter_GetSellCandidates_NoPositions(t *testing.T) {
	// Setup
	db := setupTagFilterTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	universeRepo := universe.NewSecurityRepository(db, log)
	filter := NewTagBasedFilter(universeRepo, log)

	// Create opportunity context with no positions
	ctx := planningdomain.NewOpportunityContext(
		&scoringdomain.PortfolioContext{},
		[]planningdomain.EnrichedPosition{},
		[]universe.Security{},
		1000.0,
		10000.0,
		map[string]float64{},
	)

	// Execute
	candidates, err := filter.GetSellCandidates(ctx, nil)

	// Assert
	assert.NoError(t, err)
	assert.Empty(t, candidates)
}

func TestTagBasedFilter_isMarketVolatile(t *testing.T) {
	// Setup
	db := setupTagFilterTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	universeRepo := universe.NewSecurityRepository(db, log)
	filter := NewTagBasedFilter(universeRepo, log)

	now := time.Now().Unix()

	// Insert test securities (JSON storage - migration 038)
	symbols := []string{"AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"}
	placeholders := ""
	args := []interface{}{}
	for i, symbol := range symbols {
		if i > 0 {
			placeholders += ", "
		}
		placeholders += "(?, ?, json_object('name', ?), NULL)"
		args = append(args, "ISIN"+symbol, symbol, symbol+" Inc")
	}

	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES `+placeholders, args...)
	require.NoError(t, err)

	// Insert volatility-spike tag
	_, err = db.Exec(`
		INSERT INTO tags (id, name, created_at, updated_at)
		VALUES ('volatility-spike', 'Volatility Spike', ?, ?)
	`, now, now)
	require.NoError(t, err)

	// Insert security tags - 6 securities with volatility-spike (above threshold of 5)
	// Use ISINs (mapped from symbols: "ISIN" + symbol)
	tagArgs := []interface{}{}
	for _, symbol := range symbols {
		isin := "ISIN" + symbol // Match the ISIN format used in securities insert
		tagArgs = append(tagArgs, isin, "volatility-spike", now, now)
	}
	placeholders = ""
	for i := 0; i < len(symbols); i++ {
		if i > 0 {
			placeholders += ", "
		}
		placeholders += "(?, ?, ?, ?)"
	}

	_, err = db.Exec(`
		INSERT INTO security_tags (isin, tag_id, created_at, updated_at)
		VALUES `+placeholders, tagArgs...)
	require.NoError(t, err)

	// Create opportunity context
	ctx := planningdomain.NewOpportunityContext(
		&scoringdomain.PortfolioContext{},
		[]planningdomain.EnrichedPosition{},
		[]universe.Security{},
		1000.0,
		10000.0,
		map[string]float64{},
	)

	// Execute
	config := planningdomain.NewDefaultConfiguration()
	isVolatile := filter.IsMarketVolatile(ctx, config)

	// Assert
	assert.True(t, isVolatile, "Market should be volatile with 6 securities having volatility-spike tag")
}

func TestTagBasedFilter_isMarketVolatile_NotVolatile(t *testing.T) {
	// Setup
	db := setupTagFilterTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	universeRepo := universe.NewSecurityRepository(db, log)
	filter := NewTagBasedFilter(universeRepo, log)

	now := time.Now().Unix()

	// Insert test securities
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, data, last_synced)
		VALUES
			('US0378331005', 'AAPL', json_object('name', 'Apple Inc'), NULL),
			('US5949181045', 'MSFT', json_object('name', 'Microsoft Corp'), NULL)
	`)
	require.NoError(t, err)

	// Insert volatility-spike tag
	_, err = db.Exec(`
		INSERT INTO tags (id, name, created_at, updated_at)
		VALUES ('volatility-spike', 'Volatility Spike', ?, ?)
	`, now, now)
	require.NoError(t, err)

	// Insert security tags using ISINs - only 2 securities with volatility-spike (below threshold of 5)
	_, err = db.Exec(`
		INSERT INTO security_tags (isin, tag_id, created_at, updated_at)
		VALUES
			('US0378331005', 'volatility-spike', ?, ?),
			('US5949181045', 'volatility-spike', ?, ?)
	`, now, now, now, now)
	require.NoError(t, err)

	// Create opportunity context
	ctx := planningdomain.NewOpportunityContext(
		&scoringdomain.PortfolioContext{},
		[]planningdomain.EnrichedPosition{},
		[]universe.Security{},
		1000.0,
		10000.0,
		map[string]float64{},
	)

	// Execute
	config := planningdomain.NewDefaultConfiguration()
	isVolatile := filter.IsMarketVolatile(ctx, config)

	// Assert
	assert.False(t, isVolatile, "Market should not be volatile with only 2 securities having volatility-spike tag")
}
