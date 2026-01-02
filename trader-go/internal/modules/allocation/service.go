package allocation

import (
	"database/sql"
	"fmt"
	"math"

	"github.com/rs/zerolog"
)

// Position represents a portfolio position (from Python: app/domain/models.py)
type Position struct {
	Symbol         string
	MarketValueEUR float64
}

// PortfolioAllocation represents allocation info (from Python: app/domain/models.py)
type PortfolioAllocation struct {
	Name         string
	TargetPct    float64
	CurrentPct   float64
	CurrentValue float64
	Deviation    float64
}

// PortfolioSummary represents complete portfolio summary (from Python: app/domain/models.py)
type PortfolioSummary struct {
	TotalValue          float64
	CashBalance         float64
	CountryAllocations  []PortfolioAllocation
	IndustryAllocations []PortfolioAllocation
}

// ConcentrationAlertService detects concentration limit alerts
// Faithful translation from Python: app/modules/allocation/services/concentration_alerts.py
type ConcentrationAlertService struct {
	db  *sql.DB
	log zerolog.Logger
}

// NewConcentrationAlertService creates a new concentration alert service
func NewConcentrationAlertService(db *sql.DB, log zerolog.Logger) *ConcentrationAlertService {
	return &ConcentrationAlertService{
		db:  db,
		log: log.With().Str("service", "concentration_alerts").Logger(),
	}
}

// DetectAlerts detects all concentration alerts from portfolio summary
// Faithful translation of Python: async def detect_alerts(self, portfolio_summary: PortfolioSummary) -> List[ConcentrationAlert]
func (s *ConcentrationAlertService) DetectAlerts(summary PortfolioSummary) ([]ConcentrationAlert, error) {
	var alerts []ConcentrationAlert

	if summary.TotalValue <= 0 {
		return alerts, nil
	}

	// Check country allocations
	for _, countryAlloc := range summary.CountryAllocations {
		currentPct := countryAlloc.CurrentPct
		if currentPct >= CountryAlertThreshold {
			severity := s.calculateSeverity(currentPct, MaxCountryConcentration)
			alerts = append(alerts, ConcentrationAlert{
				Type:              "country",
				Name:              countryAlloc.Name,
				CurrentPct:        currentPct,
				LimitPct:          MaxCountryConcentration,
				AlertThresholdPct: CountryAlertThreshold,
				Severity:          severity,
			})
		}
	}

	// Check industry/sector allocations
	for _, industryAlloc := range summary.IndustryAllocations {
		currentPct := industryAlloc.CurrentPct
		if currentPct >= SectorAlertThreshold {
			severity := s.calculateSeverity(currentPct, MaxSectorConcentration)
			alerts = append(alerts, ConcentrationAlert{
				Type:              "sector",
				Name:              industryAlloc.Name,
				CurrentPct:        currentPct,
				LimitPct:          MaxSectorConcentration,
				AlertThresholdPct: SectorAlertThreshold,
				Severity:          severity,
			})
		}
	}

	// Check position concentrations
	positions, err := s.getAllPositions()
	if err != nil {
		return nil, fmt.Errorf("failed to get positions: %w", err)
	}

	for _, position := range positions {
		if position.MarketValueEUR > 0 && summary.TotalValue > 0 {
			positionPct := position.MarketValueEUR / summary.TotalValue
			if positionPct >= PositionAlertThreshold {
				severity := s.calculateSeverity(positionPct, MaxPositionConcentration)
				alerts = append(alerts, ConcentrationAlert{
					Type:              "position",
					Name:              position.Symbol,
					CurrentPct:        positionPct,
					LimitPct:          MaxPositionConcentration,
					AlertThresholdPct: PositionAlertThreshold,
					Severity:          severity,
				})
			}
		}
	}

	return alerts, nil
}

// calculateSeverity calculates alert severity based on percentage of limit
// Faithful translation of Python: def _calculate_severity(self, current_pct: float, limit_pct: float) -> str
// Returns "warning" if 80-90% of limit, "critical" if 90-100% of limit
func (s *ConcentrationAlertService) calculateSeverity(currentPct, limitPct float64) string {
	if limitPct <= 0 {
		return "warning"
	}

	pctOfLimit := currentPct / limitPct
	if pctOfLimit >= 0.90 {
		return "critical"
	}
	return "warning"
}

// getAllPositions retrieves all positions from database
func (s *ConcentrationAlertService) getAllPositions() ([]Position, error) {
	query := `
		SELECT symbol, market_value_eur
		FROM positions
		WHERE market_value_eur > 0
	`

	rows, err := s.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to query positions: %w", err)
	}
	defer rows.Close()

	var positions []Position
	for rows.Next() {
		var pos Position
		if err := rows.Scan(&pos.Symbol, &pos.MarketValueEUR); err != nil {
			return nil, fmt.Errorf("failed to scan position: %w", err)
		}
		positions = append(positions, pos)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating positions: %w", err)
	}

	return positions, nil
}

// CalculateDeviationStatus determines if allocation is underweight, overweight, or balanced
// Faithful translation of Python logic from allocation API
func CalculateDeviationStatus(deviation float64) string {
	if deviation < -0.02 {
		return "underweight"
	} else if deviation > 0.02 {
		return "overweight"
	}
	return "balanced"
}

// CalculateNeed returns the need value (max of 0 or negative deviation)
// Faithful translation of Python: max(0, -a.deviation)
func CalculateNeed(deviation float64) float64 {
	return math.Max(0, -deviation)
}
