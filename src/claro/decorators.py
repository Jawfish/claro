"""Test and suite decorators."""

import threading
from collections.abc import Callable, Sequence
from typing import Any, overload

from .types import RunMode, Suite, Test

# Global registry of suites (thread-safe for free-threaded Python)
_suites_lock = threading.Lock()
_suites: list[Suite] = []

# Lock for tests that need exclusive registry access across their entire execution
# Use RLock so nested acquisition (e.g., in before_each + test) works
_registry_test_lock = threading.RLock()


def get_suites() -> list[Suite]:
    """Get all registered suites."""
    return _suites


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


class _TestMarker:
    """
    Decorator for marking test methods.

    Usage:
        @test
        def basic_test(self): ...

        @test.skip
        def skipped_test(self): ...

        @test.only
        def focused_test(self): ...

        @test.todo
        def future_test(self): ...

        @test.skip_if(condition, "reason")
        def conditional_test(self): ...

        @test.timeout(5.0)
        def slow_test(self): ...

        @test.each([(1, 2, 3), (2, 3, 5)])
        def parametrized(self, a, b, expected): ...
    """

    def __init__(
        self,
        *,
        skip: bool = False,
        only: bool = False,
        todo: bool = False,
        skip_reason: str | None = None,
        timeout_seconds: float | None = None,
        params: list[Any] | None = None,
    ):
        self._skip = skip
        self._only = only
        self._todo = todo
        self._skip_reason = skip_reason
        self._timeout = timeout_seconds
        self._params = params

    def __call__(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Apply the test marker to a function."""
        fn._is_test = True  # type: ignore[attr-defined]
        fn._skip = self._skip  # type: ignore[attr-defined]
        fn._only = self._only  # type: ignore[attr-defined]
        fn._todo = self._todo  # type: ignore[attr-defined]
        fn._skip_reason = self._skip_reason  # type: ignore[attr-defined]
        fn._timeout = self._timeout  # type: ignore[attr-defined]
        fn._params = self._params  # type: ignore[attr-defined]
        return fn

    @property
    def skip(self) -> "_TestMarker":
        """Mark test as skipped."""
        return _TestMarker(skip=True)

    @property
    def only(self) -> "_TestMarker":
        """Mark test to run exclusively (focus mode)."""
        return _TestMarker(only=True)

    @property
    def todo(self) -> "_TestMarker":
        """Mark test as a placeholder (not implemented)."""
        return _TestMarker(todo=True)

    def skip_if(self, condition: bool, reason: str = "") -> "_TestMarker":
        """Conditionally skip test if condition is true."""
        if condition:
            return _TestMarker(skip=True, skip_reason=reason)
        return _TestMarker()

    def timeout(self, seconds: float) -> "_TestMarker":
        """Set a timeout for this specific test."""
        return _TestMarker(timeout_seconds=seconds)

    def each(
        self, params: Sequence[tuple[Any, ...] | dict[str, Any] | Any]
    ) -> "_TestMarker":
        """
        Create parametrized tests.

        Args:
            params: List of parameter sets. Each can be:
                - tuple: positional args
                - dict: keyword args (can include 'id' for custom name)
                - single value: passed as single arg

        Example:
            @test.each([
                (1, 2, 3),
                (0, 0, 0),
                {"a": 1, "b": 2, "expected": 3, "id": "positive"},
            ])
            def adds(self, a, b, expected):
                expect(a + b).to_be(expected)
        """
        return _TestMarker(params=list(params))


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


@overload
def suite(cls: type) -> type: ...


@overload
def suite(
    cls: None = None,
    *,
    sequential: bool = False,
    timeout: float | None = None,
) -> Callable[[type], type]: ...


def suite(
    cls: type | None = None,
    *,
    sequential: bool = False,
    timeout: float | None = None,
) -> type | Callable[[type], type]:
    """
    Class decorator that registers a test suite.

    Args:
        sequential: If True, run tests sequentially instead of in parallel.
        timeout: Default timeout for tests in this suite (in seconds).

    Usage:
        @suite
        class MyTests:
            @test
            def example(self): ...

        @suite(sequential=True, timeout=5.0)
        class SlowTests:
            ...
    """

    def decorator(cls: type) -> type:
        s = Suite(
            name=cls.__name__,
            cls=cls,
            mode=RunMode.SEQUENTIAL if sequential else RunMode.PARALLEL,
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

                        test_name = f"{attr_name}[{param_id}]"

                        s.tests.append(
                            Test(
                                name=test_name,
                                fn=attr,
                                skip=getattr(attr, "_skip", False),
                                only=getattr(attr, "_only", False),
                                todo=getattr(attr, "_todo", False),
                                skip_reason=getattr(attr, "_skip_reason", None),
                                timeout=getattr(attr, "_timeout", None),
                                params=param_set,
                                param_id=param_id,
                            )
                        )
                else:
                    s.tests.append(
                        Test(
                            name=attr_name,
                            fn=attr,
                            skip=getattr(attr, "_skip", False),
                            only=getattr(attr, "_only", False),
                            todo=getattr(attr, "_todo", False),
                            skip_reason=getattr(attr, "_skip_reason", None),
                            timeout=getattr(attr, "_timeout", None),
                        )
                    )

            elif getattr(attr, "_is_suite", False):
                s.children.append(attr._suite_data)
            elif getattr(attr, "_is_before_each", False):
                s.before_each = attr
            elif getattr(attr, "_is_after_each", False):
                s.after_each = attr
            elif getattr(attr, "_is_before_all", False):
                s.before_all = attr
            elif getattr(attr, "_is_after_all", False):
                s.after_all = attr

        cls._suite_data = s  # type: ignore[attr-defined]
        cls._is_suite = True  # type: ignore[attr-defined]
        # Only add top-level suites to the global registry
        # Nested suites are already tracked via parent.children
        # and will be removed from _suites during discovery
        with _suites_lock:
            _suites.append(s)
        return cls

    if cls is not None:
        return decorator(cls)
    return decorator


# ============== Custom Matcher Decorator ==============


def matcher(fn: Callable[..., bool | tuple[bool, str]]) -> Any:
    """
    Decorator to create custom matchers from simple functions.

    The decorated function should take (value, *args, **kwargs) and return
    either a bool, or a tuple of (bool, message).

    Usage:
        @matcher
        def is_even(value):
            return value % 2 == 0, f"expected {value} to be even"

        @matcher
        def is_weekday(value, day):
            return value.weekday() == day

        # Use with expect().to_satisfy()
        expect(4).to_satisfy(is_even)
        expect(date).to_satisfy(is_weekday(5))  # Saturday
    """
    fn_name = getattr(fn, "__name__", "matcher")

    def wrapper(*args: Any, **kwargs: Any) -> Callable[[Any], tuple[bool, str]]:
        def check(value: Any) -> tuple[bool, str]:
            result = fn(value, *args, **kwargs)
            if isinstance(result, tuple):
                return result  # (bool, message)
            # Auto-generate message from function name
            name = fn_name.replace("_", " ")
            return result, f"expected value to satisfy: {name}"

        return check

    # Allow calling without args for simple matchers
    if not _args_required(fn):
        wrapper._no_args = True  # type: ignore[attr-defined]

    wrapper._matcher_fn = fn  # type: ignore[attr-defined]
    return wrapper


def _args_required(fn: Callable[..., Any]) -> bool:
    """Check if function requires args beyond the first (value) parameter."""
    import inspect

    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    # Skip first param (value), check if others have no defaults
    for p in params[1:]:
        if p.default is inspect.Parameter.empty and p.kind not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            return True
    return False
