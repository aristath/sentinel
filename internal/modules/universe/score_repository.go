// Package universe provides repository implementations for managing the investment universe.
// This file implements the ScoreRepository, which handles security scoring data stored
// in portfolio.db. Scores include quality, opportunity, analyst, allocation fit, and
// various technical metrics.
package universe

import (
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// ScoreSecurityProvider provides read-only access to securities for ISIN lookups.
// This interface is used by ScoreRepository to resolve symbols to ISINs when
// GetBySymbol is called. It breaks the circular dependency between ScoreRepository
// and SecurityRepository.
type ScoreSecurityProvider interface {
	GetISINBySymbol(symbol string) (string, error)
}

// ScoreRepository handles score database operations for securities.
// Scores are stored in portfolio.db and include various metrics like quality score,
// opportunity score, analyst score, technical indicators (RSI, EMA200), and more.
// After migration 030, ISIN is the primary key (replacing symbol).
//
// The repository can optionally use a ScoreSecurityProvider to resolve symbols to ISINs
// for backward compatibility with code that queries by symbol.
//
// Faithful translation from Python: app/repositories/score.py
type ScoreRepository struct {
	portfolioDB      *sql.DB               // portfolio.db - scores table
	securityProvider ScoreSecurityProvider // Optional provider for symbol -> ISIN lookup
	log              zerolog.Logger        // Structured logger
}

// scoresColumns is the list of columns for the scores table
// Used to avoid SELECT * which can break when schema changes
// Column order must match scanScore() function expectations
// After migration 030: isin is PRIMARY KEY, column order is isin, total_score, ...
const scoresColumns = `isin, total_score, quality_score, opportunity_score, analyst_score, allocation_fit_score,
volatility, cagr_score, consistency_score, history_years, technical_score, stability_score,
sharpe_score, drawdown_score, dividend_bonus, financial_strength_score,
rsi, ema_200, below_52w_high_pct, last_updated`

// NewScoreRepository creates a new score repository without security provider.
// This constructor is for backward compatibility. For new code, prefer
// NewScoreRepositoryWithUniverse to enable GetBySymbol functionality.
//
// Parameters:
//   - portfolioDB: Database connection to portfolio.db
//   - log: Structured logger
//
// Returns:
//   - *ScoreRepository: Repository instance without security provider
func NewScoreRepository(portfolioDB *sql.DB, log zerolog.Logger) *ScoreRepository {
	return &ScoreRepository{
		portfolioDB: portfolioDB,
		log:         log.With().Str("repo", "score").Logger(),
	}
}

// NewScoreRepositoryWithUniverse creates a new score repository with security provider.
// This enables GetBySymbol functionality by allowing symbol -> ISIN lookup.
// This is the recommended constructor for code that needs to query scores by symbol.
//
// Parameters:
//   - portfolioDB: Database connection to portfolio.db
//   - securityProvider: Provider for symbol -> ISIN lookup (can be SecurityRepository adapter)
//   - log: Structured logger
//
// Returns:
//   - *ScoreRepository: Repository instance with security provider
func NewScoreRepositoryWithUniverse(portfolioDB *sql.DB, securityProvider ScoreSecurityProvider, log zerolog.Logger) *ScoreRepository {
	return &ScoreRepository{
		portfolioDB:      portfolioDB,
		securityProvider: securityProvider,
		log:              log.With().Str("repo", "score").Logger(),
	}
}

// GetByISIN returns a score by ISIN (primary method).
// ISIN is the primary key for scores after migration 030.
//
// Parameters:
//   - isin: Security ISIN
//
// Returns:
//   - *SecurityScore: Score object if found, nil if not found
//   - error: Error if query fails
func (r *ScoreRepository) GetByISIN(isin string) (*SecurityScore, error) {
	query := "SELECT " + scoresColumns + " FROM scores WHERE isin = ?"

	// Normalize ISIN to uppercase and trim whitespace
	rows, err := r.portfolioDB.Query(query, strings.ToUpper(strings.TrimSpace(isin)))
	if err != nil {
		return nil, fmt.Errorf("failed to query score by ISIN: %w", err)
	}
	defer rows.Close()

	if !rows.Next() {
		return nil, nil // Score not found
	}

	score, err := r.scanScore(rows)
	if err != nil {
		return nil, fmt.Errorf("failed to scan score: %w", err)
	}

	return &score, nil
}

// GetBySymbol returns a score by symbol (helper method - looks up ISIN first).
// This method requires a securityProvider to resolve symbol -> ISIN.
// If securityProvider is not configured, returns an error directing the caller
// to use GetByISIN directly or use NewScoreRepositoryWithUniverse.
//
// Parameters:
//   - symbol: Security symbol
//
// Returns:
//   - *SecurityScore: Score object if found, nil if security not found
//   - error: Error if securityProvider is missing or query fails
func (r *ScoreRepository) GetBySymbol(symbol string) (*SecurityScore, error) {
	if r.securityProvider == nil {
		return nil, fmt.Errorf("GetBySymbol requires securityProvider - use NewScoreRepositoryWithUniverse or GetByISIN directly")
	}

	// Lookup ISIN from security provider (normalize symbol first)
	isin, err := r.securityProvider.GetISINBySymbol(strings.ToUpper(strings.TrimSpace(symbol)))
	if err != nil {
		return nil, nil // Security not found, so no score
	}

	if isin == "" {
		return nil, nil // No ISIN found, so no score
	}

	// Query score by ISIN (primary key)
	return r.GetByISIN(isin)
}

// GetByIdentifier returns a score by symbol or ISIN (smart lookup).
// This method automatically detects whether the identifier is an ISIN or symbol:
// - If identifier is 12 characters and starts with 2 letters, tries ISIN lookup first
// - Otherwise, falls back to symbol lookup (requires securityProvider)
// This is useful for user input where the format may be ambiguous.
//
// Parameters:
//   - identifier: Security symbol or ISIN
//
// Returns:
//   - *SecurityScore: Score object if found, nil if not found
//   - error: Error if query fails
//
// Faithful translation of Python: async def get_by_identifier(self, identifier: str) -> Optional[SecurityScore]
func (r *ScoreRepository) GetByIdentifier(identifier string) (*SecurityScore, error) {
	identifier = strings.ToUpper(strings.TrimSpace(identifier))

	// Check if it looks like an ISIN (12 chars, starts with 2 letters)
	// ISIN format: 2-letter country code + 9 alphanumeric + 1 check digit
	if len(identifier) == 12 && len(identifier) >= 2 {
		firstTwo := identifier[:2]
		if (firstTwo[0] >= 'A' && firstTwo[0] <= 'Z') && (firstTwo[1] >= 'A' && firstTwo[1] <= 'Z') {
			// Try ISIN lookup first (more specific, less ambiguous)
			score, err := r.GetByISIN(identifier)
			if err != nil {
				return nil, err
			}
			if score != nil {
				return score, nil
			}
		}
	}

	// Fall back to symbol lookup (requires securityProvider)
	return r.GetBySymbol(identifier)
}

// GetAll returns all scores from the database.
// This method retrieves all security scores regardless of score value.
// Use GetTop() if you only need the highest-scored securities.
//
// Returns:
//   - []SecurityScore: List of all scores (empty slice if none found)
//   - error: Error if query fails
//
// Faithful translation of Python: async def get_all(self) -> List[SecurityScore]
func (r *ScoreRepository) GetAll() ([]SecurityScore, error) {
	query := "SELECT " + scoresColumns + " FROM scores"

	rows, err := r.portfolioDB.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query all scores: %w", err)
	}
	defer rows.Close()

	var scores []SecurityScore
	for rows.Next() {
		score, err := r.scanScore(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan score: %w", err)
		}
		scores = append(scores, score)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating scores: %w", err)
	}

	return scores, nil
}

// GetTop returns top scored securities ordered by total_score descending.
// This is useful for finding the best investment opportunities.
// Only returns securities with a non-null total_score.
//
// Parameters:
//   - limit: Maximum number of scores to return
//
// Returns:
//   - []SecurityScore: List of top scores (ordered by total_score DESC)
//   - error: Error if query fails
//
// Faithful translation of Python: async def get_top(self, limit: int = 10) -> List[SecurityScore]
func (r *ScoreRepository) GetTop(limit int) ([]SecurityScore, error) {
	query := `
		SELECT ` + scoresColumns + ` FROM scores
		WHERE total_score IS NOT NULL
		ORDER BY total_score DESC
		LIMIT ?
	`

	rows, err := r.portfolioDB.Query(query, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query top scores: %w", err)
	}
	defer rows.Close()

	var scores []SecurityScore
	for rows.Next() {
		score, err := r.scanScore(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan score: %w", err)
		}
		scores = append(scores, score)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating scores: %w", err)
	}

	return scores, nil
}

// Upsert inserts or updates a score in the database.
// Uses INSERT OR REPLACE to handle both insert and update in a single operation.
// ISIN is the primary key after migration 030. The score's calculated_at timestamp
// is stored in the last_updated column.
//
// Parameters:
//   - score: SecurityScore object to upsert
//
// Returns:
//   - error: Error if database operation fails
//
// Faithful translation of Python: async def upsert(self, score: SecurityScore) -> None
func (r *ScoreRepository) Upsert(score SecurityScore) error {
	now := time.Now().Unix()
	calculatedAt := now
	if score.CalculatedAt != nil {
		calculatedAt = score.CalculatedAt.Unix()
	}

	// Normalize symbol (for logging purposes - not stored in scores table after migration)
	score.Symbol = strings.ToUpper(strings.TrimSpace(score.Symbol))

	// Begin transaction
	tx, err := r.portfolioDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	// ISIN is required (PRIMARY KEY after migration 030)
	if score.ISIN == "" {
		return fmt.Errorf("ISIN is required for score upsert")
	}

	// INSERT OR REPLACE handles both insert and update
	// If ISIN exists, replaces all columns; if not, inserts new row
	query := `
		INSERT OR REPLACE INTO scores
		(isin, total_score, quality_score, opportunity_score, analyst_score,
		 allocation_fit_score, volatility, cagr_score, consistency_score,
		 history_years, technical_score, stability_score,
		 sharpe_score, drawdown_score, dividend_bonus, financial_strength_score,
		 rsi, ema_200, below_52w_high_pct, last_updated)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	_, err = tx.Exec(query,
		strings.ToUpper(strings.TrimSpace(score.ISIN)), // Normalize ISIN
		nullFloat64(score.TotalScore),                  // Convert to sql.NullFloat64 (NULL if 0)
		nullFloat64(score.QualityScore),
		nullFloat64(score.OpportunityScore),
		nullFloat64(score.AnalystScore),
		nullFloat64(score.AllocationFitScore),
		nullFloat64(score.Volatility),
		nullFloat64(score.CAGRScore),
		nullFloat64(score.ConsistencyScore),
		nullInt64(score.HistoryYears), // Convert to sql.NullInt64 (NULL if 0)
		nullFloat64(score.TechnicalScore),
		nullFloat64(score.StabilityScore),
		nullFloat64(score.SharpeScore),
		nullFloat64(score.DrawdownScore),
		nullFloat64(score.DividendBonus),
		nullFloat64(score.FinancialStrengthScore),
		nullFloat64(score.RSI),             // Technical indicator: Relative Strength Index
		nullFloat64(score.EMA200),          // Technical indicator: 200-day Exponential Moving Average
		nullFloat64(score.Below52wHighPct), // Percentage below 52-week high
		calculatedAt,                       // Unix timestamp of calculation
	)
	if err != nil {
		return fmt.Errorf("failed to upsert score: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	r.log.Info().Str("isin", score.ISIN).Str("symbol", score.Symbol).Msg("Score upserted")
	return nil
}

// Delete deletes a score by ISIN.
// After migration 030, ISIN is the primary key (replacing symbol).
// This operation is idempotent - it does not error if the score doesn't exist.
//
// Parameters:
//   - isin: Security ISIN
//
// Returns:
//   - error: Error if database operation fails
func (r *ScoreRepository) Delete(isin string) error {
	isin = strings.ToUpper(strings.TrimSpace(isin))

	// Begin transaction
	tx, err := r.portfolioDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	query := "DELETE FROM scores WHERE isin = ?"
	result, err := tx.Exec(query, isin)
	if err != nil {
		return fmt.Errorf("failed to delete score: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Info().Str("isin", isin).Int64("rows_affected", rowsAffected).Msg("Score deleted")
	return nil
}

// DeleteAll deletes all scores from the database.
// This is a destructive operation typically used for testing or complete reset.
// Use with caution in production.
//
// Returns:
//   - error: Error if database operation fails
//
// Faithful translation of Python: async def delete_all(self) -> None
func (r *ScoreRepository) DeleteAll() error {
	// Begin transaction
	tx, err := r.portfolioDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	query := "DELETE FROM scores"
	result, err := tx.Exec(query)
	if err != nil {
		return fmt.Errorf("failed to delete all scores: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Warn().Int64("rows_affected", rowsAffected).Msg("All scores deleted")
	return nil
}

// scanScore scans a database row into a SecurityScore struct.
// This is an internal helper method used by all query methods.
// It handles nullable fields by using sql.NullFloat64 and sql.NullInt64 types.
//
// Column order after migration 030:
//
//	isin, total_score, quality_score, opportunity_score, analyst_score,
//	allocation_fit_score, volatility, cagr_score, consistency_score, history_years,
//	technical_score, stability_score, sharpe_score, drawdown_score, dividend_bonus,
//	financial_strength_score, rsi, ema_200, below_52w_high_pct, last_updated
//
// Parameters:
//   - rows: Database rows iterator (must be positioned on a valid row)
//
// Returns:
//   - SecurityScore: Scanned score object
//   - error: Error if scanning fails
func (r *ScoreRepository) scanScore(rows *sql.Rows) (SecurityScore, error) {
	var score SecurityScore
	var isin sql.NullString
	var totalScore, qualityScore, opportunityScore, analystScore, allocationFitScore sql.NullFloat64
	var volatility, cagrScore, consistencyScore sql.NullFloat64
	var historyYears sql.NullInt64
	var technicalScore, stabilityScore sql.NullFloat64
	var sharpeScore, drawdownScore, dividendBonus sql.NullFloat64
	var financialStrengthScore sql.NullFloat64
	var rsi, ema200, below52wHighPct sql.NullFloat64
	var lastUpdated sql.NullInt64

	err := rows.Scan(
		&isin, // isin (PRIMARY KEY)
		&totalScore,
		&qualityScore,
		&opportunityScore,
		&analystScore,
		&allocationFitScore,
		&volatility,
		&cagrScore,
		&consistencyScore,
		&historyYears,
		&technicalScore,
		&stabilityScore,
		&sharpeScore,
		&drawdownScore,
		&dividendBonus,
		&financialStrengthScore,
		&rsi,
		&ema200,
		&below52wHighPct,
		&lastUpdated,
	)
	if err != nil {
		return score, err
	}

	// Handle nullable fields
	if totalScore.Valid {
		score.TotalScore = totalScore.Float64
	}
	if qualityScore.Valid {
		score.QualityScore = qualityScore.Float64
	}
	if opportunityScore.Valid {
		score.OpportunityScore = opportunityScore.Float64
	}
	if analystScore.Valid {
		score.AnalystScore = analystScore.Float64
	}
	if allocationFitScore.Valid {
		score.AllocationFitScore = allocationFitScore.Float64
	}
	if volatility.Valid {
		score.Volatility = volatility.Float64
	}
	if cagrScore.Valid {
		score.CAGRScore = cagrScore.Float64
	}
	if consistencyScore.Valid {
		score.ConsistencyScore = consistencyScore.Float64
	}
	if historyYears.Valid {
		score.HistoryYears = float64(historyYears.Int64)
	}
	if technicalScore.Valid {
		score.TechnicalScore = technicalScore.Float64
	}
	if stabilityScore.Valid {
		score.StabilityScore = stabilityScore.Float64
	}
	if sharpeScore.Valid {
		score.SharpeScore = sharpeScore.Float64
	}
	if drawdownScore.Valid {
		score.DrawdownScore = drawdownScore.Float64
	}
	if dividendBonus.Valid {
		score.DividendBonus = dividendBonus.Float64
	}
	if financialStrengthScore.Valid {
		score.FinancialStrengthScore = financialStrengthScore.Float64
	}
	if rsi.Valid {
		score.RSI = rsi.Float64
	}
	if ema200.Valid {
		score.EMA200 = ema200.Float64
	}
	if below52wHighPct.Valid {
		score.Below52wHighPct = below52wHighPct.Float64
	}
	// Map last_updated (Unix timestamp) to calculated_at
	if lastUpdated.Valid {
		t := time.Unix(lastUpdated.Int64, 0).UTC()
		score.CalculatedAt = &t
	}

	// Handle ISIN
	if isin.Valid {
		score.ISIN = isin.String
	}

	// Note: Symbol is not stored in scores table after migration
	// It should be looked up from securities table using ISIN if needed
	// For backward compatibility, we leave Symbol empty (caller should populate from security)

	return score, nil
}

// nullInt64 converts a float64 to sql.NullInt64
// Returns NULL (Valid: false) if value is 0.0
func nullInt64(f float64) sql.NullInt64 {
	if f == 0 {
		return sql.NullInt64{Valid: false}
	}
	return sql.NullInt64{Int64: int64(f), Valid: true}
}
