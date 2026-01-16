package universe

import (
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// ScoreSecurityProvider provides read-only access to securities for ISIN lookups.
type ScoreSecurityProvider interface {
	GetISINBySymbol(symbol string) (string, error)
}

// ScoreRepository handles score database operations
// Faithful translation from Python: app/repositories/score.py
type ScoreRepository struct {
	portfolioDB      *sql.DB // portfolio.db - scores table
	securityProvider ScoreSecurityProvider
	log              zerolog.Logger
}

// scoresColumns is the list of columns for the scores table
// Used to avoid SELECT * which can break when schema changes
// Column order must match scanScore() function expectations
// After migration 030: isin is PRIMARY KEY, column order is isin, total_score, ...
const scoresColumns = `isin, total_score, quality_score, opportunity_score, analyst_score, allocation_fit_score,
volatility, cagr_score, consistency_score, history_years, technical_score, stability_score,
sharpe_score, drawdown_score, dividend_bonus, financial_strength_score,
rsi, ema_200, below_52w_high_pct, last_updated`

// NewScoreRepository creates a new score repository
func NewScoreRepository(portfolioDB *sql.DB, log zerolog.Logger) *ScoreRepository {
	return &ScoreRepository{
		portfolioDB: portfolioDB,
		log:         log.With().Str("repo", "score").Logger(),
	}
}

// NewScoreRepositoryWithUniverse creates a new score repository with security provider
// This is needed for GetBySymbol to lookup ISIN from symbol
func NewScoreRepositoryWithUniverse(portfolioDB *sql.DB, securityProvider ScoreSecurityProvider, log zerolog.Logger) *ScoreRepository {
	return &ScoreRepository{
		portfolioDB:      portfolioDB,
		securityProvider: securityProvider,
		log:              log.With().Str("repo", "score").Logger(),
	}
}

// GetByISIN returns a score by ISIN (primary method)
func (r *ScoreRepository) GetByISIN(isin string) (*SecurityScore, error) {
	query := "SELECT " + scoresColumns + " FROM scores WHERE isin = ?"

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

// GetBySymbol returns a score by symbol (helper method - looks up ISIN first)
// This requires securityProvider to lookup ISIN from symbol
func (r *ScoreRepository) GetBySymbol(symbol string) (*SecurityScore, error) {
	if r.securityProvider == nil {
		return nil, fmt.Errorf("GetBySymbol requires securityProvider - use NewScoreRepositoryWithUniverse or GetByISIN directly")
	}

	// Lookup ISIN from security provider
	isin, err := r.securityProvider.GetISINBySymbol(strings.ToUpper(strings.TrimSpace(symbol)))
	if err != nil {
		return nil, nil // Security not found, so no score
	}

	if isin == "" {
		return nil, nil // No ISIN found, so no score
	}

	if isin == "" {
		return nil, nil // No ISIN found
	}

	// Query score by ISIN
	return r.GetByISIN(isin)
}

// GetByIdentifier returns a score by symbol or ISIN
// Faithful translation of Python: async def get_by_identifier(self, identifier: str) -> Optional[SecurityScore]
func (r *ScoreRepository) GetByIdentifier(identifier string) (*SecurityScore, error) {
	identifier = strings.ToUpper(strings.TrimSpace(identifier))

	// Check if it looks like an ISIN (12 chars, starts with 2 letters)
	if len(identifier) == 12 && len(identifier) >= 2 {
		firstTwo := identifier[:2]
		if (firstTwo[0] >= 'A' && firstTwo[0] <= 'Z') && (firstTwo[1] >= 'A' && firstTwo[1] <= 'Z') {
			// Try ISIN lookup first
			score, err := r.GetByISIN(identifier)
			if err != nil {
				return nil, err
			}
			if score != nil {
				return score, nil
			}
		}
	}

	// Fall back to symbol lookup
	return r.GetBySymbol(identifier)
}

// GetAll returns all scores
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

// GetTop returns top scored securities
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

// Upsert inserts or updates a score
// Faithful translation of Python: async def upsert(self, score: SecurityScore) -> None
func (r *ScoreRepository) Upsert(score SecurityScore) error {
	now := time.Now().Unix()
	calculatedAt := now
	if score.CalculatedAt != nil {
		calculatedAt = score.CalculatedAt.Unix()
	}

	// Normalize symbol
	score.Symbol = strings.ToUpper(strings.TrimSpace(score.Symbol))

	// Begin transaction
	tx, err := r.portfolioDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	// ISIN is required (PRIMARY KEY)
	if score.ISIN == "" {
		return fmt.Errorf("ISIN is required for score upsert")
	}

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
		strings.ToUpper(strings.TrimSpace(score.ISIN)),
		nullFloat64(score.TotalScore),
		nullFloat64(score.QualityScore),
		nullFloat64(score.OpportunityScore),
		nullFloat64(score.AnalystScore),
		nullFloat64(score.AllocationFitScore),
		nullFloat64(score.Volatility),
		nullFloat64(score.CAGRScore),
		nullFloat64(score.ConsistencyScore),
		nullInt64(score.HistoryYears),
		nullFloat64(score.TechnicalScore),
		nullFloat64(score.StabilityScore),
		nullFloat64(score.SharpeScore),
		nullFloat64(score.DrawdownScore),
		nullFloat64(score.DividendBonus),
		nullFloat64(score.FinancialStrengthScore),
		nullFloat64(score.RSI),
		nullFloat64(score.EMA200),
		nullFloat64(score.Below52wHighPct),
		calculatedAt,
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

// Delete deletes score by ISIN
// Changed from symbol to ISIN as primary identifier
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

// DeleteAll deletes all scores
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

// scanScore scans a database row into a SecurityScore struct
// Column order after migration: isin, total_score, quality_score, opportunity_score,
// analyst_score, allocation_fit_score, volatility, cagr_score, consistency_score, history_years,
// technical_score, stability_score, sharpe_score, drawdown_score, dividend_bonus,
// financial_strength_score, rsi, ema_200, below_52w_high_pct, last_updated
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
