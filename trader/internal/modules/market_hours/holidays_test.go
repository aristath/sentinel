package market_hours

import (
	"testing"
	"time"
)

func TestCalculateEaster_Gregorian(t *testing.T) {
	tests := []struct {
		year     int
		expected time.Time
	}{
		{2024, time.Date(2024, 3, 31, 0, 0, 0, 0, time.UTC)},
		{2025, time.Date(2025, 4, 20, 0, 0, 0, 0, time.UTC)},
		{2026, time.Date(2026, 4, 5, 0, 0, 0, 0, time.UTC)},
		{2027, time.Date(2027, 3, 28, 0, 0, 0, 0, time.UTC)},
		{2028, time.Date(2028, 4, 16, 0, 0, 0, 0, time.UTC)},
		{2029, time.Date(2029, 4, 1, 0, 0, 0, 0, time.UTC)},
		{2030, time.Date(2030, 4, 21, 0, 0, 0, 0, time.UTC)},
	}

	for _, tt := range tests {
		t.Run(tt.expected.Format("2006-01-02"), func(t *testing.T) {
			result := CalculateEaster(tt.year, Gregorian)
			if !result.Equal(tt.expected) {
				t.Errorf("CalculateEaster(%d, Gregorian) = %v, want %v", tt.year, result, tt.expected)
			}
			// Verify it's a Sunday
			if result.Weekday() != time.Sunday {
				t.Errorf("Easter should be on Sunday, got %v", result.Weekday())
			}
		})
	}
}

func TestCalculateEaster_Julian(t *testing.T) {
	tests := []struct {
		year     int
		expected time.Time
	}{
		{2024, time.Date(2024, 5, 5, 0, 0, 0, 0, time.UTC)},  // Orthodox Easter 2024
		{2025, time.Date(2025, 4, 20, 0, 0, 0, 0, time.UTC)}, // Same as Gregorian in 2025
		{2026, time.Date(2026, 4, 12, 0, 0, 0, 0, time.UTC)}, // Orthodox Easter 2026
	}

	for _, tt := range tests {
		t.Run(tt.expected.Format("2006-01-02"), func(t *testing.T) {
			result := CalculateEaster(tt.year, Julian)
			if !result.Equal(tt.expected) {
				t.Errorf("CalculateEaster(%d, Julian) = %v, want %v", tt.year, result, tt.expected)
			}
			// Verify it's a Sunday
			if result.Weekday() != time.Sunday {
				t.Errorf("Easter should be on Sunday, got %v", result.Weekday())
			}
		})
	}
}

func TestCalculateGoodFriday(t *testing.T) {
	tests := []struct {
		year         int
		calendarType CalendarType
		expected     time.Time
	}{
		{2024, Gregorian, time.Date(2024, 3, 29, 0, 0, 0, 0, time.UTC)},
		{2025, Gregorian, time.Date(2025, 4, 18, 0, 0, 0, 0, time.UTC)},
		{2024, Julian, time.Date(2024, 5, 3, 0, 0, 0, 0, time.UTC)},  // Orthodox Good Friday 2024
		{2026, Julian, time.Date(2026, 4, 10, 0, 0, 0, 0, time.UTC)}, // Orthodox Good Friday 2026
	}

	for _, tt := range tests {
		t.Run(tt.expected.Format("2006-01-02"), func(t *testing.T) {
			result := CalculateGoodFriday(tt.year, tt.calendarType)
			if !result.Equal(tt.expected) {
				t.Errorf("CalculateGoodFriday(%d, %v) = %v, want %v", tt.year, tt.calendarType, result, tt.expected)
			}
			// Verify it's a Friday
			if result.Weekday() != time.Friday {
				t.Errorf("Good Friday should be on Friday, got %v", result.Weekday())
			}
		})
	}
}

func TestFindNthWeekday(t *testing.T) {
	tests := []struct {
		name     string
		year     int
		month    int
		weekday  time.Weekday
		n        int
		expected time.Time
	}{
		{"1st Monday in January 2024", 2024, 1, time.Monday, 1, time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)},
		{"3rd Monday in January 2024", 2024, 1, time.Monday, 3, time.Date(2024, 1, 15, 0, 0, 0, 0, time.UTC)},
		{"1st Monday in September 2024", 2024, 9, time.Monday, 1, time.Date(2024, 9, 2, 0, 0, 0, 0, time.UTC)},
		{"4th Thursday in November 2024", 2024, 11, time.Thursday, 4, time.Date(2024, 11, 28, 0, 0, 0, 0, time.UTC)},
		{"3rd Monday in February 2025", 2025, 2, time.Monday, 3, time.Date(2025, 2, 17, 0, 0, 0, 0, time.UTC)},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := findNthWeekday(tt.year, tt.month, tt.weekday, tt.n)
			if !result.Equal(tt.expected) {
				t.Errorf("findNthWeekday(%d, %d, %v, %d) = %v, want %v", tt.year, tt.month, tt.weekday, tt.n, result, tt.expected)
			}
			if result.Weekday() != tt.weekday {
				t.Errorf("Expected weekday %v, got %v", tt.weekday, result.Weekday())
			}
		})
	}
}

func TestFindLastWeekday(t *testing.T) {
	tests := []struct {
		name     string
		year     int
		month    int
		weekday  time.Weekday
		expected time.Time
	}{
		{"Last Monday in May 2024", 2024, 5, time.Monday, time.Date(2024, 5, 27, 0, 0, 0, 0, time.UTC)},
		{"Last Monday in May 2025", 2025, 5, time.Monday, time.Date(2025, 5, 26, 0, 0, 0, 0, time.UTC)},
		{"Last Friday in December 2024", 2024, 12, time.Friday, time.Date(2024, 12, 27, 0, 0, 0, 0, time.UTC)},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := findLastWeekday(tt.year, tt.month, tt.weekday)
			if !result.Equal(tt.expected) {
				t.Errorf("findLastWeekday(%d, %d, %v) = %v, want %v", tt.year, tt.month, tt.weekday, result, tt.expected)
			}
			if result.Weekday() != tt.weekday {
				t.Errorf("Expected weekday %v, got %v", tt.weekday, result.Weekday())
			}
		})
	}
}

func TestObserveOnWeekday(t *testing.T) {
	tests := []struct {
		name     string
		date     time.Time
		expected time.Time
	}{
		{"Monday stays Monday", time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC), time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)},
		{"Saturday moves to Friday", time.Date(2024, 1, 6, 0, 0, 0, 0, time.UTC), time.Date(2024, 1, 5, 0, 0, 0, 0, time.UTC)},
		{"Sunday moves to Monday", time.Date(2024, 1, 7, 0, 0, 0, 0, time.UTC), time.Date(2024, 1, 8, 0, 0, 0, 0, time.UTC)},
		{"Friday stays Friday", time.Date(2024, 1, 5, 0, 0, 0, 0, time.UTC), time.Date(2024, 1, 5, 0, 0, 0, 0, time.UTC)},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := observeOnWeekday(tt.date)
			if !result.Equal(tt.expected) {
				t.Errorf("observeOnWeekday(%v) = %v, want %v", tt.date, result, tt.expected)
			}
			// Result should never be Saturday or Sunday
			if result.Weekday() == time.Saturday || result.Weekday() == time.Sunday {
				t.Errorf("Observed date should not be weekend, got %v", result.Weekday())
			}
		})
	}
}

func TestCalculateUSHolidays(t *testing.T) {
	// Test 2024 US holidays
	year := 2024
	holidays := CalculateUSHolidays(year)

	expectedHolidays := map[string]time.Time{
		"New Year's Day":   time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC),
		"MLK Day":          time.Date(2024, 1, 15, 0, 0, 0, 0, time.UTC),
		"Presidents Day":   time.Date(2024, 2, 19, 0, 0, 0, 0, time.UTC),
		"Good Friday":      time.Date(2024, 3, 29, 0, 0, 0, 0, time.UTC),
		"Memorial Day":     time.Date(2024, 5, 27, 0, 0, 0, 0, time.UTC),
		"Juneteenth":       time.Date(2024, 6, 19, 0, 0, 0, 0, time.UTC),
		"Independence Day": time.Date(2024, 7, 4, 0, 0, 0, 0, time.UTC),
		"Labor Day":        time.Date(2024, 9, 2, 0, 0, 0, 0, time.UTC),
		"Thanksgiving":     time.Date(2024, 11, 28, 0, 0, 0, 0, time.UTC),
		"Christmas":        time.Date(2024, 12, 25, 0, 0, 0, 0, time.UTC),
	}

	holidayMap := make(map[string]time.Time)
	for _, h := range holidays {
		holidayMap[h.Format("2006-01-02")] = h
	}

	for name, expected := range expectedHolidays {
		dateStr := expected.Format("2006-01-02")
		if actual, ok := holidayMap[dateStr]; !ok {
			t.Errorf("Missing holiday: %s (expected %v)", name, expected)
		} else if !actual.Equal(expected) {
			t.Errorf("Holiday %s: got %v, want %v", name, actual, expected)
		}
	}

	// Test 2025
	year = 2025
	holidays = CalculateUSHolidays(year)
	expected2025 := map[string]time.Time{
		"New Year's Day":   time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC),
		"MLK Day":          time.Date(2025, 1, 20, 0, 0, 0, 0, time.UTC),
		"Presidents Day":   time.Date(2025, 2, 17, 0, 0, 0, 0, time.UTC),
		"Good Friday":      time.Date(2025, 4, 18, 0, 0, 0, 0, time.UTC),
		"Memorial Day":     time.Date(2025, 5, 26, 0, 0, 0, 0, time.UTC),
		"Juneteenth":       time.Date(2025, 6, 19, 0, 0, 0, 0, time.UTC),
		"Independence Day": time.Date(2025, 7, 4, 0, 0, 0, 0, time.UTC),
		"Labor Day":        time.Date(2025, 9, 1, 0, 0, 0, 0, time.UTC),
		"Thanksgiving":     time.Date(2025, 11, 27, 0, 0, 0, 0, time.UTC),
		"Christmas":        time.Date(2025, 12, 25, 0, 0, 0, 0, time.UTC),
	}

	holidayMap = make(map[string]time.Time)
	for _, h := range holidays {
		holidayMap[h.Format("2006-01-02")] = h
	}

	for name, expected := range expected2025 {
		dateStr := expected.Format("2006-01-02")
		if actual, ok := holidayMap[dateStr]; !ok {
			t.Errorf("Missing holiday: %s (expected %v)", name, expected)
		} else if !actual.Equal(expected) {
			t.Errorf("Holiday %s: got %v, want %v", name, actual, expected)
		}
	}

	// Verify no holidays fall on weekends (except Good Friday which can be any day)
	for _, h := range holidays {
		if h.Weekday() == time.Saturday || h.Weekday() == time.Sunday {
			// Good Friday can be any day, so skip it
			if h.Month() != 3 && h.Month() != 4 && h.Month() != 5 {
				t.Errorf("Holiday %v falls on weekend: %v", h, h.Weekday())
			}
		}
	}
}
