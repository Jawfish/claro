"""Test and suite decorators."""

import threading
from collections.abc import Callable, Sequence
from typing import Any, overload

from .types import Suite, Test

# Global registry of suites (thread-safe for free-threaded Python)
_suites_lock = threading.Lock()
_suites: list[Suite] = []


def get_suites() -> list[Suite]:
    """Get all registered suites (returns a copy for thread safety)."""
    with _suites_lock:
        return _suites.copy()


def clear_suites() -> None:
    """Clear all registered suites. Useful for testing."""
    with _suites_lock:
        _suites.clear()


# ============== Helper Functions ==============


def _generate_param_id(
    param_set: tuple[Any, ...] | dict[str, Any] | Any, index: int
) -> str:
    """Generate a human-readable ID for a parameter set."""
    try:
        if isinstance(param_set, dict):
            parts = [f"{k}={_short_repr(v)}" for k, v in list(param_set.items())[:3]]
            return ", ".join(parts)
        elif isinstance(param_set, (tuple, list)):
            parts = [_short_repr(v) for v in param_set[:3]]
            if len(param_set) > 3:
                parts.append("...")
            return ", ".join(parts)
        else:
            return _short_repr(param_set)
    except Exception:
        return str(index)


def _short_repr(value: Any, max_len: int = 20) -> str:
    """Get a short string representation of a value."""
    r = repr(value)
    if len(r) > max_len:
        return r[: max_len - 3] + "..."
    return r


# ============== Test Decorator ==============

# Type alias for test decorator
TestDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


def _make_decorator(
    *,
    skip: bool = False,
    skip_reason: str | None = None,
    timeout_seconds: float | None = None,
    params: list[Any] | None = None,
) -> TestDecorator:
    """Create a test decorator with the given settings."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn._is_test = True  # type: ignore[attr-defined]
        fn._skip = skip  # type: ignore[attr-defined]
        fn._skip_reason = skip_reason  # type: ignore[attr-defined]
        fn._timeout = timeout_seconds  # type: ignore[attr-defined]
        fn._params = params  # type: ignore[attr-defined]
        return fn

    return decorator


class _TestMarker:
    """
    Decorator for marking test methods.

    Each modifier returns a terminal decorator that cannot be chained.

    Usage:
        @test
        def basic_test(self): ...

        @test.skip
        def skipped_test(self): ...

        @test.skip_if(condition, "reason")
        def conditional_test(self): ...

        @test.timeout(5.0)
        def slow_test(self): ...

        @test.each([(1, 2, 3), (2, 3, 5)])
        def parametrized(self, a, b, expected): ...

        @test.each([(1, 2, 3)], timeout=5.0)
        def parametrized_with_timeout(self, a, b, expected): ...
    """

    def __call__(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Basic @test decorator."""
        return _make_decorator()(fn)

    @property
    def skip(self) -> TestDecorator:
        """Mark test as skipped."""
        return _make_decorator(skip=True)

    def skip_if(self, condition: bool, reason: str = "") -> TestDecorator:
        """Conditionally skip test if condition is true."""
        if condition:
            return _make_decorator(skip=True, skip_reason=reason)
        return _make_decorator()

    def timeout(self, seconds: float) -> TestDecorator:
        """Set a timeout for this specific test."""
        return _make_decorator(timeout_seconds=seconds)

    def each(
        self,
        params: Sequence[tuple[Any, ...] | dict[str, Any] | Any],
        *,
        timeout: float | None = None,
    ) -> TestDecorator:
        """
        Create parametrized tests.

        Args:
            params: List of parameter sets. Each can be:
                - tuple: positional args
                - dict: keyword args (can include 'id' for custom name)
                - single value: passed as single arg
            timeout: Optional timeout for each parametrized test (seconds).

        Example:
            @test.each([
                (1, 2, 3),
                (0, 0, 0),
                {"a": 1, "b": 2, "expected": 3, "id": "positive"},
            ])
            def adds(self, a, b, expected):
                expect(a + b).to_be(expected)
        """
        return _make_decorator(params=list(params), timeout_seconds=timeout)


# Singleton instance
test = _TestMarker()


# ============== Lifecycle Decorators ==============


def before_each(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Mark a method to run before each test."""
    fn._is_before_each = True  # type: ignore[attr-defined]
    return fn


def after_each(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Mark a method to run after each test."""
    fn._is_after_each = True  # type: ignore[attr-defined]
    return fn


def before_all(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Mark a method to run once before all tests in the suite."""
    fn._is_before_all = True  # type: ignore[attr-defined]
    return fn


def after_all(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Mark a method to run once after all tests in the suite."""
    fn._is_after_all = True  # type: ignore[attr-defined]
    return fn


# ============== Suite Decorator ==============


def _create_test(
    name: str,
    fn: Callable[..., Any],
    params: Any = None,
    param_id: str | None = None,
) -> Test:
    """Create a Test from a decorated function, extracting its metadata."""
    return Test(
        name=name,
        fn=fn,
        skip=getattr(fn, "_skip", False),
        skip_reason=getattr(fn, "_skip_reason", None),
        timeout=getattr(fn, "_timeout", None),
        params=params,
        param_id=param_id,
    )


@overload
def suite(cls: type) -> type: ...


@overload
def suite(
    cls: None = None,
    *,
    timeout: float | None = None,
) -> Callable[[type], type]: ...


def suite(
    cls: type | None = None,
    *,
    timeout: float | None = None,
) -> type | Callable[[type], type]:
    """
    Class decorator that registers a test suite.

    Args:
        timeout: Default timeout for tests in this suite (in seconds).

    Usage:
        @suite
        class MyTests:
            @test
            def example(self): ...

        @suite(timeout=5.0)
        class SlowTests:
            ...
    """

    def decorator(cls: type) -> type:
        s = Suite(
            name=cls.__name__,
            cls=cls,
            timeout=timeout,
        )

        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue

            attr = getattr(cls, attr_name)

            if getattr(attr, "_is_test", False):
                # Handle parametrized tests
                params_list = getattr(attr, "_params", None)

                if params_list:
                    for i, param_set in enumerate(params_list):
                        # Generate human-readable param ID
                        if isinstance(param_set, dict) and "id" in param_set:
                            param_set = dict(param_set)  # Copy to avoid mutating
                            param_id = param_set.pop("id")
                        else:
                            param_id = _generate_param_id(param_set, i)

                        s.tests.append(
                            _create_test(
                                f"{attr_name}[{param_id}]", attr, param_set, param_id
                            )
                        )
                else:
                    s.tests.append(_create_test(attr_name, attr))

            elif getattr(attr, "_is_before_each", False):
                s.before_each = attr
            elif getattr(attr, "_is_after_each", False):
                s.after_each = attr
            elif getattr(attr, "_is_before_all", False):
                s.before_all = attr
            elif getattr(attr, "_is_after_all", False):
                s.after_all = attr

        cls._suite_data = s  # type: ignore[attr-defined]
        with _suites_lock:
            _suites.append(s)
        return cls

    if cls is not None:
        return decorator(cls)
    return decorator
