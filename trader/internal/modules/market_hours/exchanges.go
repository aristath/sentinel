package market_hours

import (
	"strings"
	"time"
)

// Exchange name mapping from database fullExchangeName to exchange code
var exchangeNameToCode = map[string]string{
	"Amsterdam":  "XAMS",
	"Athens":     "ASEX",
	"Copenhagen": "XCSE",
	"HKSE":       "XHKG",
	"Hong Kong":  "XHKG", // Alternative name
	"LSE":        "XLON",
	"London":     "XLON", // Alternative name
	"Milan":      "XMIL",
	"NasdaqCM":   "XNAS",
	"NasdaqGS":   "XNAS",
	"NYSE":       "XNYS",
	"New York":   "XNYS", // Alternative name
	"Paris":      "XPAR",
	"Shenzhen":   "XSHG",
	"Shanghai":   "XSHG", // Alternative name (Shanghai Stock Exchange)
	"XETRA":      "XETR",
	"Frankfurt":  "XETR", // Alternative name
	"Tokyo":      "XTSE", // Tokyo Stock Exchange
	"Sydney":     "XASX", // Australian Securities Exchange
	// Legacy mappings
	"NASDAQ": "XNAS",
	"XETR":   "XETR",
	"XHKG":   "XHKG",
	"TSE":    "XTSE",
	"ASX":    "XASX",
}

// Exchanges that require strict market hours checks for all orders
var strictMarketHoursExchanges = map[string]bool{
	"XHKG": true,
	"XSHG": true,
	"XTSE": true,
	"XASX": true,
	"ASX":  true,
	"TSE":  true,
	// Also check by database name
	"HKSE":     true,
	"Shenzhen": true,
	"Tokyo":    true,
	"Sydney":   true,
}

// GetExchangeCode returns the exchange code for a database exchange name
func GetExchangeCode(fullExchangeName string) string {
	// Normalize input (trim whitespace)
	normalized := strings.TrimSpace(fullExchangeName)

	// Check if it's already a valid code
	if _, exists := exchangeConfigs[normalized]; exists {
		return normalized
	}

	// Look up in mapping (case-sensitive first)
	if code, ok := exchangeNameToCode[normalized]; ok {
		return code
	}

	// Try case-insensitive lookup
	for name, code := range exchangeNameToCode {
		if strings.EqualFold(normalized, name) {
			return code
		}
	}

	// Default to XNYS (fail-safe)
	return "XNYS"
}

// getExchangeConfig returns the configuration for an exchange code
func getExchangeConfig(exchangeCode string) *ExchangeConfig {
	if config, ok := exchangeConfigs[exchangeCode]; ok {
		return &config
	}
	// Return default (XNYS) if not found
	if config, ok := exchangeConfigs["XNYS"]; ok {
		return &config
	}
	return nil
}

// exchangeConfigs contains all exchange configurations
var exchangeConfigs = map[string]ExchangeConfig{
	"XNYS": {
		Code: "XNYS",
		Name: "New York Stock Exchange",
		TradingHours: TradingHours{
			OpenHour:    9,
			OpenMinute:  30,
			CloseHour:   16,
			CloseMinute: 0,
		},
		Timezone:    mustLoadLocation("America/New_York"),
		EasterType:  Gregorian,
		StrictHours: false,
		LunchBreak:  nil,
		EarlyCloseRules: []EarlyCloseRule{
			{
				HolidayName: "Thanksgiving",
				DayOfWeek:   time.Wednesday, // Day before Thanksgiving
				CloseHour:   13,
				CloseMinute: 0,
				DatePattern: func(t time.Time) bool {
					// Day before Thanksgiving (4th Thursday in November)
					// t is already in market timezone, compare date parts only
					thanksgiving := findNthWeekday(t.Year(), 11, time.Thursday, 4)
					dayBefore := thanksgiving.AddDate(0, 0, -1)
					return t.Year() == dayBefore.Year() && t.Month() == dayBefore.Month() && t.Day() == dayBefore.Day()
				},
			},
			{
				HolidayName: "Christmas",
				DayOfWeek:   time.Wednesday, // Day before Christmas
				CloseHour:   13,
				CloseMinute: 0,
				DatePattern: func(t time.Time) bool {
					// Day before Christmas (Dec 24)
					// t is already in market timezone, compare date parts only
					return t.Month() == 12 && t.Day() == 24
				},
			},
			{
				HolidayName: "Independence Day",
				DayOfWeek:   time.Thursday, // July 3 if July 4 is Friday
				CloseHour:   13,
				CloseMinute: 0,
				DatePattern: func(t time.Time) bool {
					// July 3 if July 4 is Friday
					// t is already in market timezone
					if t.Month() == 7 && t.Day() == 3 {
						// Check if July 4 is Friday
						july4 := time.Date(t.Year(), 7, 4, 0, 0, 0, 0, t.Location())
						return july4.Weekday() == time.Friday
					}
					return false
				},
			},
		},
		HolidayRules: HolidayRuleSet{
			FixedDateHolidays: []FixedDateHoliday{
				{Month: 1, Day: 1, ObserveOnWeekday: true},   // New Year's Day
				{Month: 6, Day: 19, ObserveOnWeekday: true},  // Juneteenth
				{Month: 7, Day: 4, ObserveOnWeekday: true},   // Independence Day
				{Month: 12, Day: 25, ObserveOnWeekday: true}, // Christmas
			},
			RuleBasedHolidays: []RuleBasedHoliday{
				{Month: 1, Weekday: time.Monday, N: 3},    // MLK Day
				{Month: 2, Weekday: time.Monday, N: 3},    // Presidents Day
				{Month: 5, Weekday: time.Monday, N: -1},   // Memorial Day (last)
				{Month: 9, Weekday: time.Monday, N: 1},    // Labor Day
				{Month: 11, Weekday: time.Thursday, N: 4}, // Thanksgiving
			},
			EasterBasedHolidays: []EasterBasedHoliday{
				{DaysOffset: -2}, // Good Friday
			},
		},
	},
	"XNAS": {
		Code: "XNAS",
		Name: "NASDAQ",
		TradingHours: TradingHours{
			OpenHour:    9,
			OpenMinute:  30,
			CloseHour:   16,
			CloseMinute: 0,
		},
		Timezone:    mustLoadLocation("America/New_York"),
		EasterType:  Gregorian,
		StrictHours: false,
		LunchBreak:  nil,
		EarlyCloseRules: []EarlyCloseRule{
			{
				HolidayName: "Thanksgiving",
				DayOfWeek:   time.Wednesday,
				CloseHour:   13,
				CloseMinute: 0,
				DatePattern: func(t time.Time) bool {
					thanksgiving := findNthWeekday(t.Year(), 11, time.Thursday, 4)
					dayBefore := thanksgiving.AddDate(0, 0, -1)
					return t.Year() == dayBefore.Year() && t.Month() == dayBefore.Month() && t.Day() == dayBefore.Day()
				},
			},
			{
				HolidayName: "Christmas",
				DayOfWeek:   time.Wednesday,
				CloseHour:   13,
				CloseMinute: 0,
				DatePattern: func(t time.Time) bool {
					return t.Month() == 12 && t.Day() == 24
				},
			},
			{
				HolidayName: "Independence Day",
				DayOfWeek:   time.Thursday,
				CloseHour:   13,
				CloseMinute: 0,
				DatePattern: func(t time.Time) bool {
					if t.Month() == 7 && t.Day() == 3 {
						july4 := time.Date(t.Year(), 7, 4, 0, 0, 0, 0, t.Location())
						return july4.Weekday() == time.Friday
					}
					return false
				},
			},
		},
		HolidayRules: HolidayRuleSet{
			FixedDateHolidays: []FixedDateHoliday{
				{Month: 1, Day: 1, ObserveOnWeekday: true},
				{Month: 6, Day: 19, ObserveOnWeekday: true},
				{Month: 7, Day: 4, ObserveOnWeekday: true},
				{Month: 12, Day: 25, ObserveOnWeekday: true},
			},
			RuleBasedHolidays: []RuleBasedHoliday{
				{Month: 1, Weekday: time.Monday, N: 3},
				{Month: 2, Weekday: time.Monday, N: 3},
				{Month: 5, Weekday: time.Monday, N: -1},
				{Month: 9, Weekday: time.Monday, N: 1},
				{Month: 11, Weekday: time.Thursday, N: 4},
			},
			EasterBasedHolidays: []EasterBasedHoliday{
				{DaysOffset: -2},
			},
		},
	},
	"XETR": {
		Code: "XETR",
		Name: "XETRA (Frankfurt)",
		TradingHours: TradingHours{
			OpenHour:    9,
			OpenMinute:  0,
			CloseHour:   17,
			CloseMinute: 30,
		},
		Timezone:        mustLoadLocation("Europe/Berlin"),
		EasterType:      Gregorian,
		StrictHours:     false,
		LunchBreak:      nil,
		EarlyCloseRules: []EarlyCloseRule{},
		HolidayRules: HolidayRuleSet{
			FixedDateHolidays: []FixedDateHoliday{
				{Month: 1, Day: 1, ObserveOnWeekday: false},   // New Year's Day
				{Month: 5, Day: 1, ObserveOnWeekday: false},   // Labor Day
				{Month: 10, Day: 3, ObserveOnWeekday: false},  // German Unity Day
				{Month: 12, Day: 25, ObserveOnWeekday: false}, // Christmas
				{Month: 12, Day: 26, ObserveOnWeekday: false}, // Boxing Day
			},
			RuleBasedHolidays: []RuleBasedHoliday{},
			EasterBasedHolidays: []EasterBasedHoliday{
				{DaysOffset: -2}, // Good Friday
				{DaysOffset: 1},  // Easter Monday
			},
		},
	},
	"XLON": {
		Code: "XLON",
		Name: "London Stock Exchange",
		TradingHours: TradingHours{
			OpenHour:    8,
			OpenMinute:  0,
			CloseHour:   16,
			CloseMinute: 30,
		},
		Timezone:        mustLoadLocation("Europe/London"),
		EasterType:      Gregorian,
		StrictHours:     false,
		LunchBreak:      nil,
		EarlyCloseRules: []EarlyCloseRule{},
		HolidayRules: HolidayRuleSet{
			FixedDateHolidays: []FixedDateHoliday{
				{Month: 1, Day: 1, ObserveOnWeekday: false},   // New Year's Day
				{Month: 12, Day: 25, ObserveOnWeekday: false}, // Christmas
				{Month: 12, Day: 26, ObserveOnWeekday: false}, // Boxing Day
			},
			RuleBasedHolidays: []RuleBasedHoliday{
				{Month: 5, Weekday: time.Monday, N: 1},  // Early May Bank Holiday
				{Month: 5, Weekday: time.Monday, N: -1}, // Spring Bank Holiday (last Monday)
				{Month: 8, Weekday: time.Monday, N: -1}, // Summer Bank Holiday (last Monday)
			},
			EasterBasedHolidays: []EasterBasedHoliday{
				{DaysOffset: -2}, // Good Friday
				{DaysOffset: 1},  // Easter Monday
			},
		},
	},
	"XPAR": {
		Code: "XPAR",
		Name: "Euronext Paris",
		TradingHours: TradingHours{
			OpenHour:    9,
			OpenMinute:  0,
			CloseHour:   17,
			CloseMinute: 30,
		},
		Timezone:        mustLoadLocation("Europe/Paris"),
		EasterType:      Gregorian,
		StrictHours:     false,
		LunchBreak:      nil,
		EarlyCloseRules: []EarlyCloseRule{},
		HolidayRules: HolidayRuleSet{
			FixedDateHolidays: []FixedDateHoliday{
				{Month: 1, Day: 1, ObserveOnWeekday: false},   // New Year's Day
				{Month: 5, Day: 1, ObserveOnWeekday: false},   // Labor Day
				{Month: 5, Day: 8, ObserveOnWeekday: false},   // Victory Day
				{Month: 7, Day: 14, ObserveOnWeekday: false},  // Bastille Day
				{Month: 8, Day: 15, ObserveOnWeekday: false},  // Assumption
				{Month: 11, Day: 1, ObserveOnWeekday: false},  // All Saints' Day
				{Month: 11, Day: 11, ObserveOnWeekday: false}, // Armistice Day
				{Month: 12, Day: 25, ObserveOnWeekday: false}, // Christmas
			},
			RuleBasedHolidays: []RuleBasedHoliday{},
			EasterBasedHolidays: []EasterBasedHoliday{
				{DaysOffset: -2}, // Good Friday
				{DaysOffset: 1},  // Easter Monday
			},
		},
	},
	"XMIL": {
		Code: "XMIL",
		Name: "Borsa Italiana (Milan)",
		TradingHours: TradingHours{
			OpenHour:    9,
			OpenMinute:  0,
			CloseHour:   17,
			CloseMinute: 30,
		},
		Timezone:        mustLoadLocation("Europe/Rome"),
		EasterType:      Gregorian,
		StrictHours:     false,
		LunchBreak:      nil,
		EarlyCloseRules: []EarlyCloseRule{},
		HolidayRules: HolidayRuleSet{
			FixedDateHolidays: []FixedDateHoliday{
				{Month: 1, Day: 1, ObserveOnWeekday: false},   // New Year's Day
				{Month: 1, Day: 6, ObserveOnWeekday: false},   // Epiphany
				{Month: 4, Day: 25, ObserveOnWeekday: false},  // Liberation Day
				{Month: 5, Day: 1, ObserveOnWeekday: false},   // Labor Day
				{Month: 6, Day: 2, ObserveOnWeekday: false},   // Republic Day
				{Month: 8, Day: 15, ObserveOnWeekday: false},  // Ferragosto
				{Month: 11, Day: 1, ObserveOnWeekday: false},  // All Saints' Day
				{Month: 12, Day: 8, ObserveOnWeekday: false},  // Immaculate Conception
				{Month: 12, Day: 25, ObserveOnWeekday: false}, // Christmas
				{Month: 12, Day: 26, ObserveOnWeekday: false}, // St. Stephen's Day
			},
			RuleBasedHolidays: []RuleBasedHoliday{},
			EasterBasedHolidays: []EasterBasedHoliday{
				{DaysOffset: -2}, // Good Friday
				{DaysOffset: 1},  // Easter Monday
			},
		},
	},
	"XAMS": {
		Code: "XAMS",
		Name: "Euronext Amsterdam",
		TradingHours: TradingHours{
			OpenHour:    9,
			OpenMinute:  0,
			CloseHour:   17,
			CloseMinute: 30,
		},
		Timezone:        mustLoadLocation("Europe/Amsterdam"),
		EasterType:      Gregorian,
		StrictHours:     false,
		LunchBreak:      nil,
		EarlyCloseRules: []EarlyCloseRule{},
		HolidayRules: HolidayRuleSet{
			FixedDateHolidays: []FixedDateHoliday{
				{Month: 1, Day: 1, ObserveOnWeekday: false},   // New Year's Day
				{Month: 4, Day: 27, ObserveOnWeekday: false},  // King's Day
				{Month: 5, Day: 5, ObserveOnWeekday: false},   // Liberation Day
				{Month: 12, Day: 25, ObserveOnWeekday: false}, // Christmas
				{Month: 12, Day: 26, ObserveOnWeekday: false}, // Boxing Day
			},
			RuleBasedHolidays: []RuleBasedHoliday{},
			EasterBasedHolidays: []EasterBasedHoliday{
				{DaysOffset: -2}, // Good Friday
				{DaysOffset: 1},  // Easter Monday
			},
		},
	},
	"XCSE": {
		Code: "XCSE",
		Name: "Copenhagen Stock Exchange",
		TradingHours: TradingHours{
			OpenHour:    9,
			OpenMinute:  0,
			CloseHour:   17,
			CloseMinute: 0,
		},
		Timezone:        mustLoadLocation("Europe/Copenhagen"),
		EasterType:      Gregorian,
		StrictHours:     false,
		LunchBreak:      nil,
		EarlyCloseRules: []EarlyCloseRule{},
		HolidayRules: HolidayRuleSet{
			FixedDateHolidays: []FixedDateHoliday{
				{Month: 1, Day: 1, ObserveOnWeekday: false},   // New Year's Day
				{Month: 5, Day: 1, ObserveOnWeekday: false},   // Labor Day
				{Month: 6, Day: 5, ObserveOnWeekday: false},   // Constitution Day
				{Month: 12, Day: 25, ObserveOnWeekday: false}, // Christmas
				{Month: 12, Day: 26, ObserveOnWeekday: false}, // Boxing Day
			},
			RuleBasedHolidays: []RuleBasedHoliday{},
			EasterBasedHolidays: []EasterBasedHoliday{
				{DaysOffset: -2}, // Good Friday
				{DaysOffset: 1},  // Easter Monday
			},
		},
	},
	"ASEX": {
		Code: "ASEX",
		Name: "Athens Stock Exchange",
		TradingHours: TradingHours{
			OpenHour:    10,
			OpenMinute:  0,
			CloseHour:   15,
			CloseMinute: 20,
		},
		Timezone:        mustLoadLocation("Europe/Athens"),
		EasterType:      Julian, // IMPORTANT: Orthodox Easter
		StrictHours:     false,
		LunchBreak:      nil,
		EarlyCloseRules: []EarlyCloseRule{},
		HolidayRules: HolidayRuleSet{
			FixedDateHolidays: []FixedDateHoliday{
				{Month: 1, Day: 1, ObserveOnWeekday: false},   // New Year's Day
				{Month: 1, Day: 6, ObserveOnWeekday: false},   // Epiphany
				{Month: 3, Day: 25, ObserveOnWeekday: false},  // Independence Day
				{Month: 5, Day: 1, ObserveOnWeekday: false},   // Labor Day
				{Month: 8, Day: 15, ObserveOnWeekday: false},  // Assumption
				{Month: 10, Day: 28, ObserveOnWeekday: false}, // Ochi Day
				{Month: 12, Day: 25, ObserveOnWeekday: false}, // Christmas
				{Month: 12, Day: 26, ObserveOnWeekday: false}, // Boxing Day
			},
			RuleBasedHolidays: []RuleBasedHoliday{},
			EasterBasedHolidays: []EasterBasedHoliday{
				{DaysOffset: -2}, // Good Friday (Orthodox)
				{DaysOffset: 1},  // Easter Monday (Orthodox)
			},
		},
	},
	"XHKG": {
		Code: "XHKG",
		Name: "Hong Kong Stock Exchange",
		TradingHours: TradingHours{
			OpenHour:    9,
			OpenMinute:  30,
			CloseHour:   16,
			CloseMinute: 0,
		},
		Timezone:    mustLoadLocation("Asia/Hong_Kong"),
		EasterType:  Gregorian,
		StrictHours: true,
		LunchBreak: &LunchBreak{
			StartHour:   12,
			StartMinute: 0,
			EndHour:     13,
			EndMinute:   0,
		},
		EarlyCloseRules: []EarlyCloseRule{},
		HolidayRules: HolidayRuleSet{
			// Hong Kong has many holidays - simplified for now
			// In production, would need full HK holiday calendar
			FixedDateHolidays: []FixedDateHoliday{
				{Month: 1, Day: 1, ObserveOnWeekday: false},   // New Year's Day
				{Month: 12, Day: 25, ObserveOnWeekday: false}, // Christmas
				{Month: 12, Day: 26, ObserveOnWeekday: false}, // Boxing Day
			},
			RuleBasedHolidays:   []RuleBasedHoliday{},
			EasterBasedHolidays: []EasterBasedHoliday{},
		},
	},
	"XSHG": {
		Code: "XSHG",
		Name: "Shanghai Stock Exchange",
		TradingHours: TradingHours{
			OpenHour:    9,
			OpenMinute:  30,
			CloseHour:   15,
			CloseMinute: 0,
		},
		Timezone:    mustLoadLocation("Asia/Shanghai"),
		EasterType:  Gregorian,
		StrictHours: true,
		LunchBreak: &LunchBreak{
			StartHour:   11,
			StartMinute: 30,
			EndHour:     13,
			EndMinute:   0,
		},
		EarlyCloseRules: []EarlyCloseRule{},
		HolidayRules: HolidayRuleSet{
			// Chinese holidays - simplified for now
			FixedDateHolidays: []FixedDateHoliday{
				{Month: 1, Day: 1, ObserveOnWeekday: false},  // New Year's Day
				{Month: 10, Day: 1, ObserveOnWeekday: false}, // National Day
			},
			RuleBasedHolidays:   []RuleBasedHoliday{},
			EasterBasedHolidays: []EasterBasedHoliday{},
		},
	},
	"XTSE": {
		Code: "XTSE",
		Name: "Tokyo Stock Exchange",
		TradingHours: TradingHours{
			OpenHour:    9,
			OpenMinute:  0,
			CloseHour:   15,
			CloseMinute: 0,
		},
		Timezone:    mustLoadLocation("Asia/Tokyo"),
		EasterType:  Gregorian,
		StrictHours: true,
		LunchBreak: &LunchBreak{
			StartHour:   11,
			StartMinute: 30,
			EndHour:     12,
			EndMinute:   30,
		},
		EarlyCloseRules: []EarlyCloseRule{},
		HolidayRules: HolidayRuleSet{
			// Japanese holidays - simplified for now
			FixedDateHolidays: []FixedDateHoliday{
				{Month: 1, Day: 1, ObserveOnWeekday: false},   // New Year's Day
				{Month: 12, Day: 23, ObserveOnWeekday: false}, // Emperor's Birthday (varies)
			},
			RuleBasedHolidays:   []RuleBasedHoliday{},
			EasterBasedHolidays: []EasterBasedHoliday{},
		},
	},
	"XASX": {
		Code: "XASX",
		Name: "Australian Securities Exchange",
		TradingHours: TradingHours{
			OpenHour:    10,
			OpenMinute:  0,
			CloseHour:   16,
			CloseMinute: 0,
		},
		Timezone:        mustLoadLocation("Australia/Sydney"),
		EasterType:      Gregorian,
		StrictHours:     true,
		LunchBreak:      nil,
		EarlyCloseRules: []EarlyCloseRule{},
		HolidayRules: HolidayRuleSet{
			FixedDateHolidays: []FixedDateHoliday{
				{Month: 1, Day: 1, ObserveOnWeekday: false},   // New Year's Day
				{Month: 1, Day: 26, ObserveOnWeekday: false},  // Australia Day
				{Month: 4, Day: 25, ObserveOnWeekday: false},  // ANZAC Day
				{Month: 12, Day: 25, ObserveOnWeekday: false}, // Christmas
				{Month: 12, Day: 26, ObserveOnWeekday: false}, // Boxing Day
			},
			RuleBasedHolidays: []RuleBasedHoliday{
				{Month: 3, Weekday: time.Monday, N: 2},  // Labour Day (varies by state, simplified)
				{Month: 6, Weekday: time.Monday, N: 2},  // Queen's Birthday (varies)
				{Month: 10, Weekday: time.Monday, N: 1}, // Labour Day (varies by state)
			},
			EasterBasedHolidays: []EasterBasedHoliday{
				{DaysOffset: -2}, // Good Friday
				{DaysOffset: 1},  // Easter Monday
			},
		},
	},
}

// mustLoadLocation loads a timezone location, panicking if it fails
func mustLoadLocation(name string) *time.Location {
	loc, err := time.LoadLocation(name)
	if err != nil {
		panic("failed to load timezone: " + name + ": " + err.Error())
	}
	return loc
}
