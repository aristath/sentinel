package progress

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestCall_NilCallback(t *testing.T) {
	// Should not panic when callback is nil
	assert.NotPanics(t, func() {
		Call(nil, 5, 10, "test message")
	})
}

func TestCall_InvokesCallback(t *testing.T) {
	var capturedCurrent, capturedTotal int
	var capturedMessage string

	cb := func(current, total int, message string) {
		capturedCurrent = current
		capturedTotal = total
		capturedMessage = message
	}

	Call(cb, 5, 10, "Generating sequences")

	assert.Equal(t, 5, capturedCurrent)
	assert.Equal(t, 10, capturedTotal)
	assert.Equal(t, "Generating sequences", capturedMessage)
}

func TestCall_MultipleInvocations(t *testing.T) {
	var invocations []struct {
		current int
		total   int
		message string
	}

	cb := func(current, total int, message string) {
		invocations = append(invocations, struct {
			current int
			total   int
			message string
		}{current, total, message})
	}

	Call(cb, 1, 100, "Step 1")
	Call(cb, 50, 100, "Step 2")
	Call(cb, 100, 100, "Complete")

	assert.Len(t, invocations, 3)
	assert.Equal(t, 1, invocations[0].current)
	assert.Equal(t, 50, invocations[1].current)
	assert.Equal(t, 100, invocations[2].current)
}

func TestCallback_ZeroValues(t *testing.T) {
	var capturedCurrent, capturedTotal int
	var capturedMessage string

	cb := func(current, total int, message string) {
		capturedCurrent = current
		capturedTotal = total
		capturedMessage = message
	}

	// Zero values should be passed through without issue
	Call(cb, 0, 0, "")

	assert.Equal(t, 0, capturedCurrent)
	assert.Equal(t, 0, capturedTotal)
	assert.Equal(t, "", capturedMessage)
}

// Tests for DetailedCallback

func TestUpdate_Structure(t *testing.T) {
	update := Update{
		Phase:    "sequence_generation",
		SubPhase: "depth_3",
		Current:  3,
		Total:    8,
		Message:  "Generating depth 3 sequences",
		Details: map[string]any{
			"candidates_count":      15,
			"combinations_at_depth": 455,
			"sequences_generated":   200,
		},
	}

	assert.Equal(t, "sequence_generation", update.Phase)
	assert.Equal(t, "depth_3", update.SubPhase)
	assert.Equal(t, 3, update.Current)
	assert.Equal(t, 8, update.Total)
	assert.Equal(t, "Generating depth 3 sequences", update.Message)
	assert.Equal(t, 15, update.Details["candidates_count"])
	assert.Equal(t, 455, update.Details["combinations_at_depth"])
}

func TestCallDetailed_NilCallback(t *testing.T) {
	update := Update{
		Phase:   "test",
		Current: 1,
		Total:   10,
	}

	// Should not panic when callback is nil
	assert.NotPanics(t, func() {
		CallDetailed(nil, update)
	})
}

func TestCallDetailed_InvokesCallback(t *testing.T) {
	var capturedUpdate Update

	cb := func(u Update) {
		capturedUpdate = u
	}

	update := Update{
		Phase:    "sequence_generation",
		SubPhase: "depth_5",
		Current:  5,
		Total:    8,
		Message:  "Generating depth 5 sequences",
		Details: map[string]any{
			"candidates_count": 20,
		},
	}

	CallDetailed(cb, update)

	assert.Equal(t, "sequence_generation", capturedUpdate.Phase)
	assert.Equal(t, "depth_5", capturedUpdate.SubPhase)
	assert.Equal(t, 5, capturedUpdate.Current)
	assert.Equal(t, 8, capturedUpdate.Total)
	assert.Equal(t, "Generating depth 5 sequences", capturedUpdate.Message)
	assert.Equal(t, 20, capturedUpdate.Details["candidates_count"])
}

func TestCallDetailed_MultipleInvocations(t *testing.T) {
	var invocations []Update

	cb := func(u Update) {
		invocations = append(invocations, u)
	}

	CallDetailed(cb, Update{Phase: "phase1", Current: 1, Total: 3})
	CallDetailed(cb, Update{Phase: "phase2", Current: 2, Total: 3})
	CallDetailed(cb, Update{Phase: "phase3", Current: 3, Total: 3})

	assert.Len(t, invocations, 3)
	assert.Equal(t, "phase1", invocations[0].Phase)
	assert.Equal(t, "phase2", invocations[1].Phase)
	assert.Equal(t, "phase3", invocations[2].Phase)
}

func TestCallDetailed_NilDetails(t *testing.T) {
	var capturedUpdate Update

	cb := func(u Update) {
		capturedUpdate = u
	}

	update := Update{
		Phase:   "test",
		Current: 1,
		Total:   10,
		Details: nil, // nil details should be handled gracefully
	}

	CallDetailed(cb, update)

	assert.Nil(t, capturedUpdate.Details)
}
