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


# Global registries (initialized by submodules)
opportunity_calculator_registry: Optional[Registry] = None
pattern_generator_registry: Optional[Registry] = None
sequence_generator_registry: Optional[Registry] = None
filter_registry: Optional[Registry] = None


def init_registries():
    """Initialize all global registries."""
    global opportunity_calculator_registry
    global pattern_generator_registry
    global sequence_generator_registry
    global filter_registry

    opportunity_calculator_registry = Registry()
    pattern_generator_registry = Registry()
    sequence_generator_registry = Registry()
    filter_registry = Registry()
