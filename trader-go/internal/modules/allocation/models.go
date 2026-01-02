package allocation

import "time"

// AllocationTarget represents target allocation for country_group or industry_group
// Faithful translation from Python: app/modules/allocation/domain/models.py
type AllocationTarget struct {
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
	Type      string    `json:"type"`
	Name      string    `json:"name"`
	ID        int64     `json:"id"`
	TargetPct float64   `json:"target_pct"`
}

// ConcentrationAlert represents alert for approaching concentration limit
// Faithful translation from Python: app/modules/allocation/services/concentration_alerts.py
type ConcentrationAlert struct {
	Type              string  `json:"type"`
	Name              string  `json:"name"`
	Severity          string  `json:"severity"`
	CurrentPct        float64 `json:"current_pct"`
	LimitPct          float64 `json:"limit_pct"`
	AlertThresholdPct float64 `json:"alert_threshold_pct"`
}

// AllocationInfo represents allocation status for display
type AllocationInfo struct {
	Name         string  `json:"name"`
	TargetPct    float64 `json:"target_pct"`
	CurrentPct   float64 `json:"current_pct"`
	CurrentValue float64 `json:"current_value"`
	Deviation    float64 `json:"deviation"`
}

// DeviationInfo represents allocation deviation for a group
type DeviationInfo struct {
	Status    string  `json:"status"`
	Deviation float64 `json:"deviation"`
	Need      float64 `json:"need"`
}

// CountryGroup represents a country group definition
type CountryGroup struct {
	GroupName    string   `json:"group_name"`
	CountryNames []string `json:"country_names"`
}

// IndustryGroup represents an industry group definition
type IndustryGroup struct {
	GroupName     string   `json:"group_name"`
	IndustryNames []string `json:"industry_names"`
}

// Concentration limit constants
// Faithful translation from Python: app/modules/scoring/domain/constants.py
const (
	MaxCountryConcentration  = 0.35 // 35% max per country
	MaxSectorConcentration   = 0.30 // 30% max per sector
	MaxPositionConcentration = 0.15 // 15% max per position

	CountryAlertThreshold  = 0.28 // Alert at 28% (80% of 35%)
	SectorAlertThreshold   = 0.24 // Alert at 24% (80% of 30%)
	PositionAlertThreshold = 0.12 // Alert at 12% (80% of 15%)
)
