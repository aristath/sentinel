package work

import (
	"context"
	"sync"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewRegistry(t *testing.T) {
	r := NewRegistry()

	assert.NotNil(t, r)
	assert.Equal(t, 0, r.Count())
}

func TestRegistry_Register(t *testing.T) {
	r := NewRegistry()

	wt := &WorkType{
		ID:       "test:work",
		Priority: PriorityMedium,
	}

	r.Register(wt)

	assert.Equal(t, 1, r.Count())
	assert.True(t, r.Has("test:work"))
}

func TestRegistry_RegisterOverwrites(t *testing.T) {
	r := NewRegistry()

	wt1 := &WorkType{
		ID:       "test:work",
		Priority: PriorityLow,
	}
	wt2 := &WorkType{
		ID:       "test:work",
		Priority: PriorityHigh,
	}

	r.Register(wt1)
	r.Register(wt2)

	assert.Equal(t, 1, r.Count())
	got := r.Get("test:work")
	assert.Equal(t, PriorityHigh, got.Priority)
}

func TestRegistry_Get(t *testing.T) {
	r := NewRegistry()

	wt := &WorkType{
		ID:           "security:sync",
		Priority:     PriorityMedium,
		MarketTiming: AfterMarketClose,
	}
	r.Register(wt)

	t.Run("returns registered work type", func(t *testing.T) {
		got := r.Get("security:sync")
		require.NotNil(t, got)
		assert.Equal(t, "security:sync", got.ID)
		assert.Equal(t, AfterMarketClose, got.MarketTiming)
	})

	t.Run("returns nil for unknown ID", func(t *testing.T) {
		got := r.Get("unknown:work")
		assert.Nil(t, got)
	})
}

func TestRegistry_Has(t *testing.T) {
	r := NewRegistry()

	r.Register(&WorkType{ID: "test:work"})

	assert.True(t, r.Has("test:work"))
	assert.False(t, r.Has("unknown:work"))
}

func TestRegistry_Remove(t *testing.T) {
	r := NewRegistry()

	r.Register(&WorkType{ID: "test:work"})
	assert.True(t, r.Has("test:work"))

	r.Remove("test:work")
	assert.False(t, r.Has("test:work"))
	assert.Equal(t, 0, r.Count())
}

func TestRegistry_IDs(t *testing.T) {
	r := NewRegistry()

	r.Register(&WorkType{ID: "planner:weights"})
	r.Register(&WorkType{ID: "security:sync"})
	r.Register(&WorkType{ID: "maintenance:backup"})

	ids := r.IDs()

	// IDs should be sorted alphabetically
	assert.Equal(t, []string{"maintenance:backup", "planner:weights", "security:sync"}, ids)
}

func TestRegistry_ByPriority(t *testing.T) {
	r := NewRegistry()

	// Register work types with different priorities
	r.Register(&WorkType{ID: "maintenance:backup", Priority: PriorityLow})
	r.Register(&WorkType{ID: "security:sync", Priority: PriorityMedium})
	r.Register(&WorkType{ID: "planner:weights", Priority: PriorityCritical})
	r.Register(&WorkType{ID: "sync:portfolio", Priority: PriorityHigh})
	r.Register(&WorkType{ID: "trading:execute", Priority: PriorityCritical})

	ordered := r.ByPriority()

	require.Len(t, ordered, 5)

	// Critical priority first (alphabetically within same priority)
	assert.Equal(t, "planner:weights", ordered[0].ID)
	assert.Equal(t, "trading:execute", ordered[1].ID)

	// High priority next
	assert.Equal(t, "sync:portfolio", ordered[2].ID)

	// Medium priority
	assert.Equal(t, "security:sync", ordered[3].ID)

	// Low priority last
	assert.Equal(t, "maintenance:backup", ordered[4].ID)
}

func TestRegistry_ByPriority_ReturnsACopy(t *testing.T) {
	r := NewRegistry()

	r.Register(&WorkType{ID: "test:work", Priority: PriorityMedium})

	ordered1 := r.ByPriority()
	ordered2 := r.ByPriority()

	// Modify one slice
	ordered1[0] = nil

	// The other should be unaffected
	assert.NotNil(t, ordered2[0])
}

func TestRegistry_GetDependencies(t *testing.T) {
	r := NewRegistry()

	r.Register(&WorkType{ID: "planner:weights"})
	r.Register(&WorkType{ID: "planner:context", DependsOn: []string{"planner:weights"}})
	r.Register(&WorkType{ID: "planner:plan", DependsOn: []string{"planner:context"}})

	t.Run("returns dependencies", func(t *testing.T) {
		deps := r.GetDependencies("planner:context")

		require.Len(t, deps, 1)
		assert.Equal(t, "planner:weights", deps[0].ID)
	})

	t.Run("returns nil for work type with no dependencies", func(t *testing.T) {
		deps := r.GetDependencies("planner:weights")

		assert.Len(t, deps, 0)
	})

	t.Run("returns nil for unknown work type", func(t *testing.T) {
		deps := r.GetDependencies("unknown:work")

		assert.Nil(t, deps)
	})

	t.Run("filters out missing dependencies", func(t *testing.T) {
		r.Register(&WorkType{ID: "test:orphan", DependsOn: []string{"missing:dep"}})

		deps := r.GetDependencies("test:orphan")

		assert.Len(t, deps, 0)
	})
}

func TestRegistry_GetDependents(t *testing.T) {
	r := NewRegistry()

	r.Register(&WorkType{ID: "planner:weights"})
	r.Register(&WorkType{ID: "planner:context", DependsOn: []string{"planner:weights"}})
	r.Register(&WorkType{ID: "planner:plan", DependsOn: []string{"planner:context"}})

	t.Run("returns dependents", func(t *testing.T) {
		dependents := r.GetDependents("planner:weights")

		require.Len(t, dependents, 1)
		assert.Equal(t, "planner:context", dependents[0].ID)
	})

	t.Run("returns empty for work type with no dependents", func(t *testing.T) {
		dependents := r.GetDependents("planner:plan")

		assert.Len(t, dependents, 0)
	})

	t.Run("returns empty for unknown work type", func(t *testing.T) {
		dependents := r.GetDependents("unknown:work")

		assert.Len(t, dependents, 0)
	})
}

func TestRegistry_ConcurrentAccess(t *testing.T) {
	r := NewRegistry()

	// Pre-register some work types
	for i := 0; i < 10; i++ {
		r.Register(&WorkType{ID: "initial:" + string(rune('a'+i))})
	}

	var wg sync.WaitGroup
	errCh := make(chan error, 100)

	// Concurrent reads
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				_ = r.Get("initial:a")
				_ = r.Has("initial:b")
				_ = r.Count()
				_ = r.IDs()
				_ = r.ByPriority()
			}
		}()
	}

	// Concurrent writes
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func(id int) {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				r.Register(&WorkType{ID: "concurrent:" + string(rune('a'+id))})
				r.Remove("concurrent:" + string(rune('a'+id)))
			}
		}(i)
	}

	wg.Wait()
	close(errCh)

	for err := range errCh {
		t.Errorf("concurrent access error: %v", err)
	}
}

func TestRegistry_FullWorkflowExample(t *testing.T) {
	r := NewRegistry()

	// Register a planner chain with dependencies
	r.Register(&WorkType{
		ID:       "planner:weights",
		Priority: PriorityCritical,
		FindSubjects: func() []string {
			return []string{""} // Global work
		},
		Execute: func(ctx context.Context, subject string) error {
			return nil
		},
	})

	r.Register(&WorkType{
		ID:        "planner:context",
		Priority:  PriorityCritical,
		DependsOn: []string{"planner:weights"},
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string) error {
			return nil
		},
	})

	r.Register(&WorkType{
		ID:        "planner:plan",
		Priority:  PriorityCritical,
		DependsOn: []string{"planner:context"},
		FindSubjects: func() []string {
			return []string{""}
		},
		Execute: func(ctx context.Context, subject string) error {
			return nil
		},
	})

	// Verify the chain
	assert.Equal(t, 3, r.Count())

	// Check dependency chain
	contextDeps := r.GetDependencies("planner:context")
	require.Len(t, contextDeps, 1)
	assert.Equal(t, "planner:weights", contextDeps[0].ID)

	planDeps := r.GetDependencies("planner:plan")
	require.Len(t, planDeps, 1)
	assert.Equal(t, "planner:context", planDeps[0].ID)

	// Check reverse dependencies
	weightsDependents := r.GetDependents("planner:weights")
	require.Len(t, weightsDependents, 1)
	assert.Equal(t, "planner:context", weightsDependents[0].ID)
}
