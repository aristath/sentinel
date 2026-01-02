package scorers

import (
	"fmt"
	"math"
)

// round1 rounds to 1 decimal place
func round1(f float64) float64 {
	return math.Round(f*10) / 10
}

// round2 rounds to 2 decimal places
func round2(f float64) float64 {
	return math.Round(f*100) / 100
}

// roundPercent formats a percentage with label (helper for windfall reasons)
func roundPercent(label string, pct float64) string {
	if label == "" {
		return fmt.Sprintf("%.0f", pct)
	}
	return fmt.Sprintf("%s: %.0f%%", label, pct)
}
