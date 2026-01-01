"""Base classes and registries for calculation modules.

Provides the foundation for pluggable calculation modules with
automatic registration and discovery.
"""

from typing import Dict, Generic, Optional, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    """Generic registry for modules."""

    def __init__(self):
        self._modules: Dict[str, T] = {}

    def register(self, name: str, module: T):
        """Register a module by name."""
        if name in self._modules:
            raise ValueError(f"Module '{name}' already registered")
        self._modules[name] = module

    def get(self, name: str) -> Optional[T]:
        """Get module by name."""
        return self._modules.get(name)

    def get_all(self) -> Dict[str, T]:
        """Get all registered modules."""
        return self._modules.copy()

    def list_names(self) -> list[str]:
        """List all registered module names."""
        return list(self._modules.keys())

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        count = len(self._modules)
        names = ", ".join(sorted(self._modules.keys()))
        return f"Registry({count} modules: {names})"


# Global registries (initialized by submodules)
#
# ARCHITECTURAL NOTE: These use global mutable state for pragmatic simplicity.
# Each module type (opportunities/, patterns/, sequences/, filters/) creates
# its own registry instance on import, and individual modules auto-register.
#
# Trade-offs:
# - PRO: Simple, no boilerplate, easy to add new modules
# - PRO: Import-time registration ensures all modules are available
# - CON: Import order matters (but handled by __init__.py)
# - CON: Testing requires careful setup (but registries are independent)
#
# This is a documented architectural decision prioritizing simplicity
# over pure dependency injection for the Arduino's constrained environment.
#
# See: CLAUDE.md "Architecture Violations" section
opportunity_calculator_registry: Optional[Registry] = None
pattern_generator_registry: Optional[Registry] = None
sequence_generator_registry: Optional[Registry] = None
filter_registry: Optional[Registry] = None
