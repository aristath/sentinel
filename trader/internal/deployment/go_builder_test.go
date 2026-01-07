package deployment

import (
	"os"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestEscapeFlagValue(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{
			name:     "no special characters",
			input:    "simple_value",
			expected: "simple_value",
		},
		{
			name:     "with double quotes",
			input:    `value"with"quotes`,
			expected: `value\"with\"quotes`,
		},
		{
			name:     "empty string",
			input:    "",
			expected: "",
		},
		{
			name:     "only quotes",
			input:    `""`,
			expected: `\"\"`,
		},
		{
			name:     "quotes at start and end",
			input:    `"value"`,
			expected: `\"value\"`,
		},
		{
			name:     "multiple quotes",
			input:    `"one"two"three"`,
			expected: `\"one\"two\"three\"`,
		},
		{
			name:     "with spaces",
			input:    "value with spaces",
			expected: "value with spaces",
		},
		{
			name:     "quotes and spaces",
			input:    `"value with spaces"`,
			expected: `\"value with spaces\"`,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := escapeFlagValue(tt.input)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestGetEnv(t *testing.T) {
	// Save original environment
	originalValue := os.Getenv("TEST_ENV_VAR")
	defer func() {
		if originalValue != "" {
			os.Setenv("TEST_ENV_VAR", originalValue)
		} else {
			os.Unsetenv("TEST_ENV_VAR")
		}
	}()

	tests := []struct {
		name         string
		key          string
		setValue     string
		defaultValue string
		expected     string
	}{
		{
			name:         "env var exists",
			key:          "TEST_ENV_VAR",
			setValue:     "actual_value",
			defaultValue: "default_value",
			expected:     "actual_value",
		},
		{
			name:         "env var not set",
			key:          "TEST_ENV_VAR",
			setValue:     "",
			defaultValue: "default_value",
			expected:     "default_value",
		},
		{
			name:         "env var set to empty string",
			key:          "TEST_ENV_VAR",
			setValue:     "",
			defaultValue: "default_value",
			expected:     "default_value",
		},
		{
			name:         "default is empty string",
			key:          "TEST_ENV_VAR",
			setValue:     "",
			defaultValue: "",
			expected:     "",
		},
		{
			name:         "non-existent key",
			key:          "NON_EXISTENT_VAR",
			setValue:     "",
			defaultValue: "fallback",
			expected:     "fallback",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.setValue != "" {
				os.Setenv(tt.key, tt.setValue)
			} else {
				os.Unsetenv(tt.key)
			}

			result := getEnv(tt.key, tt.defaultValue)
			assert.Equal(t, tt.expected, result)
		})
	}
}
