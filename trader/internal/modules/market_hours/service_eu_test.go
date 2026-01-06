package market_hours

import (
	"testing"
	"time"
)

func TestIsMarketOpen_XETR(t *testing.T) {
	service := NewMarketHoursService()
	berlinTZ, _ := time.LoadLocation("Europe/Berlin")

	tests := []struct {
		name     string
		datetime time.Time
		expected bool
	}{
		{
			name:     "Market open during regular hours",
			datetime: time.Date(2024, 1, 16, 10, 0, 0, 0, time.UTC), // Tuesday 11:00 AM CET
			expected: true,
		},
		{
			name:     "Market closed on weekend",
			datetime: time.Date(2024, 1, 13, 10, 0, 0, 0, time.UTC), // Saturday
			expected: false,
		},
		{
			name:     "Market closed on Good Friday",
			datetime: time.Date(2024, 3, 29, 10, 0, 0, 0, time.UTC), // Good Friday 2024
			expected: false,
		},
		{
			name:     "Market closed on New Year's Day",
			datetime: time.Date(2024, 1, 1, 10, 0, 0, 0, time.UTC), // New Year's Day
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			berlinTime := tt.datetime.In(berlinTZ)
			t.Logf("Testing at %v (Berlin time: %v)", tt.datetime, berlinTime)

			result := service.IsMarketOpen("XETR", tt.datetime)
			if result != tt.expected {
				t.Errorf("IsMarketOpen(\"XETR\", %v) = %v, want %v", tt.datetime, result, tt.expected)
			}
		})
	}
}

func TestIsMarketOpen_XLON(t *testing.T) {
	service := NewMarketHoursService()
	londonTZ, _ := time.LoadLocation("Europe/London")

	tests := []struct {
		name     string
		datetime time.Time
		expected bool
	}{
		{
			name:     "Market open during regular hours",
			datetime: time.Date(2024, 1, 16, 12, 0, 0, 0, time.UTC), // Tuesday 12:00 PM GMT
			expected: true,
		},
		{
			name:     "Market closed on Good Friday",
			datetime: time.Date(2024, 3, 29, 12, 0, 0, 0, time.UTC), // Good Friday 2024
			expected: false,
		},
		{
			name:     "Market closed on Christmas",
			datetime: time.Date(2024, 12, 25, 12, 0, 0, 0, time.UTC), // Christmas
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			londonTime := tt.datetime.In(londonTZ)
			t.Logf("Testing at %v (London time: %v)", tt.datetime, londonTime)

			result := service.IsMarketOpen("XLON", tt.datetime)
			if result != tt.expected {
				t.Errorf("IsMarketOpen(\"XLON\", %v) = %v, want %v", tt.datetime, result, tt.expected)
			}
		})
	}
}

func TestIsMarketOpen_ASEX_OrthodoxEaster(t *testing.T) {
	service := NewMarketHoursService()
	athensTZ, _ := time.LoadLocation("Europe/Athens")

	tests := []struct {
		name     string
		datetime time.Time
		expected bool
	}{
		{
			name:     "Market closed on Orthodox Good Friday 2024",
			datetime: time.Date(2024, 5, 3, 12, 0, 0, 0, time.UTC), // Orthodox Good Friday 2024
			expected: false,
		},
		{
			name:     "Market closed on Orthodox Easter Monday 2024",
			datetime: time.Date(2024, 5, 6, 12, 0, 0, 0, time.UTC), // Orthodox Easter Monday 2024
			expected: false,
		},
		{
			name:     "Market open on regular day",
			datetime: time.Date(2024, 1, 16, 12, 0, 0, 0, time.UTC), // Regular Tuesday
			expected: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			athensTime := tt.datetime.In(athensTZ)
			t.Logf("Testing at %v (Athens time: %v)", tt.datetime, athensTime)

			result := service.IsMarketOpen("ASEX", tt.datetime)
			if result != tt.expected {
				t.Errorf("IsMarketOpen(\"ASEX\", %v) = %v, want %v", tt.datetime, result, tt.expected)
			}
		})
	}
}
