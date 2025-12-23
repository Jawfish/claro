"""Core type definitions for claro."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from collections.abc import Awaitable


class _Missing:
    """Sentinel for missing values."""

    def __repr__(self) -> str:
        return "<MISSING>"


MISSING = _Missing()


class TestStatus(Enum):
    """Result status of a test."""

    PASSED = auto()
    FAILED = auto()
    SKIPPED = auto()
    TODO = auto()


class RunMode(Enum):
    """Execution mode for a test suite."""

    PARALLEL = auto()
    SEQUENTIAL = auto()


@dataclass(slots=True)
class Test:
    """Represents a single test case."""

    name: str
    fn: Callable[..., Any | Awaitable[Any]]
    skip: bool = False
    only: bool = False
    todo: bool = False
    skip_reason: str | None = None
    timeout: float | None = None
    params: tuple[Any, ...] | dict[str, Any] | None = None
    param_id: str | None = None


@dataclass(slots=True)
class Suite:
    """Represents a test suite (collection of tests)."""

    name: str
    cls: type
    tests: list[Test] = field(default_factory=list)
    children: list["Suite"] = field(default_factory=list)
    before_each: Callable[..., Any] | None = None
    after_each: Callable[..., Any] | None = None
    before_all: Callable[..., Any] | None = None
    after_all: Callable[..., Any] | None = None
    mode: RunMode = RunMode.PARALLEL
    timeout: float | None = None


@dataclass(slots=True)
class TestResult:
    """Result of running a single test."""

    suite_name: str
    test_name: str
    status: TestStatus
    duration_ms: float = 0
    error: str | None = None
    expected: Any = field(default_factory=lambda: MISSING)
    actual: Any = field(default_factory=lambda: MISSING)
    show_diff: bool = True


class ExpectationError(AssertionError):
    """Raised when an expectation fails."""

    def __init__(
        self,
        message: str,
        expected: Any = MISSING,
        actual: Any = MISSING,
        *,
        show_diff: bool = True,
    ):
        super().__init__(message)
        self.expected = expected
        self.actual = actual
        self.show_diff = show_diff


class TestTimeoutError(Exception):
    """Raised when a test exceeds its timeout."""

    def __init__(self, timeout: float):
        self.timeout = timeout
        super().__init__(f"Test timed out after {timeout}s")
