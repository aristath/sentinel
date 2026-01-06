package market_hours

import (
	"testing"
	"time"
)

func TestIsMarketOpen_XHKG_LunchBreak(t *testing.T) {
	service := NewMarketHoursService()
	hkTZ, _ := time.LoadLocation("Asia/Hong_Kong")

	tests := []struct {
		name     string
		datetime time.Time
		expected bool
	}{
		{
			name:     "Market open before lunch",
			datetime: time.Date(2024, 1, 16, 2, 0, 0, 0, time.UTC), // Tuesday 10:00 AM HKT
			expected: true,
		},
		{
			name:     "Market closed during lunch break",
			datetime: time.Date(2024, 1, 16, 4, 30, 0, 0, time.UTC), // Tuesday 12:30 PM HKT (during lunch)
			expected: false,
		},
		{
			name:     "Market open after lunch",
			datetime: time.Date(2024, 1, 16, 6, 0, 0, 0, time.UTC), // Tuesday 2:00 PM HKT
			expected: true,
		},
		{
			name:     "Market closed on weekend",
			datetime: time.Date(2024, 1, 13, 5, 0, 0, 0, time.UTC), // Saturday
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			hkTime := tt.datetime.In(hkTZ)
			t.Logf("Testing at %v (HK time: %v)", tt.datetime, hkTime)

			result := service.IsMarketOpen("XHKG", tt.datetime)
			if result != tt.expected {
				t.Errorf("IsMarketOpen(\"XHKG\", %v) = %v, want %v", tt.datetime, result, tt.expected)
			}
		})
	}
}

func TestIsMarketOpen_XSHG_LunchBreak(t *testing.T) {
	service := NewMarketHoursService()
	shanghaiTZ, _ := time.LoadLocation("Asia/Shanghai")

	tests := []struct {
		name     string
		datetime time.Time
		expected bool
	}{
		{
			name:     "Market open before lunch",
			datetime: time.Date(2024, 1, 16, 2, 0, 0, 0, time.UTC), // Tuesday 10:00 AM CST
			expected: true,
		},
		{
			name:     "Market closed during lunch break",
			datetime: time.Date(2024, 1, 16, 4, 0, 0, 0, time.UTC), // Tuesday 12:00 PM CST (during lunch)
			expected: false,
		},
		{
			name:     "Market open after lunch",
			datetime: time.Date(2024, 1, 16, 5, 0, 0, 0, time.UTC), // Tuesday 1:00 PM CST
			expected: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			shanghaiTime := tt.datetime.In(shanghaiTZ)
			t.Logf("Testing at %v (Shanghai time: %v)", tt.datetime, shanghaiTime)

			result := service.IsMarketOpen("XSHG", tt.datetime)
			if result != tt.expected {
				t.Errorf("IsMarketOpen(\"XSHG\", %v) = %v, want %v", tt.datetime, result, tt.expected)
			}
		})
	}
}

func TestIsMarketOpen_XTSE_LunchBreak(t *testing.T) {
	service := NewMarketHoursService()
	tokyoTZ, _ := time.LoadLocation("Asia/Tokyo")

	tests := []struct {
		name     string
		datetime time.Time
		expected bool
	}{
		{
			name:     "Market open before lunch",
			datetime: time.Date(2024, 1, 16, 0, 0, 0, 0, time.UTC), // Tuesday 9:00 AM JST
			expected: true,
		},
		{
			name:     "Market closed during lunch break",
			datetime: time.Date(2024, 1, 16, 2, 30, 0, 0, time.UTC), // Tuesday 11:30 AM JST (during lunch)
			expected: false,
		},
		{
			name:     "Market open after lunch",
			datetime: time.Date(2024, 1, 16, 3, 30, 0, 0, time.UTC), // Tuesday 12:30 PM JST
			expected: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tokyoTime := tt.datetime.In(tokyoTZ)
			t.Logf("Testing at %v (Tokyo time: %v)", tt.datetime, tokyoTime)

			result := service.IsMarketOpen("XTSE", tt.datetime)
			if result != tt.expected {
				t.Errorf("IsMarketOpen(\"XTSE\", %v) = %v, want %v", tt.datetime, result, tt.expected)
			}
		})
	}
}

func TestIsMarketOpen_XASX(t *testing.T) {
	service := NewMarketHoursService()
	sydneyTZ, _ := time.LoadLocation("Australia/Sydney")

	tests := []struct {
		name     string
		datetime time.Time
		expected bool
	}{
		{
			name:     "Market open during regular hours",
			datetime: time.Date(2024, 1, 16, 23, 0, 0, 0, time.UTC), // Wednesday 10:00 AM AEDT
			expected: true,
		},
		{
			name:     "Market closed on Good Friday",
			datetime: time.Date(2024, 3, 29, 23, 0, 0, 0, time.UTC), // Good Friday 2024
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			sydneyTime := tt.datetime.In(sydneyTZ)
			t.Logf("Testing at %v (Sydney time: %v)", tt.datetime, sydneyTime)

			result := service.IsMarketOpen("XASX", tt.datetime)
			if result != tt.expected {
				t.Errorf("IsMarketOpen(\"XASX\", %v) = %v, want %v", tt.datetime, result, tt.expected)
			}
		})
	}
}
