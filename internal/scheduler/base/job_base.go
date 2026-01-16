// Package base provides base implementation for scheduler jobs.
package base

// JobBase provides a default SetJob implementation and progress reporter access
// Jobs can embed this to satisfy the Job interface and get progress reporting support
type JobBase struct {
	queueJob interface{}
}

// SetJob stores the queue job reference for progress reporting
func (j *JobBase) SetJob(qj interface{}) {
	j.queueJob = qj
}

// GetProgressReporter returns the progress reporter for this job (may be nil)
// Returns interface{} to avoid import cycles - caller must type assert to the appropriate progress reporter type
func (j *JobBase) GetProgressReporter() interface{} {
	if j.queueJob == nil {
		return nil
	}
	// Use reflection to call GetProgressReporter on the queue job
	// This avoids importing queue package which would create a cycle
	type progressReporterGetter interface {
		GetProgressReporter() interface{}
	}
	if getter, ok := j.queueJob.(progressReporterGetter); ok {
		return getter.GetProgressReporter()
	}
	return nil
}
