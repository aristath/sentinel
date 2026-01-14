package utils

import "strings"

// ParseCSV splits a comma-separated string and returns trimmed non-empty values.
// Returns nil for empty/whitespace-only input.
// This function is used throughout the codebase to parse comma-separated
// industry and geography values stored in the database.
func ParseCSV(s string) []string {
	if s == "" {
		return nil
	}

	var result []string
	for _, v := range strings.Split(s, ",") {
		trimmed := strings.TrimSpace(v)
		if trimmed != "" {
			result = append(result, trimmed)
		}
	}

	if len(result) == 0 {
		return nil
	}

	return result
}
