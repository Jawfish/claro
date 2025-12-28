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
from .fixtures import Inject, clear_fixtures, fixture, get_fixtures
from .narrowing import narrow, require
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
    # Fixtures
    "fixture",
    "Inject",
    "get_fixtures",
    "clear_fixtures",
    # Registry
    "get_suites",
    "clear_suites",
    # Assertions
    "expect",
    "Expectation",
    # Narrowing
    "require",
    "narrow",
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
