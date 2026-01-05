package calculators

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

// mockTagFilter is a test implementation of TagFilter
type mockTagFilter struct {
	opportunityCandidates []string
	sellCandidates        []string
}

func (m *mockTagFilter) GetOpportunityCandidates(ctx *planningdomain.OpportunityContext) ([]string, error) {
	return m.opportunityCandidates, nil
}

func (m *mockTagFilter) GetSellCandidates(ctx *planningdomain.OpportunityContext) ([]string, error) {
	return m.sellCandidates, nil
}

func setupHybridCalculatorTestDB(t *testing.T) *sql.DB {
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
			PRIMARY KEY (symbol, tag_id)
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

func TestHybridOpportunityBuysCalculator_Calculate_WithTagFiltering(t *testing.T) {
	// Setup
	db := setupHybridCalculatorTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityRepo := universe.NewSecurityRepository(db, log)

	// Create mock tag filter that returns specific candidates
	mockFilter := &mockTagFilter{
		opportunityCandidates: []string{"AAPL", "MSFT"},
	}

	calculator := NewHybridOpportunityBuysCalculator(mockFilter, securityRepo, log)

	now := time.Now().Format(time.RFC3339)

	// Insert test securities
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, name, active, currency, created_at, updated_at)
		VALUES
			('US0378331005', 'AAPL', 'Apple Inc', 1, 'USD', ?, ?),
			('US5949181045', 'MSFT', 'Microsoft Corp', 1, 'USD', ?, ?)
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

	// Insert security tags
	_, err = db.Exec(`
		INSERT INTO security_tags (symbol, tag_id, created_at, updated_at)
		VALUES
			('AAPL', 'quality-gate-pass', ?, ?),
			('AAPL', 'high-quality', ?, ?),
			('MSFT', 'quality-gate-pass', ?, ?)
	`, now, now, now, now, now, now)
	require.NoError(t, err)

	// Create opportunity context
	securities := []domain.Security{
		{ISIN: "US0378331005", Symbol: "AAPL", Name: "Apple Inc", Currency: domain.CurrencyUSD},
		{ISIN: "US5949181045", Symbol: "MSFT", Name: "Microsoft Corp", Currency: domain.CurrencyUSD},
	}

	ctx := planningdomain.NewOpportunityContext(
		&scoringdomain.PortfolioContext{},
		[]domain.Position{},
		securities,
		2000.0,
		10000.0,
		map[string]float64{
			"US0378331005": 150.0,
			"US5949181045": 300.0,
		},
	)

	// Set security scores
	ctx.SecurityScores = map[string]float64{
		"AAPL": 0.85,
		"MSFT": 0.80,
	}

	// Execute
	candidates, err := calculator.Calculate(ctx, nil)

	// Assert
	assert.NoError(t, err)
	assert.NotEmpty(t, candidates)
	// Should have candidates for both AAPL and MSFT (tag-filtered)
	assert.GreaterOrEqual(t, len(candidates), 1)
}

func TestHybridOpportunityBuysCalculator_Calculate_ExcludesValueTraps(t *testing.T) {
	// Setup
	db := setupHybridCalculatorTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityRepo := universe.NewSecurityRepository(db, log)

	// Create mock tag filter
	mockFilter := &mockTagFilter{
		opportunityCandidates: []string{"TRAP"},
	}

	calculator := NewHybridOpportunityBuysCalculator(mockFilter, securityRepo, log)

	now := time.Now().Format(time.RFC3339)

	// Insert test security with value-trap tag
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, name, active, currency, created_at, updated_at)
		VALUES ('TRAP001', 'TRAP', 'Value Trap Inc', 1, 'USD', ?, ?)
	`, now, now)
	require.NoError(t, err)

	// Insert value-trap tag
	_, err = db.Exec(`
		INSERT INTO tags (id, name, created_at, updated_at)
		VALUES ('value-trap', 'Value Trap', ?, ?)
	`, now, now)
	require.NoError(t, err)

	// Insert security tag
	_, err = db.Exec(`
		INSERT INTO security_tags (symbol, tag_id, created_at, updated_at)
		VALUES ('TRAP', 'value-trap', ?, ?)
	`, now, now)
	require.NoError(t, err)

	// Create opportunity context
	securities := []domain.Security{
		{ISIN: "TRAP001", Symbol: "TRAP", Name: "Value Trap Inc", Currency: domain.CurrencyUSD},
	}

	ctx := planningdomain.NewOpportunityContext(
		&scoringdomain.PortfolioContext{},
		[]domain.Position{},
		securities,
		2000.0,
		10000.0,
		map[string]float64{
			"TRAP001": 50.0,
		},
	)

	ctx.SecurityScores = map[string]float64{
		"TRAP": 0.85, // High score, but should be excluded
	}

	// Execute
	candidates, err := calculator.Calculate(ctx, nil)

	// Assert
	assert.NoError(t, err)
	// Should exclude value trap even though it has high score
	assert.Empty(t, candidates, "Value trap should be excluded")
}

func TestHybridOpportunityBuysCalculator_Calculate_ExcludesBubbleRisks(t *testing.T) {
	// Setup
	db := setupHybridCalculatorTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityRepo := universe.NewSecurityRepository(db, log)

	// Create mock tag filter
	mockFilter := &mockTagFilter{
		opportunityCandidates: []string{"BUBBLE"},
	}

	calculator := NewHybridOpportunityBuysCalculator(mockFilter, securityRepo, log)

	now := time.Now().Format(time.RFC3339)

	// Insert test security with bubble-risk tag (but not quality-high-cagr)
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, name, active, currency, created_at, updated_at)
		VALUES ('BUBBLE001', 'BUBBLE', 'Bubble Corp', 1, 'USD', ?, ?)
	`, now, now)
	require.NoError(t, err)

	// Insert bubble-risk tag
	_, err = db.Exec(`
		INSERT INTO tags (id, name, created_at, updated_at)
		VALUES ('bubble-risk', 'Bubble Risk', ?, ?)
	`, now, now)
	require.NoError(t, err)

	// Insert security tag
	_, err = db.Exec(`
		INSERT INTO security_tags (symbol, tag_id, created_at, updated_at)
		VALUES ('BUBBLE', 'bubble-risk', ?, ?)
	`, now, now)
	require.NoError(t, err)

	// Create opportunity context
	securities := []domain.Security{
		{ISIN: "BUBBLE001", Symbol: "BUBBLE", Name: "Bubble Corp", Currency: domain.CurrencyUSD},
	}

	ctx := planningdomain.NewOpportunityContext(
		&scoringdomain.PortfolioContext{},
		[]domain.Position{},
		securities,
		2000.0,
		10000.0,
		map[string]float64{
			"BUBBLE001": 200.0,
		},
	)

	ctx.SecurityScores = map[string]float64{
		"BUBBLE": 0.90, // High score, but should be excluded
	}

	// Execute
	candidates, err := calculator.Calculate(ctx, nil)

	// Assert
	assert.NoError(t, err)
	// Should exclude bubble risk (without quality-high-cagr)
	assert.Empty(t, candidates, "Bubble risk should be excluded")
}

func TestHybridOpportunityBuysCalculator_Calculate_PriorityBoosting(t *testing.T) {
	// Setup
	db := setupHybridCalculatorTestDB(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	securityRepo := universe.NewSecurityRepository(db, log)

	// Create mock tag filter
	mockFilter := &mockTagFilter{
		opportunityCandidates: []string{"QUALITY"},
	}

	calculator := NewHybridOpportunityBuysCalculator(mockFilter, securityRepo, log)

	now := time.Now().Format(time.RFC3339)

	// Insert test security with quality-value tag (should get priority boost)
	_, err := db.Exec(`
		INSERT INTO securities (isin, symbol, name, active, currency, created_at, updated_at)
		VALUES ('QUALITY001', 'QUALITY', 'Quality Value Inc', 1, 'USD', ?, ?)
	`, now, now)
	require.NoError(t, err)

	// Insert tags
	_, err = db.Exec(`
		INSERT INTO tags (id, name, created_at, updated_at)
		VALUES
			('quality-gate-pass', 'Quality Gate Pass', ?, ?),
			('quality-value', 'Quality Value', ?, ?)
	`, now, now, now, now)
	require.NoError(t, err)

	// Insert security tags
	_, err = db.Exec(`
		INSERT INTO security_tags (symbol, tag_id, created_at, updated_at)
		VALUES
			('QUALITY', 'quality-gate-pass', ?, ?),
			('QUALITY', 'quality-value', ?, ?)
	`, now, now, now, now)
	require.NoError(t, err)

	// Create opportunity context
	securities := []domain.Security{
		{ISIN: "QUALITY001", Symbol: "QUALITY", Name: "Quality Value Inc", Currency: domain.CurrencyUSD},
	}

	ctx := planningdomain.NewOpportunityContext(
		&scoringdomain.PortfolioContext{},
		[]domain.Position{},
		securities,
		2000.0,
		10000.0,
		map[string]float64{
			"QUALITY001": 100.0,
		},
	)

	baseScore := 0.70
	ctx.SecurityScores = map[string]float64{
		"QUALITY": baseScore,
	}

	// Execute
	candidates, err := calculator.Calculate(ctx, nil)

	// Assert
	assert.NoError(t, err)
	assert.NotEmpty(t, candidates)
	
	// Priority should be boosted (quality-value tag gives 1.4x boost, capped at 1.0)
	// So 0.70 * 1.4 = 0.98, which should be capped at 1.0
	// But due to floating point precision, it might be slightly less
	assert.Greater(t, candidates[0].Priority, baseScore, "Priority should be boosted for quality-value tag")
	assert.LessOrEqual(t, candidates[0].Priority, 1.0, "Priority should be capped at 1.0")
	// Should be close to 0.98 (0.70 * 1.4)
	assert.InDelta(t, 0.98, candidates[0].Priority, 0.01, "Priority should be approximately 0.98")
}

