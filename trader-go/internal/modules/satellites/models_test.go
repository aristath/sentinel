package satellites

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestBucket_IsActive(t *testing.T) {
	tests := []struct {
		name     string
		status   BucketStatus
		expected bool
	}{
		{"active bucket", BucketStatusActive, true},
		{"accumulating bucket", BucketStatusAccumulating, false},
		{"paused bucket", BucketStatusPaused, false},
		{"retired bucket", BucketStatusRetired, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			bucket := &Bucket{Status: tt.status}
			assert.Equal(t, tt.expected, bucket.IsActive())
		})
	}
}

func TestBucket_IsTradingAllowed(t *testing.T) {
	tests := []struct {
		name     string
		status   BucketStatus
		expected bool
	}{
		{"active bucket", BucketStatusActive, true},
		{"accumulating bucket", BucketStatusAccumulating, true},
		{"paused bucket", BucketStatusPaused, false},
		{"hibernating bucket", BucketStatusHibernating, false},
		{"retired bucket", BucketStatusRetired, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			bucket := &Bucket{Status: tt.status}
			assert.Equal(t, tt.expected, bucket.IsTradingAllowed())
		})
	}
}

func TestBucket_IsCore(t *testing.T) {
	tests := []struct {
		name       string
		bucketType BucketType
		expected   bool
	}{
		{"core bucket", BucketTypeCore, true},
		{"satellite bucket", BucketTypeSatellite, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			bucket := &Bucket{Type: tt.bucketType}
			assert.Equal(t, tt.expected, bucket.IsCore())
		})
	}
}

func TestBucket_IsSatellite(t *testing.T) {
	tests := []struct {
		name       string
		bucketType BucketType
		expected   bool
	}{
		{"core bucket", BucketTypeCore, false},
		{"satellite bucket", BucketTypeSatellite, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			bucket := &Bucket{Type: tt.bucketType}
			assert.Equal(t, tt.expected, bucket.IsSatellite())
		})
	}
}

func TestBucket_CalculateDrawdown(t *testing.T) {
	tests := []struct {
		name          string
		highWaterMark float64
		currentValue  float64
		expected      float64
	}{
		{
			name:          "no drawdown",
			highWaterMark: 10000.0,
			currentValue:  10000.0,
			expected:      0.0,
		},
		{
			name:          "10% drawdown",
			highWaterMark: 10000.0,
			currentValue:  9000.0,
			expected:      0.1,
		},
		{
			name:          "50% drawdown",
			highWaterMark: 10000.0,
			currentValue:  5000.0,
			expected:      0.5,
		},
		{
			name:          "zero high water mark",
			highWaterMark: 0.0,
			currentValue:  5000.0,
			expected:      0.0,
		},
		{
			name:          "negative high water mark (edge case)",
			highWaterMark: -1000.0,
			currentValue:  5000.0,
			expected:      0.0,
		},
		{
			name:          "current value above high water mark",
			highWaterMark: 10000.0,
			currentValue:  11000.0,
			expected:      0.0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			bucket := &Bucket{HighWaterMark: tt.highWaterMark}
			drawdown := bucket.CalculateDrawdown(tt.currentValue)
			assert.InDelta(t, tt.expected, drawdown, 0.0001)
		})
	}
}

func TestNewBucketTransaction(t *testing.T) {
	bucketID := "satellite_1"
	txType := TransactionTypeDeposit
	amount := 1000.0
	currency := "USD"
	description := "Monthly deposit"

	tx := NewBucketTransaction(bucketID, txType, amount, currency, &description)

	assert.Equal(t, bucketID, tx.BucketID)
	assert.Equal(t, txType, tx.Type)
	assert.Equal(t, amount, tx.Amount)
	assert.Equal(t, currency, tx.Currency)
	assert.Equal(t, description, *tx.Description)
	assert.Nil(t, tx.ID) // ID not set until database insert

	// Verify timestamp is recent (within last second)
	createdAt, err := time.Parse(time.RFC3339, tx.CreatedAt)
	assert.NoError(t, err)
	assert.WithinDuration(t, time.Now(), createdAt, time.Second)
}

func TestNewBucketTransaction_NilDescription(t *testing.T) {
	tx := NewBucketTransaction("core", TransactionTypeTradeBuy, 500.0, "EUR", nil)

	assert.Equal(t, "core", tx.BucketID)
	assert.Equal(t, TransactionTypeTradeBuy, tx.Type)
	assert.Equal(t, 500.0, tx.Amount)
	assert.Equal(t, "EUR", tx.Currency)
	assert.Nil(t, tx.Description)
	assert.NotEmpty(t, tx.CreatedAt)
}

func TestNewSatelliteSettings(t *testing.T) {
	satelliteID := "satellite_momentum_1"
	settings := NewSatelliteSettings(satelliteID)

	assert.Equal(t, satelliteID, settings.SatelliteID)
	assert.Equal(t, 0.5, settings.RiskAppetite)
	assert.Equal(t, 0.5, settings.HoldDuration)
	assert.Equal(t, 0.5, settings.EntryStyle)
	assert.Equal(t, 0.5, settings.PositionSpread)
	assert.Equal(t, 0.5, settings.ProfitTaking)
	assert.False(t, settings.TrailingStops)
	assert.False(t, settings.FollowRegime)
	assert.False(t, settings.AutoHarvest)
	assert.False(t, settings.PauseHighVolatility)
	assert.Equal(t, "reinvest_same", settings.DividendHandling)
	assert.Nil(t, settings.Preset)
}

func TestSatelliteSettings_Validate_ValidSettings(t *testing.T) {
	settings := &SatelliteSettings{
		SatelliteID:         "satellite_1",
		RiskAppetite:        0.7,
		HoldDuration:        0.3,
		EntryStyle:          0.9,
		PositionSpread:      0.2,
		ProfitTaking:        0.5,
		TrailingStops:       true,
		FollowRegime:        false,
		AutoHarvest:         true,
		PauseHighVolatility: false,
		DividendHandling:    "send_to_core",
	}

	err := settings.Validate()
	assert.NoError(t, err)
}

func TestSatelliteSettings_Validate_InvalidSliderValues(t *testing.T) {
	tests := []struct {
		name          string
		setupSettings func(*SatelliteSettings)
		expectedError string
	}{
		{
			name: "risk appetite too high",
			setupSettings: func(s *SatelliteSettings) {
				s.RiskAppetite = 1.5
			},
			expectedError: "risk_appetite must be between 0.0 and 1.0",
		},
		{
			name: "risk appetite too low",
			setupSettings: func(s *SatelliteSettings) {
				s.RiskAppetite = -0.1
			},
			expectedError: "risk_appetite must be between 0.0 and 1.0",
		},
		{
			name: "hold duration too high",
			setupSettings: func(s *SatelliteSettings) {
				s.HoldDuration = 2.0
			},
			expectedError: "hold_duration must be between 0.0 and 1.0",
		},
		{
			name: "entry style too low",
			setupSettings: func(s *SatelliteSettings) {
				s.EntryStyle = -1.0
			},
			expectedError: "entry_style must be between 0.0 and 1.0",
		},
		{
			name: "position spread too high",
			setupSettings: func(s *SatelliteSettings) {
				s.PositionSpread = 1.1
			},
			expectedError: "position_spread must be between 0.0 and 1.0",
		},
		{
			name: "profit taking too low",
			setupSettings: func(s *SatelliteSettings) {
				s.ProfitTaking = -0.5
			},
			expectedError: "profit_taking must be between 0.0 and 1.0",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			settings := NewSatelliteSettings("satellite_test")
			tt.setupSettings(settings)

			err := settings.Validate()
			assert.Error(t, err)
			assert.Contains(t, err.Error(), tt.expectedError)
		})
	}
}

func TestSatelliteSettings_Validate_InvalidDividendHandling(t *testing.T) {
	settings := NewSatelliteSettings("satellite_1")
	settings.DividendHandling = "invalid_option"

	err := settings.Validate()
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "dividend_handling must be one of")
}

func TestSatelliteSettings_Validate_BoundaryValues(t *testing.T) {
	// Test exact boundary values (0.0 and 1.0) are valid
	tests := []struct {
		name  string
		value float64
	}{
		{"minimum value", 0.0},
		{"maximum value", 1.0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			settings := &SatelliteSettings{
				SatelliteID:      "satellite_1",
				RiskAppetite:     tt.value,
				HoldDuration:     tt.value,
				EntryStyle:       tt.value,
				PositionSpread:   tt.value,
				ProfitTaking:     tt.value,
				DividendHandling: "reinvest_same",
			}

			err := settings.Validate()
			assert.NoError(t, err)
		})
	}
}

func TestSatelliteSettings_Validate_AllDividendHandlingOptions(t *testing.T) {
	validOptions := []string{"reinvest_same", "send_to_core", "accumulate_cash"}

	for _, option := range validOptions {
		t.Run(option, func(t *testing.T) {
			settings := NewSatelliteSettings("satellite_1")
			settings.DividendHandling = option

			err := settings.Validate()
			assert.NoError(t, err)
		})
	}
}
