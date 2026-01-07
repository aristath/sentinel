package market_hours

import (
	"fmt"
	"time"
)

// MarketHoursService provides market hours checking functionality
type MarketHoursService struct {
	holidayCache map[int][]time.Time // Cache holidays by year
}

// NewMarketHoursService creates a new market hours service
func NewMarketHoursService() *MarketHoursService {
	return &MarketHoursService{
		holidayCache: make(map[int][]time.Time),
	}
}

// IsMarketOpen checks if a market is currently open for trading
func (s *MarketHoursService) IsMarketOpen(exchangeName string, t time.Time) bool {
	exchangeCode := GetExchangeCode(exchangeName)
	config := getExchangeConfig(exchangeCode)
	if config == nil {
		return false
	}

	// Convert time to market timezone
	marketTime := t.In(config.Timezone)
	marketDate := time.Date(marketTime.Year(), marketTime.Month(), marketTime.Day(), 0, 0, 0, 0, config.Timezone)

	// Check if weekend
	if marketTime.Weekday() == time.Saturday || marketTime.Weekday() == time.Sunday {
		return false
	}

	// Check if holiday
	if s.isHoliday(config, marketDate) {
		return false
	}

	// Check trading hours
	openTime := time.Date(marketTime.Year(), marketTime.Month(), marketTime.Day(),
		config.TradingHours.OpenHour, config.TradingHours.OpenMinute, 0, 0, config.Timezone)
	closeTime := time.Date(marketTime.Year(), marketTime.Month(), marketTime.Day(),
		config.TradingHours.CloseHour, config.TradingHours.CloseMinute, 0, 0, config.Timezone)

	// Check for early close and adjust close time if needed
	for _, rule := range config.EarlyCloseRules {
		if rule.DatePattern != nil && rule.DatePattern(marketTime) {
			// This is an early close day, use the early close time
			closeTime = time.Date(marketTime.Year(), marketTime.Month(), marketTime.Day(),
				rule.CloseHour, rule.CloseMinute, 0, 0, config.Timezone)
			break
		}
	}

	// Market is open if current time is after open and before close
	if marketTime.Before(openTime) || marketTime.After(closeTime) || marketTime.Equal(closeTime) {
		return false
	}

	// Check lunch break if applicable
	if config.LunchBreak != nil {
		lunchStart := time.Date(marketTime.Year(), marketTime.Month(), marketTime.Day(),
			config.LunchBreak.StartHour, config.LunchBreak.StartMinute, 0, 0, config.Timezone)
		lunchEnd := time.Date(marketTime.Year(), marketTime.Month(), marketTime.Day(),
			config.LunchBreak.EndHour, config.LunchBreak.EndMinute, 0, 0, config.Timezone)

		// Market is closed during lunch break [start, end) - includes start, excludes end
		if (marketTime.After(lunchStart) || marketTime.Equal(lunchStart)) && marketTime.Before(lunchEnd) {
			return false
		}
	}

	return true
}

// isHoliday checks if a date is a holiday for the given exchange
func (s *MarketHoursService) isHoliday(config *ExchangeConfig, date time.Time) bool {
	year := date.Year()
	holidays := s.getHolidaysForYear(config, year)

	dateStr := date.Format("2006-01-02")
	for _, holiday := range holidays {
		if holiday.Format("2006-01-02") == dateStr {
			return true
		}
	}

	return false
}

// getHolidaysForYear calculates all holidays for a given year and exchange
func (s *MarketHoursService) getHolidaysForYear(config *ExchangeConfig, year int) []time.Time {
	// Check cache
	if holidays, ok := s.holidayCache[year]; ok {
		return holidays
	}

	holidays := make([]time.Time, 0)

	// Fixed date holidays
	for _, h := range config.HolidayRules.FixedDateHolidays {
		date := time.Date(year, time.Month(h.Month), h.Day, 0, 0, 0, 0, config.Timezone)
		if h.ObserveOnWeekday {
			date = observeOnWeekday(date)
		}
		holidays = append(holidays, date)
	}

	// Rule-based holidays
	for _, h := range config.HolidayRules.RuleBasedHolidays {
		var date time.Time
		if h.N == -1 {
			// Last occurrence
			date = findLastWeekday(year, h.Month, h.Weekday)
		} else {
			// Nth occurrence
			date = findNthWeekday(year, h.Month, h.Weekday, h.N)
		}
		holidays = append(holidays, date)
	}

	// Easter-based holidays
	for _, h := range config.HolidayRules.EasterBasedHolidays {
		easter := CalculateEaster(year, config.EasterType)
		holiday := easter.AddDate(0, 0, h.DaysOffset)
		holidays = append(holidays, holiday)
	}

	// Cache the result
	s.holidayCache[year] = holidays

	return holidays
}

// isEarlyClose checks if a date/time is an early close day
// Reserved for future use
//
//nolint:unused // Reserved for future use
func (s *MarketHoursService) isEarlyClose(config *ExchangeConfig, t time.Time) bool {
	for _, rule := range config.EarlyCloseRules {
		if rule.DatePattern != nil && rule.DatePattern(t) {
			return true
		}
	}
	return false
}

// ShouldCheckMarketHours determines if market hours check is required for a trade
// Rules:
// - SELL orders: Always check market hours (all markets)
// - BUY orders: Only check if exchange requires strict market hours
func (s *MarketHoursService) ShouldCheckMarketHours(exchangeName, side string) bool {
	if side == "SELL" {
		return true
	}

	if side == "BUY" {
		return s.RequiresStrictMarketHours(exchangeName)
	}

	// Unknown side, default to checking (safe default)
	return true
}

// RequiresStrictMarketHours checks if an exchange requires strict market hours
func (s *MarketHoursService) RequiresStrictMarketHours(exchangeName string) bool {
	exchangeCode := GetExchangeCode(exchangeName)
	// Check both by code and by original name
	if strictMarketHoursExchanges[exchangeCode] {
		return true
	}
	if strictMarketHoursExchanges[exchangeName] {
		return true
	}
	return false
}

// GetOpenMarkets returns a list of currently open exchanges
func (s *MarketHoursService) GetOpenMarkets(t time.Time) []string {
	openMarkets := make([]string, 0)
	for code := range exchangeConfigs {
		if s.IsMarketOpen(code, t) {
			openMarkets = append(openMarkets, code)
		}
	}
	return openMarkets
}

// GetMarketStatus returns detailed status for a market
func (s *MarketHoursService) GetMarketStatus(exchangeName string, t time.Time) (*MarketStatus, error) {
	exchangeCode := GetExchangeCode(exchangeName)
	config := getExchangeConfig(exchangeCode)
	if config == nil {
		return nil, fmt.Errorf("exchange not found: %s", exchangeName)
	}

	marketTime := t.In(config.Timezone)
	isOpen := s.IsMarketOpen(exchangeCode, t)

	status := &MarketStatus{
		Open:     isOpen,
		Exchange: exchangeCode,
		Timezone: config.Timezone.String(),
	}

	if isOpen {
		// Get closing time for today (check for early close)
		closeTime := time.Date(marketTime.Year(), marketTime.Month(), marketTime.Day(),
			config.TradingHours.CloseHour, config.TradingHours.CloseMinute, 0, 0, config.Timezone)

		// Check for early close and adjust close time if needed
		for _, rule := range config.EarlyCloseRules {
			if rule.DatePattern != nil && rule.DatePattern(marketTime) {
				// This is an early close day, use the early close time
				closeTime = time.Date(marketTime.Year(), marketTime.Month(), marketTime.Day(),
					rule.CloseHour, rule.CloseMinute, 0, 0, config.Timezone)
				break
			}
		}

		status.ClosesAt = closeTime.Format("15:04")
	} else {
		// Find next trading session
		nextOpen := s.findNextTradingSession(config, marketTime)
		if nextOpen != nil {
			status.OpensAt = nextOpen.Format("15:04")
			if nextOpen.Day() != marketTime.Day() {
				status.OpensDate = nextOpen.Format("2006-01-02")
			}
		}
	}

	return status, nil
}

// findNextTradingSession finds the next time the market will be open
func (s *MarketHoursService) findNextTradingSession(config *ExchangeConfig, currentTime time.Time) *time.Time {
	// Check up to 7 days ahead
	for i := 0; i < 7; i++ {
		checkTime := currentTime.AddDate(0, 0, i)
		if i == 0 {
			// For today, check if market opens later today
			openTime := time.Date(checkTime.Year(), checkTime.Month(), checkTime.Day(),
				config.TradingHours.OpenHour, config.TradingHours.OpenMinute, 0, 0, config.Timezone)
			if checkTime.Before(openTime) && !s.isHoliday(config, checkTime) && checkTime.Weekday() != time.Saturday && checkTime.Weekday() != time.Sunday {
				return &openTime
			}
		} else {
			// For future days, check if it's a trading day
			if checkTime.Weekday() != time.Saturday && checkTime.Weekday() != time.Sunday {
				if !s.isHoliday(config, checkTime) {
					openTime := time.Date(checkTime.Year(), checkTime.Month(), checkTime.Day(),
						config.TradingHours.OpenHour, config.TradingHours.OpenMinute, 0, 0, config.Timezone)
					return &openTime
				}
			}
		}
	}
	return nil
}
