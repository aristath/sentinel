package work

import (
	"sort"
	"sync"
)

// Registry holds all registered work types and provides lookup by ID and priority ordering.
type Registry struct {
	types   map[string]*WorkType
	ordered []*WorkType // Ordered by priority (highest first)
	mu      sync.RWMutex
	reorder bool // Flag to indicate ordering needs refresh
}

// NewRegistry creates a new work type registry.
func NewRegistry() *Registry {
	return &Registry{
		types:   make(map[string]*WorkType),
		ordered: make([]*WorkType, 0),
	}
}

// Register adds a work type to the registry.
// If a work type with the same ID already exists, it will be replaced.
func (r *Registry) Register(wt *WorkType) {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.types[wt.ID] = wt
	r.reorder = true
}

// Get returns a work type by ID, or nil if not found.
func (r *Registry) Get(id string) *WorkType {
	r.mu.RLock()
	defer r.mu.RUnlock()

	return r.types[id]
}

// Has returns true if a work type with the given ID is registered.
func (r *Registry) Has(id string) bool {
	r.mu.RLock()
	defer r.mu.RUnlock()

	_, exists := r.types[id]
	return exists
}

// ByPriority returns all work types ordered by priority (highest first).
// Within the same priority, work types are ordered alphabetically by ID.
func (r *Registry) ByPriority() []*WorkType {
	r.mu.Lock()
	defer r.mu.Unlock()

	if r.reorder {
		r.refreshOrder()
		r.reorder = false
	}

	// Return a copy to prevent external modification
	result := make([]*WorkType, len(r.ordered))
	copy(result, r.ordered)
	return result
}

// refreshOrder rebuilds the ordered slice based on priority.
// Must be called with lock held.
func (r *Registry) refreshOrder() {
	r.ordered = make([]*WorkType, 0, len(r.types))
	for _, wt := range r.types {
		r.ordered = append(r.ordered, wt)
	}

	// Sort by priority (descending), then by ID (ascending) for deterministic order
	sort.Slice(r.ordered, func(i, j int) bool {
		if r.ordered[i].Priority != r.ordered[j].Priority {
			return r.ordered[i].Priority > r.ordered[j].Priority
		}
		return r.ordered[i].ID < r.ordered[j].ID
	})
}

// Count returns the number of registered work types.
func (r *Registry) Count() int {
	r.mu.RLock()
	defer r.mu.RUnlock()

	return len(r.types)
}

// Remove removes a work type from the registry.
func (r *Registry) Remove(id string) {
	r.mu.Lock()
	defer r.mu.Unlock()

	delete(r.types, id)
	r.reorder = true
}

// IDs returns all registered work type IDs.
func (r *Registry) IDs() []string {
	r.mu.RLock()
	defer r.mu.RUnlock()

	ids := make([]string, 0, len(r.types))
	for id := range r.types {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	return ids
}

// GetDependencies returns the work types that the given work type depends on.
func (r *Registry) GetDependencies(id string) []*WorkType {
	r.mu.RLock()
	defer r.mu.RUnlock()

	wt := r.types[id]
	if wt == nil {
		return nil
	}

	deps := make([]*WorkType, 0, len(wt.DependsOn))
	for _, depID := range wt.DependsOn {
		if dep := r.types[depID]; dep != nil {
			deps = append(deps, dep)
		}
	}
	return deps
}

// GetDependents returns the work types that depend on the given work type.
func (r *Registry) GetDependents(id string) []*WorkType {
	r.mu.RLock()
	defer r.mu.RUnlock()

	dependents := make([]*WorkType, 0)
	for _, wt := range r.types {
		for _, depID := range wt.DependsOn {
			if depID == id {
				dependents = append(dependents, wt)
				break
			}
		}
	}
	return dependents
}
