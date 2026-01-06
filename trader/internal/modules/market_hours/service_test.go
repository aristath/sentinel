package market_hours

import (
	"testing"
	"time"
)

func TestIsMarketOpen_XNYS_RegularHours(t *testing.T) {
	service := NewMarketHoursService()
	nyTZ, _ := time.LoadLocation("America/New_York")

	tests := []struct {
		name     string
		datetime time.Time
		expected bool
	}{
		{
			name:     "Market open during regular hours",
			datetime: time.Date(2024, 1, 16, 15, 0, 0, 0, time.UTC), // Tuesday 10:00 AM EST
			expected: true,
		},
		{
			name:     "Market closed before open",
			datetime: time.Date(2024, 1, 16, 13, 0, 0, 0, time.UTC), // Tuesday 8:00 AM EST (before 9:30 AM)
			expected: false,
		},
		{
			name:     "Market closed after close",
			datetime: time.Date(2024, 1, 16, 21, 0, 0, 0, time.UTC), // Tuesday 4:00 PM EST (after 4:00 PM)
			expected: false,
		},
		{
			name:     "Market open at 9:30 AM",
			datetime: time.Date(2024, 1, 16, 14, 30, 0, 0, time.UTC), // Tuesday 9:30 AM EST
			expected: true,
		},
		{
			name:     "Market open at 4:00 PM",
			datetime: time.Date(2024, 1, 16, 21, 0, 0, 0, time.UTC), // Tuesday 4:00 PM EST
			expected: false,                                         // Closed at exactly 4:00 PM
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Convert to NY timezone for verification
			nyTime := tt.datetime.In(nyTZ)
			t.Logf("Testing at %v (NY time: %v)", tt.datetime, nyTime)

			result := service.IsMarketOpen("XNYS", tt.datetime)
			if result != tt.expected {
				t.Errorf("IsMarketOpen(\"XNYS\", %v) = %v, want %v", tt.datetime, result, tt.expected)
			}
		})
	}
}

func TestIsMarketOpen_XNYS_Weekend(t *testing.T) {
	service := NewMarketHoursService()

	tests := []struct {
		name     string
		datetime time.Time
		expected bool
	}{
		{
			name:     "Saturday",
			datetime: time.Date(2024, 1, 13, 15, 0, 0, 0, time.UTC), // Saturday
			expected: false,
		},
		{
			name:     "Sunday",
			datetime: time.Date(2024, 1, 14, 15, 0, 0, 0, time.UTC), // Sunday
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.IsMarketOpen("XNYS", tt.datetime)
			if result != tt.expected {
				t.Errorf("IsMarketOpen(\"XNYS\", %v) = %v, want %v", tt.datetime, result, tt.expected)
			}
		})
	}
}

func TestIsMarketOpen_XNYS_Holidays(t *testing.T) {
	service := NewMarketHoursService()

	tests := []struct {
		name     string
		datetime time.Time
		expected bool
	}{
		{
			name:     "New Year's Day 2024",
			datetime: time.Date(2024, 1, 1, 15, 0, 0, 0, time.UTC), // Monday (observed)
			expected: false,
		},
		{
			name:     "Christmas 2024",
			datetime: time.Date(2024, 12, 25, 15, 0, 0, 0, time.UTC), // Wednesday
			expected: false,
		},
		{
			name:     "Thanksgiving 2024",
			datetime: time.Date(2024, 11, 28, 15, 0, 0, 0, time.UTC), // Thursday
			expected: false,
		},
		{
			name:     "Good Friday 2024",
			datetime: time.Date(2024, 3, 29, 15, 0, 0, 0, time.UTC), // Friday
			expected: false,
		},
		{
			name:     "Regular trading day",
			datetime: time.Date(2024, 1, 16, 15, 0, 0, 0, time.UTC), // Tuesday (not a holiday)
			expected: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.IsMarketOpen("XNYS", tt.datetime)
			if result != tt.expected {
				t.Errorf("IsMarketOpen(\"XNYS\", %v) = %v, want %v", tt.datetime, result, tt.expected)
			}
		})
	}
}

func TestIsMarketOpen_XNYS_EarlyClose(t *testing.T) {
	service := NewMarketHoursService()
	nyTZ, _ := time.LoadLocation("America/New_York")

	// Day before Thanksgiving 2024 (Nov 27, Wednesday)
	// Should close at 1:00 PM EST
	tests := []struct {
		name     string
		datetime time.Time
		expected bool
	}{
		{
			name:     "Before early close",
			datetime: time.Date(2024, 11, 27, 18, 0, 0, 0, time.UTC), // 1:00 PM EST
			expected: false,                                          // Closed at exactly 1:00 PM
		},
		{
			name:     "During early close day morning",
			datetime: time.Date(2024, 11, 27, 14, 30, 0, 0, time.UTC), // 9:30 AM EST
			expected: true,
		},
		{
			name:     "After early close",
			datetime: time.Date(2024, 11, 27, 19, 0, 0, 0, time.UTC), // 2:00 PM EST
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			nyTime := tt.datetime.In(nyTZ)
			t.Logf("Testing at %v (NY time: %v)", tt.datetime, nyTime)

			result := service.IsMarketOpen("XNYS", tt.datetime)
			if result != tt.expected {
				t.Errorf("IsMarketOpen(\"XNYS\", %v) = %v, want %v", tt.datetime, result, tt.expected)
			}
		})
	}
}

func TestIsMarketOpen_XNYS_Timezone(t *testing.T) {
	service := NewMarketHoursService()

	// Test that timezone conversion works correctly
	// 3:00 PM EST = 8:00 PM UTC (during standard time)
	// 3:00 PM EDT = 7:00 PM UTC (during daylight time)

	// January 16, 2024 - Standard time (EST)
	estTime := time.Date(2024, 1, 16, 20, 0, 0, 0, time.UTC) // 3:00 PM EST
	if !service.IsMarketOpen("XNYS", estTime) {
		t.Errorf("Market should be open at 3:00 PM EST")
	}

	// July 16, 2024 - Daylight time (EDT)
	edtTime := time.Date(2024, 7, 16, 19, 0, 0, 0, time.UTC) // 3:00 PM EDT
	if !service.IsMarketOpen("XNYS", edtTime) {
		t.Errorf("Market should be open at 3:00 PM EDT")
	}
}

func TestShouldCheckMarketHours(t *testing.T) {
	service := NewMarketHoursService()

	tests := []struct {
		name         string
		exchangeName string
		side         string
		expected     bool
	}{
		{"SELL on XNYS", "XNYS", "SELL", true},
		{"BUY on XNYS", "XNYS", "BUY", false}, // Flexible hours
		{"SELL on XHKG", "XHKG", "SELL", true},
		{"BUY on XHKG", "XHKG", "BUY", true}, // Strict hours
		{"SELL on XSHG", "XSHG", "SELL", true},
		{"BUY on XSHG", "XSHG", "BUY", true},      // Strict hours
		{"Unknown side", "XNYS", "UNKNOWN", true}, // Default to checking
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.ShouldCheckMarketHours(tt.exchangeName, tt.side)
			if result != tt.expected {
				t.Errorf("ShouldCheckMarketHours(%q, %q) = %v, want %v", tt.exchangeName, tt.side, result, tt.expected)
			}
		})
	}
}

func TestRequiresStrictMarketHours(t *testing.T) {
	service := NewMarketHoursService()

	tests := []struct {
		name         string
		exchangeName string
		expected     bool
	}{
		{"XNYS", "XNYS", false},
		{"XNAS", "XNAS", false},
		{"XHKG", "XHKG", true},
		{"XSHG", "XSHG", true},
		{"XTSE", "XTSE", true},
		{"XASX", "XASX", true},
		{"XETR", "XETR", false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := service.RequiresStrictMarketHours(tt.exchangeName)
			if result != tt.expected {
				t.Errorf("RequiresStrictMarketHours(%q) = %v, want %v", tt.exchangeName, result, tt.expected)
			}
		})
	}
}
