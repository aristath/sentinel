// Package progress provides progress reporting utilities for long-running planning operations.
package progress

// Callback is a function that reports progress during long operations.
// Parameters:
//   - current: Number of items completed
//   - total: Total number of items
//   - message: Human-readable description of the current phase
//
// A nil Callback is valid and will be safely ignored by the Call() helper.
type Callback func(current, total int, message string)

// Call safely invokes the callback if non-nil.
// This allows callers to pass progress updates without checking for nil.
func Call(cb Callback, current, total int, message string) {
	if cb != nil {
		cb(current, total, message)
	}
}

// Update represents a detailed progress update with hierarchical phase information.
// Used for rich progress reporting in the planner pipeline.
type Update struct {
	Phase    string         // Phase identifier (e.g., "sequence_generation", "sequence_evaluation")
	SubPhase string         // Sub-phase identifier (e.g., "depth_3", "batch_1")
	Current  int            // Current progress count within the phase
	Total    int            // Total items to process in the phase
	Message  string         // Human-readable progress message
	Details  map[string]any // Arbitrary metrics for debugging (e.g., combinations_at_depth, duplicates_removed)
}

// DetailedCallback is a function that receives detailed progress updates.
// A nil DetailedCallback is valid and will be safely ignored by CallDetailed().
type DetailedCallback func(update Update)

// CallDetailed safely invokes the detailed callback if non-nil.
// This allows callers to pass progress updates without checking for nil.
func CallDetailed(cb DetailedCallback, update Update) {
	if cb != nil {
		cb(update)
	}
}
