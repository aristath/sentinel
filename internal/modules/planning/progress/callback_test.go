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
