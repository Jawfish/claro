"""Fluent assertion interface."""

import inspect
import re
from functools import lru_cache
from typing import Any, TypeVar

from .types import MISSING, ExpectationError

T = TypeVar("T")


@lru_cache(maxsize=128)
def _compile_pattern(pattern: str) -> re.Pattern[str]:
    """Cache compiled regex patterns to avoid recompilation."""
    return re.compile(pattern)


class Expectation:
    """
    Fluent assertion interface.

    Usage:
        expect(value).to_be(expected)
        expect(value).not_.to_be(unexpected)
        expect(items).to_contain(item)
        await expect(func).to_raise(ValueError)
    """

    __slots__ = ("value", "_negated")

    def __init__(self, value: Any, *, negated: bool = False):
        self.value = value
        self._negated = negated

    @property
    def not_(self) -> "Expectation":
        """Negate the next assertion."""
        return Expectation(self.value, negated=not self._negated)

    @property
    def to_not(self) -> "Expectation":
        """Alias for not_."""
        return self.not_

    def _check(
        self,
        condition: bool,
        message: str,
        expected: Any = MISSING,
        actual: Any = MISSING,
        *,
        show_diff: bool = True,
    ) -> None:
        """Check a condition. Raises ExpectationError if condition is false."""
        if self._negated:
            condition = not condition
            message = f"NOT {message}"

        if not condition:
            raise ExpectationError(
                message,
                expected=expected,
                actual=actual,
                show_diff=show_diff,
            )

    # ===== Equality =====

    def to_be(self, expected: Any) -> None:
        """Assert strict equality (==)."""
        self._check(
            self.value == expected,
            f"Expected {self.value!r} to be {expected!r}",
            expected=expected,
            actual=self.value,
        )

    def to_equal(self, expected: Any) -> None:
        """Alias for to_be."""
        self.to_be(expected)

    def to_be_same(self, expected: Any) -> None:
        """Assert identity (is)."""
        self._check(
            self.value is expected,
            f"Expected {self.value!r} to be the same object as {expected!r}",
            show_diff=False,
        )

    # ===== Truthiness =====

    def to_be_truthy(self) -> None:
        """Assert value is truthy."""
        self._check(
            bool(self.value),
            f"Expected {self.value!r} to be truthy",
            show_diff=False,
        )

    def to_be_falsy(self) -> None:
        """Assert value is falsy."""
        self._check(
            not bool(self.value),
            f"Expected {self.value!r} to be falsy",
            show_diff=False,
        )

    def to_be_none(self) -> None:
        """Assert value is None."""
        self._check(
            self.value is None,
            f"Expected {self.value!r} to be None",
            expected=None,
            actual=self.value,
        )

    def to_be_defined(self) -> None:
        """Assert value is not None."""
        self._check(
            self.value is not None,
            "Expected value to be defined (not None)",
            show_diff=False,
        )

    # ===== Type Checking =====

    def to_be_instance_of(self, cls: type) -> None:
        """Assert value is an instance of the given class."""
        self._check(
            isinstance(self.value, cls),
            f"Expected {self.value!r} to be instance of {cls.__name__}, "
            f"got {type(self.value).__name__}",
            show_diff=False,
        )

    def to_be_type(self, expected_type: type) -> None:
        """Assert value's type is exactly the given type."""
        self._check(
            type(self.value) is expected_type,
            f"Expected type {expected_type.__name__}, got {type(self.value).__name__}",
            show_diff=False,
        )

    # ===== Numeric Comparisons =====

    def to_be_close_to(self, expected: float, *, delta: float = 1e-9) -> None:
        """Assert float value is within delta of expected."""
        import math

        actual = float(self.value)

        # Handle NaN - NaN is never close to anything, including itself
        if math.isnan(actual) or math.isnan(expected):
            self._check(
                False,
                f"Cannot compare NaN values: actual={actual!r}, expected={expected!r}",
                show_diff=False,
            )
            return

        # Handle Infinity - infinities are only equal to themselves
        if math.isinf(actual) or math.isinf(expected):
            self._check(
                actual == expected,
                f"Expected {actual!r} to equal {expected!r} (infinity comparison)",
                expected=expected,
                actual=actual,
                show_diff=False,
            )
            return

        diff = abs(actual - expected)
        self._check(
            diff <= delta,
            f"Expected {actual!r} to be within {delta} of {expected!r} (diff: {diff})",
            expected=expected,
            actual=actual,
            show_diff=False,
        )

    def to_be_greater_than(self, n: Any) -> None:
        """Assert value > n."""
        self._check(
            self.value > n,
            f"Expected {self.value!r} to be greater than {n!r}",
            show_diff=False,
        )

    def to_be_greater_than_or_equal(self, n: Any) -> None:
        """Assert value >= n."""
        self._check(
            self.value >= n,
            f"Expected {self.value!r} to be greater than or equal to {n!r}",
            show_diff=False,
        )

    def to_be_less_than(self, n: Any) -> None:
        """Assert value < n."""
        self._check(
            self.value < n,
            f"Expected {self.value!r} to be less than {n!r}",
            show_diff=False,
        )

    def to_be_less_than_or_equal(self, n: Any) -> None:
        """Assert value <= n."""
        self._check(
            self.value <= n,
            f"Expected {self.value!r} to be less than or equal to {n!r}",
            show_diff=False,
        )

    def to_be_between(self, low: Any, high: Any, *, inclusive: bool = True) -> None:
        """Assert value is between low and high."""
        if low > high:
            msg = f"Invalid range: low ({low!r}) must be <= high ({high!r})"
            raise ValueError(msg)

        if inclusive:
            in_range = low <= self.value <= high
            desc = "between"
        else:
            in_range = low < self.value < high
            desc = "strictly between"

        self._check(
            in_range,
            f"Expected {self.value!r} to be {desc} {low!r} and {high!r}",
            show_diff=False,
        )

    # ===== Collections =====

    def to_have_length(self, length: int) -> None:
        """Assert collection has specific length."""
        actual_len = len(self.value)
        self._check(
            actual_len == length,
            f"Expected length {length}, got {actual_len}",
            expected=length,
            actual=actual_len,
        )

    def to_be_empty(self) -> None:
        """Assert collection is empty."""
        self._check(
            len(self.value) == 0,
            f"Expected {self.value!r} to be empty (length={len(self.value)})",
            show_diff=False,
        )

    def to_contain(self, item: Any) -> None:
        """Assert collection contains item."""
        self._check(
            item in self.value,
            f"Expected {self.value!r} to contain {item!r}",
            show_diff=False,
        )

    def to_include(self, *items: Any) -> None:
        """Assert collection contains all specified items."""
        missing = [item for item in items if item not in self.value]
        self._check(
            len(missing) == 0,
            f"Expected {self.value!r} to include {items!r}, missing: {missing!r}",
            show_diff=False,
        )

    def to_have_property(self, key: str, value: Any = MISSING) -> None:
        """Assert object has property, optionally with specific value."""
        # Check for attribute or dict key
        if hasattr(self.value, key):
            actual = getattr(self.value, key)
            has_prop = True
        elif isinstance(self.value, dict) and key in self.value:
            actual = self.value[key]
            has_prop = True
        else:
            has_prop = False
            actual = MISSING

        self._check(
            has_prop,
            f"Expected {self.value!r} to have property {key!r}",
            show_diff=False,
        )

        if value is not MISSING and has_prop:
            self._check(
                actual == value,
                f"Expected property {key!r} to be {value!r}, got {actual!r}",
                expected=value,
                actual=actual,
            )

    def to_match_object(self, subset: dict[str, Any]) -> None:
        """Assert dict/object contains all key-value pairs from subset."""
        for key, expected_val in subset.items():
            if isinstance(self.value, dict):
                has_key = key in self.value
                actual_val = self.value.get(key, MISSING)
            else:
                has_key = hasattr(self.value, key)
                actual_val = getattr(self.value, key, MISSING)

            self._check(
                has_key,
                f"Expected {self.value!r} to have key {key!r}",
                show_diff=False,
            )

            if has_key:
                self._check(
                    actual_val == expected_val,
                    f"Expected [{key!r}] to be {expected_val!r}, got {actual_val!r}",
                    expected=expected_val,
                    actual=actual_val,
                )

    # ===== Strings =====

    def to_match(self, pattern: str | re.Pattern[str]) -> None:
        """Assert string matches regex pattern."""
        if isinstance(pattern, str):
            pattern = _compile_pattern(pattern)

        self._check(
            pattern.search(str(self.value)) is not None,
            f"Expected {self.value!r} to match pattern {pattern.pattern!r}",
            show_diff=False,
        )

    def to_start_with(self, prefix: str) -> None:
        """Assert string starts with prefix."""
        s = str(self.value)
        self._check(
            s.startswith(prefix),
            f"Expected {self.value!r} to start with {prefix!r}",
            show_diff=False,
        )

    def to_end_with(self, suffix: str) -> None:
        """Assert string ends with suffix."""
        s = str(self.value)
        self._check(
            s.endswith(suffix),
            f"Expected {self.value!r} to end with {suffix!r}",
            show_diff=False,
        )

    def to_contain_string(self, substring: str) -> None:
        """Assert string contains substring."""
        s = str(self.value)
        self._check(
            substring in s,
            f"Expected {self.value!r} to contain {substring!r}",
            show_diff=False,
        )

    # ===== Exceptions =====

    def _check_exception(
        self, raised: bool, raised_type: type | None, exception_type: type[Exception]
    ) -> None:
        """Common exception checking logic."""
        if raised_type is not None and not raised:
            self._check(
                False,
                f"Expected {exception_type.__name__} to be raised, "
                f"got {raised_type.__name__}",
                show_diff=False,
            )
        else:
            self._check(
                raised,
                f"Expected {exception_type.__name__} to be raised, "
                "but nothing was raised",
                show_diff=False,
            )

    async def to_raise(self, exception_type: type[Exception] = Exception) -> None:
        """Assert that calling the value raises an exception."""
        raised = False
        raised_type = None

        try:
            result = self.value()
            if inspect.isawaitable(result):
                await result
        except exception_type:
            raised = True
        except Exception as e:
            raised_type = type(e)

        self._check_exception(raised, raised_type, exception_type)

    def to_raise_sync(self, exception_type: type[Exception] = Exception) -> None:
        """Assert that calling the value raises an exception (sync-only version)."""
        raised = False
        raised_type = None

        try:
            self.value()
        except exception_type:
            raised = True
        except Exception as e:
            raised_type = type(e)

        self._check_exception(raised, raised_type, exception_type)


def expect(value: T) -> Expectation:
    """Create an expectation for the given value."""
    return Expectation(value)
