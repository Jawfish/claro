"""Claro - async-first Python test framework."""

from .assertions import Expectation, expect
from .decorators import (
    after_all,
    after_each,
    before_all,
    before_each,
    clear_suites,
    get_suites,
    suite,
    test,
)
from .types import (
    MISSING,
    ExpectationError,
    Suite,
    Test,
    TestResult,
    TestStatus,
    TestTimeoutError,
)

__version__ = "0.1.0"

__all__ = [
    # Decorators
    "suite",
    "test",
    "before_each",
    "after_each",
    "before_all",
    "after_all",
    # Registry
    "get_suites",
    "clear_suites",
    # Assertions
    "expect",
    "Expectation",
    # Types
    "Suite",
    "Test",
    "TestResult",
    "TestStatus",
    # Exceptions
    "ExpectationError",
    "TestTimeoutError",
    # Sentinels
    "MISSING",
]
