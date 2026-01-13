package scheduler

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestCheckCoreDatabasesJob_Name(t *testing.T) {
	job := &CheckCoreDatabasesJob{
		log: zerolog.Nop(),
	}
	assert.Equal(t, "check_core_databases", job.Name())
}

func TestCheckCoreDatabasesJob_Run_NoDatabases(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	job := NewCheckCoreDatabasesJob(nil, nil, nil, nil)
	job.SetLogger(log)

	err := job.Run()
	assert.NoError(t, err) // Should handle nil databases gracefully
}

// Note: Full integration test would require actual database connections
// This is a basic unit test to verify the job structure
