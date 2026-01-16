package universe

import (
	"database/sql"
	"testing"
	"time"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	_ "github.com/mattn/go-sqlite3"
)

// mockScoreSecurityProvider implements ScoreSecurityProvider for testing
type mockScoreSecurityProvider struct {
	universeDB *sql.DB
}

func (m *mockScoreSecurityProvider) GetISINBySymbol(symbol string) (string, error) {
	var isin string
	query := `SELECT isin FROM securities WHERE symbol = ?`
	err := m.universeDB.QueryRow(query, symbol).Scan(&isin)
	if err == sql.ErrNoRows {
		return "", nil
	}
	return isin, err
}

func setupTestDBForScoresWithISIN(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)

	// Create scores table with ISIN as PRIMARY KEY (post-migration schema)
	_, err = db.Exec(`
		CREATE TABLE scores (
			isin TEXT PRIMARY KEY,
			total_score REAL NOT NULL,
			quality_score REAL,
			opportunity_score REAL,
			analyst_score REAL,
			allocation_fit_score REAL,
			volatility REAL,
			cagr_score REAL,
			consistency_score REAL,
			history_years INTEGER,
			technical_score REAL,
			stability_score REAL,
			sharpe_score REAL,
			drawdown_score REAL,
			dividend_bonus REAL,
			financial_strength_score REAL,
			rsi REAL,
			ema_200 REAL,
			below_52w_high_pct REAL,
			last_updated INTEGER NOT NULL
		)
	`)
	require.NoError(t, err)

	// Create index on symbol for lookups (if we keep symbol column)
	// Note: After migration, scores table uses ISIN as PRIMARY KEY
	// Symbol may be removed or kept as indexed column

	return db
}

func TestScoreRepository_GetByISIN_PrimaryMethod(t *testing.T) {
	db := setupTestDBForScoresWithISIN(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewScoreRepository(db, log)

	// Insert test data
	testDate := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
	_, err := db.Exec(`
		INSERT INTO scores (isin, total_score, last_updated)
		VALUES ('US0378331005', 85.5, ?)
	`, testDate.Unix())
	require.NoError(t, err)

	// Execute
	score, err := repo.GetByISIN("US0378331005")

	// Assert
	require.NoError(t, err)
	require.NotNil(t, score)
	assert.Equal(t, "US0378331005", score.ISIN)
	assert.Equal(t, 85.5, score.TotalScore)
}

func TestScoreRepository_GetByISIN_NotFound(t *testing.T) {
	db := setupTestDBForScoresWithISIN(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewScoreRepository(db, log)

	// Execute
	score, err := repo.GetByISIN("US0000000000")

	// Assert
	require.NoError(t, err)
	assert.Nil(t, score)
}

func TestScoreRepository_Upsert_WithISIN(t *testing.T) {
	db := setupTestDBForScoresWithISIN(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewScoreRepository(db, log)

	// Execute - Upsert should use ISIN
	now := time.Now()
	score := SecurityScore{
		ISIN:         "US0378331005",
		Symbol:       "AAPL.US", // Keep symbol for display/backward compatibility
		TotalScore:   90.0,
		QualityScore: 85.0,
		CalculatedAt: &now,
	}

	err := repo.Upsert(score)
	require.NoError(t, err)

	// Verify upsert
	retrieved, err := repo.GetByISIN("US0378331005")
	require.NoError(t, err)
	require.NotNil(t, retrieved)
	assert.Equal(t, 90.0, retrieved.TotalScore)
	assert.Equal(t, 85.0, retrieved.QualityScore)
}

func TestScoreRepository_Delete_ByISIN(t *testing.T) {
	db := setupTestDBForScoresWithISIN(t)
	defer db.Close()

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewScoreRepository(db, log)

	// Insert test data
	_, err := db.Exec(`
		INSERT INTO scores (isin, total_score, last_updated)
		VALUES ('US0378331005', 85.5, '2024-01-01T00:00:00Z')
	`)
	require.NoError(t, err)

	// Execute - Delete should use ISIN
	err = repo.Delete("US0378331005")
	require.NoError(t, err)

	// Verify deletion
	score, err := repo.GetByISIN("US0378331005")
	require.NoError(t, err)
	assert.Nil(t, score, "Score should be deleted")
}

func TestScoreRepository_GetBySymbol_HelperMethod(t *testing.T) {
	portfolioDB := setupTestDBForScoresWithISIN(t)
	defer portfolioDB.Close()

	// Create universe DB with securities table
	universeDB, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)
	defer universeDB.Close()

	_, err = universeDB.Exec(`
		CREATE TABLE securities (
			isin TEXT PRIMARY KEY,
			symbol TEXT NOT NULL,
			name TEXT NOT NULL,
			created_at INTEGER NOT NULL,
			updated_at INTEGER NOT NULL
		)
	`)
	require.NoError(t, err)

	// Insert security
	testDate := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
	_, err = universeDB.Exec(`
		INSERT INTO securities (isin, symbol, name, created_at, updated_at)
		VALUES ('US0378331005', 'AAPL.US', 'Apple Inc.', ?, ?)
	`, testDate.Unix(), testDate.Unix())
	require.NoError(t, err)

	// Insert score
	_, err = portfolioDB.Exec(`
		INSERT INTO scores (isin, total_score, last_updated)
		VALUES ('US0378331005', 85.5, ?)
	`, testDate.Unix())
	require.NoError(t, err)

	// Create mock security provider for testing
	mockSecurityProvider := &mockScoreSecurityProvider{
		universeDB: universeDB,
	}

	log := zerolog.New(nil).Level(zerolog.Disabled)
	repo := NewScoreRepositoryWithUniverse(portfolioDB, mockSecurityProvider, log)

	// GetBySymbol should lookup ISIN first, then query by ISIN
	score, err := repo.GetBySymbol("AAPL.US")
	require.NoError(t, err)
	require.NotNil(t, score)
	assert.Equal(t, "US0378331005", score.ISIN)
	assert.Equal(t, 85.5, score.TotalScore)
}
