"""Fixture system for dependency injection."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal, get_args, get_origin, get_type_hints


class Inject:
    """Marker for dependency injection in type annotations.

    Usage:
        @test
        def my_test(self, db: Annotated[Database, Inject]):
            ...
    """

    pass


Scope = Literal["test", "suite", "session"]


@dataclass(slots=True)
class FixtureDef:
    """Definition of a registered fixture."""

    fn: Callable[..., Any]
    return_type: type
    scope: Scope
    is_generator: bool  # True if fn uses yield (needs cleanup)


# Global fixture registry: return_type -> FixtureDef
_fixtures: dict[type, FixtureDef] = {}


def get_fixtures() -> dict[type, FixtureDef]:
    """Get all registered fixtures (returns a copy for safety)."""
    return _fixtures.copy()


def clear_fixtures() -> None:
    """Clear all registered fixtures. Useful for testing."""
    _fixtures.clear()


def fixture(
    fn: Callable[..., Any] | None = None,
    *,
    scope: Scope = "test",
) -> Callable[..., Any]:
    """
    Decorator to register a fixture.

    Usage:
        @fixture
        def database() -> Database:
            return Database()

        @fixture(scope="suite")
        def shared_resource() -> Resource:
            r = Resource()
            yield r
            r.cleanup()

        @fixture(scope="session")
        def config() -> Config:
            return Config.from_env()

    Args:
        scope: Fixture lifetime - "test" (per-test), "suite" (per-class),
               or "session" (entire run).
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        hints = get_type_hints(fn)
        return_type = hints.get("return")
        if return_type is None:
            name = getattr(fn, "__name__", repr(fn))
            msg = f"Fixture {name} must have a return type annotation"
            raise TypeError(msg)

        # Handle Generator[T, None, None] return types from yield fixtures
        origin = get_origin(return_type)
        if origin is not None:
            # For Generator[T, None, None], extract T
            import collections.abc

            if origin in (collections.abc.Generator, collections.abc.AsyncGenerator):
                args = get_args(return_type)
                if args:
                    return_type = args[0]

        # Check for duplicate fixtures
        if return_type in _fixtures:
            existing_name = getattr(_fixtures[return_type].fn, "__name__", "unknown")
            new_name = getattr(fn, "__name__", "unknown")
            msg = (
                f"Duplicate fixture for type {return_type.__name__}: "
                f"'{existing_name}' and '{new_name}'"
            )
            raise TypeError(msg)

        # Check if it's a generator (uses yield)
        is_gen = inspect.isgeneratorfunction(fn) or inspect.isasyncgenfunction(fn)

        _fixtures[return_type] = FixtureDef(
            fn=fn,
            return_type=return_type,
            scope=scope,
            is_generator=is_gen,
        )
        return fn

    if fn is not None:
        return decorator(fn)
    return decorator


def is_inject_annotation(hint: Any) -> tuple[bool, type | None]:
    """
    Check if a type hint is Annotated[T, Inject].

    Returns:
        (is_injectable, inner_type) - inner_type is None if not injectable.
    """
    if get_origin(hint) is Annotated:
        args = get_args(hint)
        if len(args) >= 2 and args[1] is Inject:
            return True, args[0]
    return False, None


def get_injectable_params(fn: Callable[..., Any]) -> dict[str, type]:
    """
    Get all parameters that need injection from a function.

    Returns:
        {param_name: expected_type} for all Annotated[T, Inject] params.
    """
    try:
        hints = get_type_hints(fn, include_extras=True)
    except Exception:
        return {}

    result = {}
    for name, hint in hints.items():
        if name == "return":
            continue
        is_injectable, inner_type = is_inject_annotation(hint)
        if is_injectable and inner_type is not None:
            result[name] = inner_type
    return result


class FixtureError(Exception):
    """Raised when fixture resolution fails."""

    pass
