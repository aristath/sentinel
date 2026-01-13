package scheduler

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestCheckWALCheckpointsJob_Name(t *testing.T) {
	job := &CheckWALCheckpointsJob{
		log: zerolog.Nop(),
	}
	assert.Equal(t, "check_wal_checkpoints", job.Name())
}

func TestCheckWALCheckpointsJob_Run_NoDatabases(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	job := NewCheckWALCheckpointsJob(nil, nil, nil, nil, nil, nil, nil)
	job.SetLogger(log)

	err := job.Run()
	assert.NoError(t, err) // Should handle nil databases gracefully
}
