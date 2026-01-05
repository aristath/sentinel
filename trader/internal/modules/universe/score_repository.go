package universe

import (
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/rs/zerolog"
)

// ScoreRepository handles score database operations
// Faithful translation from Python: app/repositories/score.py
type ScoreRepository struct {
	portfolioDB *sql.DB // portfolio.db - scores table
	log         zerolog.Logger
}

// scoresColumns is the list of columns for the scores table
// Used to avoid SELECT * which can break when schema changes
// Column order must match scanScore() function expectations
// Order matches database schema (migration 004 + 029):
// symbol, total_score, quality_score, opportunity_score, analyst_score, allocation_fit_score,
// volatility, cagr_score, consistency_score, history_years, technical_score, fundamental_score,
// sharpe_score, drawdown_score, dividend_bonus, financial_strength_score,
// rsi, ema_200, below_52w_high_pct, last_updated
const scoresColumns = `symbol, total_score, quality_score, opportunity_score, analyst_score, allocation_fit_score,
volatility, cagr_score, consistency_score, history_years, technical_score, fundamental_score,
sharpe_score, drawdown_score, dividend_bonus, financial_strength_score,
rsi, ema_200, below_52w_high_pct, last_updated`

// NewScoreRepository creates a new score repository
func NewScoreRepository(portfolioDB *sql.DB, log zerolog.Logger) *ScoreRepository {
	return &ScoreRepository{
		portfolioDB: portfolioDB,
		log:         log.With().Str("repo", "score").Logger(),
	}
}

// GetBySymbol returns a score by symbol
// Faithful translation of Python: async def get_by_symbol(self, symbol: str) -> Optional[SecurityScore]
func (r *ScoreRepository) GetBySymbol(symbol string) (*SecurityScore, error) {
	query := "SELECT " + scoresColumns + " FROM scores WHERE symbol = ?"

	rows, err := r.portfolioDB.Query(query, strings.ToUpper(strings.TrimSpace(symbol)))
	if err != nil {
		return nil, fmt.Errorf("failed to query score by symbol: %w", err)
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

// GetByIdentifier returns a score by symbol or ISIN
// Faithful translation of Python: async def get_by_identifier(self, identifier: str) -> Optional[SecurityScore]
func (r *ScoreRepository) GetByIdentifier(identifier string) (*SecurityScore, error) {
	identifier = strings.ToUpper(strings.TrimSpace(identifier))

	// For now, just use symbol (ISIN lookup would require JOIN with securities table)
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
	now := time.Now().Format(time.RFC3339)
	calculatedAt := now
	if score.CalculatedAt != nil {
		calculatedAt = score.CalculatedAt.Format(time.RFC3339)
	}

	// Normalize symbol
	score.Symbol = strings.ToUpper(strings.TrimSpace(score.Symbol))

	// Begin transaction
	tx, err := r.portfolioDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	query := `
		INSERT OR REPLACE INTO scores
		(symbol, quality_score, opportunity_score, analyst_score,
		 allocation_fit_score, cagr_score, consistency_score,
		 financial_strength_score, sharpe_score, drawdown_score,
		 dividend_bonus, rsi, ema_200, below_52w_high_pct,
		 total_score, sell_score, history_years, calculated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	_, err = tx.Exec(query,
		score.Symbol,
		nullFloat64(score.QualityScore),
		nullFloat64(score.OpportunityScore),
		nullFloat64(score.AnalystScore),
		nullFloat64(score.AllocationFitScore),
		nullFloat64(score.CAGRScore),
		nullFloat64(score.ConsistencyScore),
		nullFloat64(score.FinancialStrengthScore),
		nullFloat64(score.SharpeScore),
		nullFloat64(score.DrawdownScore),
		nullFloat64(score.DividendBonus),
		nullFloat64(score.RSI),
		nullFloat64(score.EMA200),
		nullFloat64(score.Below52wHighPct),
		nullFloat64(score.TotalScore),
		nullFloat64(score.SellScore),
		nullFloat64(score.HistoryYears),
		calculatedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to upsert score: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	r.log.Info().Str("symbol", score.Symbol).Msg("Score upserted")
	return nil
}

// Delete deletes score for a symbol
// Faithful translation of Python: async def delete(self, symbol: str) -> None
func (r *ScoreRepository) Delete(symbol string) error {
	symbol = strings.ToUpper(strings.TrimSpace(symbol))

	// Begin transaction
	tx, err := r.portfolioDB.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	query := "DELETE FROM scores WHERE symbol = ?"
	result, err := tx.Exec(query, symbol)
	if err != nil {
		return fmt.Errorf("failed to delete score: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	rowsAffected, _ := result.RowsAffected()
	r.log.Info().Str("symbol", symbol).Int64("rows_affected", rowsAffected).Msg("Score deleted")
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
// Column order matches database schema: symbol, total_score, quality_score, opportunity_score,
// analyst_score, allocation_fit_score, volatility, cagr_score, consistency_score, history_years,
// technical_score, fundamental_score, sharpe_score, drawdown_score, dividend_bonus,
// financial_strength_score, rsi, ema_200, below_52w_high_pct, last_updated
func (r *ScoreRepository) scanScore(rows *sql.Rows) (SecurityScore, error) {
	var score SecurityScore
	var totalScore, qualityScore, opportunityScore, analystScore, allocationFitScore sql.NullFloat64
	var volatility, cagrScore, consistencyScore sql.NullFloat64
	var historyYears sql.NullInt64
	var technicalScore, fundamentalScore sql.NullFloat64
	var sharpeScore, drawdownScore, dividendBonus sql.NullFloat64
	var financialStrengthScore sql.NullFloat64
	var rsi, ema200, below52wHighPct sql.NullFloat64
	var lastUpdated sql.NullString

	err := rows.Scan(
		&score.Symbol,
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
		&fundamentalScore,
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
	if fundamentalScore.Valid {
		score.FundamentalScore = fundamentalScore.Float64
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
	// Map last_updated to calculated_at
	if lastUpdated.Valid && lastUpdated.String != "" {
		if t, err := time.Parse(time.RFC3339, lastUpdated.String); err == nil {
			score.CalculatedAt = &t
		} else {
			// Try parsing as other common formats
			if t, err := time.Parse("2006-01-02 15:04:05", lastUpdated.String); err == nil {
				score.CalculatedAt = &t
			}
		}
	}

	// Normalize symbol
	score.Symbol = strings.ToUpper(strings.TrimSpace(score.Symbol))

	return score, nil
}
