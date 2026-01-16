package scheduler

import "github.com/aristath/sentinel/internal/scheduler/base"

// JobBase re-exports base.JobBase for backward compatibility
// Jobs in the scheduler package can embed this directly
// Note: GetProgressReporter() returns interface{} - type assert to the appropriate progress reporter type when needed
type JobBase = base.JobBase
