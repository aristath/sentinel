package yahoo

import (
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
)

func TestNewNativeClient(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	client := NewNativeClient(log)

	assert.NotNil(t, client)
	assert.NotNil(t, client.log)
}

func TestNativeClient_ImplementsFullClientInterface(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)
	client := NewNativeClient(log)

	// Ensure NativeClient implements FullClientInterface
	var _ FullClientInterface = client
}
