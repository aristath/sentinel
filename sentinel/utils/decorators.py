"""Utility decorators for the Sentinel codebase."""

import functools
from typing import Any, TypeVar

T = TypeVar("T")


def singleton(cls: type[T]) -> type[T]:
    """
    Singleton decorator for classes.

    Ensures only one instance of the class exists within a single thread.
    Safe for single-threaded async usage, but NOT thread-safe for concurrent
    access from multiple threads (lacks proper locking mechanisms).

    Usage:
        @singleton
        class MyClass:
            def __init__(self):
                self._db = Database()

        a = MyClass()
        b = MyClass()
        assert a is b
    """
    instances: dict[type[Any], Any] = {}

    @functools.wraps(cls)
    def get_instance(*args: Any, **kwargs: Any) -> T:
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    # Store reference for testing/reset purposes
    get_instance._instances = instances  # type: ignore
    get_instance._clear = lambda: instances.clear()  # type: ignore

    return get_instance  # type: ignore
