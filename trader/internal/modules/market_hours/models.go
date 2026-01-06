package market_hours

import "time"

// CalendarType represents the calendar system used for Easter calculation
type CalendarType int

const (
	// Gregorian calendar (Western/Catholic)
	Gregorian CalendarType = iota
	// Julian calendar (Orthodox)
	Julian
)

// TradingHours represents regular trading hours for an exchange
type TradingHours struct {
	OpenHour    int // Hour (0-23)
	OpenMinute  int // Minute (0-59)
	CloseHour   int // Hour (0-23)
	CloseMinute int // Minute (0-59)
}

// LunchBreak represents a midday trading break
type LunchBreak struct {
	StartHour   int // Hour (0-23)
	StartMinute int // Minute (0-59)
	EndHour     int // Hour (0-23)
	EndMinute   int // Minute (0-59)
}

// EarlyCloseRule represents a rule for early market closure
type EarlyCloseRule struct {
	// Condition: if this holiday falls on this day of week, close early
	HolidayName string // e.g., "Thanksgiving", "Christmas"
	DayOfWeek   time.Weekday
	CloseHour   int
	CloseMinute int
	// Or: if date matches this pattern
	DatePattern func(time.Time) bool // e.g., day before Thanksgiving
}

// HolidayRuleSet defines holidays for an exchange
type HolidayRuleSet struct {
	// Fixed date holidays (with observance rules)
	FixedDateHolidays []FixedDateHoliday
	// Rule-based holidays (nth weekday, etc.)
	RuleBasedHolidays []RuleBasedHoliday
	// Easter-based holidays
	EasterBasedHolidays []EasterBasedHoliday
}

// FixedDateHoliday represents a holiday on a fixed date
type FixedDateHoliday struct {
	Month int // 1-12
	Day   int // 1-31
	// If true, observe on nearest weekday if falls on weekend
	ObserveOnWeekday bool
}

// RuleBasedHoliday represents a holiday calculated by rule
type RuleBasedHoliday struct {
	Month   int          // 1-12
	Weekday time.Weekday // Monday, Tuesday, etc.
	N       int          // Nth occurrence (1 = first, -1 = last)
}

// EasterBasedHoliday represents a holiday relative to Easter
type EasterBasedHoliday struct {
	DaysOffset int // Days from Easter (negative = before, positive = after)
}

// ExchangeConfig represents configuration for a single exchange
type ExchangeConfig struct {
	Code            string
	Name            string
	TradingHours    TradingHours
	Timezone        *time.Location
	EasterType      CalendarType
	StrictHours     bool // Requires checks for all orders
	LunchBreak      *LunchBreak
	EarlyCloseRules []EarlyCloseRule
	HolidayRules    HolidayRuleSet
}

// MarketStatus represents the current status of a market
type MarketStatus struct {
	Open      bool   `json:"open"`
	Exchange  string `json:"exchange"`
	Timezone  string `json:"timezone"`
	ClosesAt  string `json:"closes_at"`  // Time when market closes (if open)
	OpensAt   string `json:"opens_at"`   // Time when market opens (if closed)
	OpensDate string `json:"opens_date"` // Date when market opens (if closed and opens tomorrow or later)
}
