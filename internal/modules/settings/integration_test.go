package settings_test

import (
	"testing"

	"github.com/aristath/sentinel/internal/modules/settings"
	"github.com/stretchr/testify/assert"
)

func TestSettingDefaults_OnlyJobAutoDeployExists(t *testing.T) {
	// Verify SettingDefaults map has correct job_ settings
	defaults := settings.SettingDefaults

	// Should exist
	_, hasAutoDeploy := defaults["job_auto_deploy_minutes"]
	assert.True(t, hasAutoDeploy, "job_auto_deploy_minutes should exist")

	// Should NOT exist
	_, hasSyncCycle := defaults["job_sync_cycle_minutes"]
	assert.False(t, hasSyncCycle, "job_sync_cycle_minutes should NOT exist")

	_, hasMaintenanceHour := defaults["job_maintenance_hour"]
	assert.False(t, hasMaintenanceHour, "job_maintenance_hour should NOT exist")
}

func TestSettingDescriptions_JobAutoDeployHasDescription(t *testing.T) {
	descriptions := settings.SettingDescriptions

	// job_auto_deploy_minutes should have description
	desc, exists := descriptions["job_auto_deploy_minutes"]
	assert.True(t, exists, "job_auto_deploy_minutes should have description")

	// Description should mention it's the only configurable interval
	assert.Contains(t, desc, "user-configurable", "Description should mention user-configurable")
}
