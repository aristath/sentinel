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
