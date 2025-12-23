"""Terminal output formatting and colors."""

import os
import sys
from typing import Any

from .types import MISSING, TestResult, TestStatus


class Colors:
    """ANSI color codes with automatic TTY detection."""

    _enabled: bool | None = None

    @classmethod
    def _is_enabled(cls) -> bool:
        if cls._enabled is not None:
            return cls._enabled

        # Check for NO_COLOR environment variable (https://no-color.org/)
        if os.environ.get("NO_COLOR") is not None:
            return False

        # Check for FORCE_COLOR
        if os.environ.get("FORCE_COLOR") is not None:
            return True

        # Check if stdout is a TTY
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    @classmethod
    def disable(cls) -> None:
        cls._enabled = False

    @classmethod
    def enable(cls) -> None:
        cls._enabled = True

    @classmethod
    def reset_detection(cls) -> None:
        cls._enabled = None

    @classmethod
    def code(cls, code: str) -> str:
        return code if cls._is_enabled() else ""

    # Basic formatting
    @property
    def RESET(self) -> str:
        return Colors.code("\033[0m")

    @property
    def BOLD(self) -> str:
        return Colors.code("\033[1m")

    @property
    def DIM(self) -> str:
        return Colors.code("\033[2m")

    # Colors
    @property
    def RED(self) -> str:
        return Colors.code("\033[31m")

    @property
    def GREEN(self) -> str:
        return Colors.code("\033[32m")

    @property
    def YELLOW(self) -> str:
        return Colors.code("\033[33m")

    @property
    def MAGENTA(self) -> str:
        return Colors.code("\033[35m")

    @property
    def CYAN(self) -> str:
        return Colors.code("\033[36m")

    @property
    def GRAY(self) -> str:
        return Colors.code("\033[90m")


# Singleton instance
c = Colors()


def format_duration(ms: float) -> str:
    """Format duration in human-readable form."""
    if ms < 1:
        return f"{ms * 1000:.0f}us"
    elif ms < 1000:
        return f"{ms:.1f}ms"
    else:
        return f"{ms / 1000:.2f}s"


def format_diff(expected: Any, actual: Any, indent: str = "      ") -> list[str]:
    """Generate diff lines between expected and actual values."""
    lines: list[str] = []
    exp_str = repr(expected)
    act_str = repr(actual)

    # For strings, show line-by-line diff
    if (
        isinstance(expected, str)
        and isinstance(actual, str)
        and ("\n" in expected or "\n" in actual)
    ):
        import difflib

        exp_lines = expected.splitlines(keepends=True)
        act_lines = actual.splitlines(keepends=True)

        diff = difflib.unified_diff(
            exp_lines, act_lines, fromfile="expected", tofile="actual", lineterm=""
        )

        lines.append(f"{indent}{c.DIM}Diff:{c.RESET}")
        for line in diff:
            if line.startswith("+") and not line.startswith("+++"):
                lines.append(f"{indent}  {c.GREEN}{line.rstrip()}{c.RESET}")
            elif line.startswith("-") and not line.startswith("---"):
                lines.append(f"{indent}  {c.RED}{line.rstrip()}{c.RESET}")
            elif line.startswith("@"):
                lines.append(f"{indent}  {c.CYAN}{line.rstrip()}{c.RESET}")
            else:
                lines.append(f"{indent}  {c.DIM}{line.rstrip()}{c.RESET}")
    else:
        # Simple expected/actual display
        lines.append(f"{indent}{c.RED}- Expected: {exp_str}{c.RESET}")
        lines.append(f"{indent}{c.GREEN}+ Actual:   {act_str}{c.RESET}")

    return lines


def format_result(result: TestResult, indent: str = "") -> list[str]:
    """Format a single test result."""
    lines: list[str] = []
    duration = format_duration(result.duration_ms)

    if result.status == TestStatus.PASSED:
        icon = f"{c.GREEN}✓{c.RESET}"
        name_color = ""
        duration_str = f"{c.DIM}({duration}){c.RESET}"
    elif result.status == TestStatus.FAILED:
        icon = f"{c.RED}✗{c.RESET}"
        name_color = c.RED
        duration_str = f"{c.DIM}({duration}){c.RESET}"
    elif result.status == TestStatus.SKIPPED:
        icon = f"{c.YELLOW}○{c.RESET}"
        name_color = c.DIM
        duration_str = f"{c.DIM}[skipped]{c.RESET}"
    elif result.status == TestStatus.TODO:
        icon = f"{c.MAGENTA}◌{c.RESET}"
        name_color = c.DIM
        duration_str = f"{c.DIM}[todo]{c.RESET}"
    else:
        icon = "?"
        name_color = ""
        duration_str = ""

    lines.append(
        f"{indent}  {icon} {name_color}{result.test_name}{c.RESET} {duration_str}"
    )

    # Print error details for failed tests
    if result.status == TestStatus.FAILED and result.error:
        error_indent = indent + "    "
        lines.append(f"{error_indent}{c.RED}{result.error}{c.RESET}")

        # Print diff if we have expected/actual values
        if (
            result.show_diff
            and result.expected is not MISSING
            and result.actual is not MISSING
        ):
            lines.extend(format_diff(result.expected, result.actual, error_indent))

    return lines


def format_summary(results: list[TestResult], total_time_ms: float) -> str:
    """Format final test summary."""
    passed = sum(1 for r in results if r.status == TestStatus.PASSED)
    failed = sum(1 for r in results if r.status == TestStatus.FAILED)
    skipped = sum(1 for r in results if r.status == TestStatus.SKIPPED)
    todo = sum(1 for r in results if r.status == TestStatus.TODO)

    parts = []

    if passed > 0:
        parts.append(f"{c.GREEN}{passed} passed{c.RESET}")
    if failed > 0:
        parts.append(f"{c.RED}{failed} failed{c.RESET}")
    if skipped > 0:
        parts.append(f"{c.YELLOW}{skipped} skipped{c.RESET}")
    if todo > 0:
        parts.append(f"{c.MAGENTA}{todo} todo{c.RESET}")

    summary = ", ".join(parts) if parts else "No tests"
    duration = format_duration(total_time_ms)

    return f"\n{summary} {c.DIM}({duration}){c.RESET}"
