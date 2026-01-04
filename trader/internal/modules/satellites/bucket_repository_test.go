package satellites

import (
	"database/sql"
	"testing"

	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func setupTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite3", ":memory:")
	require.NoError(t, err)

	err = InitSchema(db)
	require.NoError(t, err)

	return db
}

func TestBucketRepository_Create(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBucketRepository(db, zerolog.Nop())

	targetPct := 0.10
	bucket := &Bucket{
		ID:                   "satellite_test_1",
		Name:                 "Test Satellite",
		Type:                 BucketTypeSatellite,
		Status:               BucketStatusActive,
		TargetPct:            &targetPct,
		ConsecutiveLosses:    0,
		MaxConsecutiveLosses: 5,
		HighWaterMark:        0.0,
	}

	err := repo.Create(bucket)
	require.NoError(t, err)
	assert.NotEmpty(t, bucket.CreatedAt)
	assert.NotEmpty(t, bucket.UpdatedAt)

	// Verify it was created
	retrieved, err := repo.GetByID("satellite_test_1")
	require.NoError(t, err)
	require.NotNil(t, retrieved)
	assert.Equal(t, "Test Satellite", retrieved.Name)
	assert.Equal(t, BucketTypeSatellite, retrieved.Type)
	assert.Equal(t, targetPct, *retrieved.TargetPct)
}

func TestBucketRepository_GetCore(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBucketRepository(db, zerolog.Nop())

	// Create core bucket
	core := &Bucket{
		ID:                   "core",
		Name:                 "Core Portfolio",
		Type:                 BucketTypeCore,
		Status:               BucketStatusActive,
		ConsecutiveLosses:    0,
		MaxConsecutiveLosses: 5,
		HighWaterMark:        0.0,
	}

	err := repo.Create(core)
	require.NoError(t, err)

	// Retrieve core
	retrieved, err := repo.GetCore()
	require.NoError(t, err)
	require.NotNil(t, retrieved)
	assert.Equal(t, "core", retrieved.ID)
	assert.True(t, retrieved.IsCore())
}

func TestBucketRepository_Update(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBucketRepository(db, zerolog.Nop())

	// Create bucket
	bucket := &Bucket{
		ID:                   "satellite_update",
		Name:                 "Original Name",
		Type:                 BucketTypeSatellite,
		Status:               BucketStatusActive,
		ConsecutiveLosses:    0,
		MaxConsecutiveLosses: 5,
		HighWaterMark:        0.0,
	}
	err := repo.Create(bucket)
	require.NoError(t, err)

	// Update
	updated, err := repo.Update("satellite_update", map[string]interface{}{
		"name":   "Updated Name",
		"status": BucketStatusPaused,
	})
	require.NoError(t, err)
	require.NotNil(t, updated)
	assert.Equal(t, "Updated Name", updated.Name)
	assert.Equal(t, BucketStatusPaused, updated.Status)
}

func TestBucketRepository_Update_InvalidColumn(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBucketRepository(db, zerolog.Nop())

	// Create bucket
	bucket := &Bucket{
		ID:                   "satellite_test",
		Name:                 "Test",
		Type:                 BucketTypeSatellite,
		Status:               BucketStatusActive,
		ConsecutiveLosses:    0,
		MaxConsecutiveLosses: 5,
		HighWaterMark:        0.0,
	}
	err := repo.Create(bucket)
	require.NoError(t, err)

	// Try to update with invalid column
	_, err = repo.Update("satellite_test", map[string]interface{}{
		"invalid_column": "value",
	})
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "invalid column")
}

func TestBucketRepository_IncrementConsecutiveLosses(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBucketRepository(db, zerolog.Nop())

	// Create bucket
	bucket := &Bucket{
		ID:                   "satellite_losses",
		Name:                 "Test",
		Type:                 BucketTypeSatellite,
		Status:               BucketStatusActive,
		ConsecutiveLosses:    0,
		MaxConsecutiveLosses: 5,
		HighWaterMark:        0.0,
	}
	err := repo.Create(bucket)
	require.NoError(t, err)

	// Increment losses
	count, err := repo.IncrementConsecutiveLosses("satellite_losses")
	require.NoError(t, err)
	assert.Equal(t, 1, count)

	// Increment again
	count, err = repo.IncrementConsecutiveLosses("satellite_losses")
	require.NoError(t, err)
	assert.Equal(t, 2, count)
}

func TestBucketRepository_ResetConsecutiveLosses(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBucketRepository(db, zerolog.Nop())

	// Create bucket with losses
	bucket := &Bucket{
		ID:                   "satellite_reset",
		Name:                 "Test",
		Type:                 BucketTypeSatellite,
		Status:               BucketStatusActive,
		ConsecutiveLosses:    3,
		MaxConsecutiveLosses: 5,
		HighWaterMark:        0.0,
	}
	err := repo.Create(bucket)
	require.NoError(t, err)

	// Reset
	err = repo.ResetConsecutiveLosses("satellite_reset")
	require.NoError(t, err)

	// Verify reset
	retrieved, err := repo.GetByID("satellite_reset")
	require.NoError(t, err)
	assert.Equal(t, 0, retrieved.ConsecutiveLosses)
	assert.Nil(t, retrieved.LossStreakPausedAt)
}

func TestBucketRepository_UpdateHighWaterMark(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBucketRepository(db, zerolog.Nop())

	// Create bucket
	bucket := &Bucket{
		ID:                   "satellite_hwm",
		Name:                 "Test",
		Type:                 BucketTypeSatellite,
		Status:               BucketStatusActive,
		ConsecutiveLosses:    0,
		MaxConsecutiveLosses: 5,
		HighWaterMark:        1000.0,
	}
	err := repo.Create(bucket)
	require.NoError(t, err)

	// Update to higher value (should update)
	updated, err := repo.UpdateHighWaterMark("satellite_hwm", 1500.0)
	require.NoError(t, err)
	assert.Equal(t, 1500.0, updated.HighWaterMark)
	assert.NotNil(t, updated.HighWaterMarkDate)

	// Try to update to lower value (should not update)
	beforeUpdate := updated.HighWaterMark
	updated, err = repo.UpdateHighWaterMark("satellite_hwm", 1200.0)
	require.NoError(t, err)
	assert.Equal(t, beforeUpdate, updated.HighWaterMark) // Should remain unchanged
}

func TestBucketRepository_Delete_CoreProtection(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBucketRepository(db, zerolog.Nop())

	// Try to delete core bucket
	err := repo.Delete("core")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "cannot delete core")
}

func TestBucketRepository_GetByType(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBucketRepository(db, zerolog.Nop())

	// Create core and satellites
	core := &Bucket{
		ID:                   "core",
		Name:                 "Core",
		Type:                 BucketTypeCore,
		Status:               BucketStatusActive,
		ConsecutiveLosses:    0,
		MaxConsecutiveLosses: 5,
		HighWaterMark:        0.0,
	}
	repo.Create(core)

	satellite1 := &Bucket{
		ID:                   "sat1",
		Name:                 "Satellite 1",
		Type:                 BucketTypeSatellite,
		Status:               BucketStatusActive,
		ConsecutiveLosses:    0,
		MaxConsecutiveLosses: 5,
		HighWaterMark:        0.0,
	}
	repo.Create(satellite1)

	satellite2 := &Bucket{
		ID:                   "sat2",
		Name:                 "Satellite 2",
		Type:                 BucketTypeSatellite,
		Status:               BucketStatusActive,
		ConsecutiveLosses:    0,
		MaxConsecutiveLosses: 5,
		HighWaterMark:        0.0,
	}
	repo.Create(satellite2)

	// Get satellites
	satellites, err := repo.GetByType(BucketTypeSatellite)
	require.NoError(t, err)
	assert.Len(t, satellites, 2)
}

func TestBucketRepository_GetActive(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBucketRepository(db, zerolog.Nop())

	// Create buckets with different statuses
	active := &Bucket{
		ID:                   "active1",
		Name:                 "Active",
		Type:                 BucketTypeSatellite,
		Status:               BucketStatusActive,
		ConsecutiveLosses:    0,
		MaxConsecutiveLosses: 5,
		HighWaterMark:        0.0,
	}
	repo.Create(active)

	paused := &Bucket{
		ID:                   "paused1",
		Name:                 "Paused",
		Type:                 BucketTypeSatellite,
		Status:               BucketStatusPaused,
		ConsecutiveLosses:    0,
		MaxConsecutiveLosses: 5,
		HighWaterMark:        0.0,
	}
	repo.Create(paused)

	// Get active (should exclude paused)
	activeBuckets, err := repo.GetActive()
	require.NoError(t, err)
	assert.Len(t, activeBuckets, 1)
	assert.Equal(t, "active1", activeBuckets[0].ID)
}

func TestBucketRepository_Settings(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBucketRepository(db, zerolog.Nop())

	// Create satellite
	satellite := &Bucket{
		ID:                   "satellite_settings",
		Name:                 "Test",
		Type:                 BucketTypeSatellite,
		Status:               BucketStatusActive,
		ConsecutiveLosses:    0,
		MaxConsecutiveLosses: 5,
		HighWaterMark:        0.0,
	}
	err := repo.Create(satellite)
	require.NoError(t, err)

	// Save settings
	preset := "momentum_hunter"
	settings := &SatelliteSettings{
		SatelliteID:         "satellite_settings",
		Preset:              &preset,
		RiskAppetite:        0.7,
		HoldDuration:        0.3,
		EntryStyle:          0.9,
		PositionSpread:      0.5,
		ProfitTaking:        0.6,
		TrailingStops:       true,
		FollowRegime:        false,
		AutoHarvest:         true,
		PauseHighVolatility: false,
		DividendHandling:    "send_to_core",
	}

	err = repo.SaveSettings(settings)
	require.NoError(t, err)

	// Retrieve settings
	retrieved, err := repo.GetSettings("satellite_settings")
	require.NoError(t, err)
	require.NotNil(t, retrieved)
	assert.Equal(t, "momentum_hunter", *retrieved.Preset)
	assert.Equal(t, 0.7, retrieved.RiskAppetite)
	assert.True(t, retrieved.TrailingStops)
	assert.True(t, retrieved.AutoHarvest)
	assert.Equal(t, "send_to_core", retrieved.DividendHandling)
}

func TestBucketRepository_Settings_Validation(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBucketRepository(db, zerolog.Nop())

	// Invalid settings (risk_appetite out of range)
	settings := &SatelliteSettings{
		SatelliteID:      "sat1",
		RiskAppetite:     1.5, // Invalid
		HoldDuration:     0.5,
		EntryStyle:       0.5,
		PositionSpread:   0.5,
		ProfitTaking:     0.5,
		DividendHandling: "reinvest_same",
	}

	err := repo.SaveSettings(settings)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "risk_appetite")
}

func TestBucketRepository_DeleteSettings(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	repo := NewBucketRepository(db, zerolog.Nop())

	// Create satellite
	satellite := &Bucket{
		ID:                   "satellite_delete_settings",
		Name:                 "Test",
		Type:                 BucketTypeSatellite,
		Status:               BucketStatusActive,
		ConsecutiveLosses:    0,
		MaxConsecutiveLosses: 5,
		HighWaterMark:        0.0,
	}
	repo.Create(satellite)

	// Save and delete settings
	settings := NewSatelliteSettings("satellite_delete_settings")
	repo.SaveSettings(settings)

	err := repo.DeleteSettings("satellite_delete_settings")
	require.NoError(t, err)

	// Verify deleted
	retrieved, err := repo.GetSettings("satellite_delete_settings")
	require.NoError(t, err)
	assert.Nil(t, retrieved)
}
