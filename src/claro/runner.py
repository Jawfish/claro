"""Async test execution engine."""

import asyncio
import inspect
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from .fixtures import FixtureDef, FixtureError, get_fixtures, get_injectable_params
from .output import c, format_duration, format_summary
from .types import (
    MISSING,
    ExpectationError,
    Suite,
    Test,
    TestResult,
    TestStatus,
    TestTimeoutError,
)


# Status display configuration: (icon, name_color, status_suffix_fn)
# status_suffix_fn takes duration string and returns the suffix
_STATUS_CONFIG: dict[TestStatus, tuple[str, str, str]] = {
    TestStatus.PASSED: ("✓", "", "duration"),
    TestStatus.FAILED: ("✗", "name_red", "duration"),
    TestStatus.SKIPPED: ("○", "dim", "[skipped]"),
}


async def maybe_await(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Call a function and await it if it returns an awaitable."""
    result = fn(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


@asynccontextmanager
async def timeout_context(seconds: float | None):
    """Async context manager for timeouts."""
    if seconds is None:
        yield
        return

    try:
        async with asyncio.timeout(seconds):
            yield
    except asyncio.TimeoutError:
        raise TestTimeoutError(seconds) from None


# ============== Fixture Resolution ==============


async def _resolve_fixture(
    fixture_def: FixtureDef,
    test_cache: dict[type, Any],
    suite_cache: dict[type, Any],
    session_cache: dict[type, Any],
    test_cleanups: list[Callable[[], Any]],
    suite_cleanups: list[Callable[[], Any]],
    session_cleanups: list[Callable[[], Any]],
) -> Any:
    """
    Resolve a fixture value, using cache based on scope.

    Adds cleanup functions to the appropriate cleanup list based on scope.

    Returns:
        The resolved fixture value.
    """
    cache = {
        "test": test_cache,
        "suite": suite_cache,
        "session": session_cache,
    }[fixture_def.scope]

    cleanup_list = {
        "test": test_cleanups,
        "suite": suite_cleanups,
        "session": session_cleanups,
    }[fixture_def.scope]

    # Return cached value if available (cleanup already registered)
    if fixture_def.return_type in cache:
        return cache[fixture_def.return_type]

    # Create new instance
    cleanup: Callable[[], Any] | None = None

    if fixture_def.is_generator:
        gen = fixture_def.fn()
        if inspect.isasyncgen(gen):
            value = await gen.__anext__()

            async def async_cleanup() -> None:
                try:
                    await gen.__anext__()
                except StopAsyncIteration:
                    pass

            cleanup = async_cleanup
        else:
            value = next(gen)

            def sync_cleanup() -> None:
                try:
                    next(gen)
                except StopIteration:
                    pass

            cleanup = sync_cleanup
    else:
        result = fixture_def.fn()
        if inspect.isawaitable(result):
            value = await result
        else:
            value = result

    cache[fixture_def.return_type] = value
    if cleanup is not None:
        cleanup_list.append(cleanup)

    return value


async def _resolve_all_fixtures(
    fn: Callable[..., Any],
    test_cache: dict[type, Any],
    suite_cache: dict[type, Any],
    session_cache: dict[type, Any],
    test_cleanups: list[Callable[[], Any]],
    suite_cleanups: list[Callable[[], Any]],
    session_cleanups: list[Callable[[], Any]],
) -> dict[str, Any]:
    """
    Resolve all fixtures for a test function.

    Adds cleanup functions to the appropriate cleanup lists based on scope.

    Returns:
        Dict of resolved fixture kwargs.
    """
    injectable_params = get_injectable_params(fn)
    if not injectable_params:
        return {}

    fixtures = get_fixtures()
    resolved: dict[str, Any] = {}

    for param_name, expected_type in injectable_params.items():
        fixture_def = fixtures.get(expected_type)
        if fixture_def is None:
            msg = f"No fixture registered for type {expected_type.__name__}"
            raise FixtureError(msg)

        value = await _resolve_fixture(
            fixture_def,
            test_cache,
            suite_cache,
            session_cache,
            test_cleanups,
            suite_cleanups,
            session_cleanups,
        )
        resolved[param_name] = value

    return resolved


async def _run_cleanups(cleanups: list[Callable[[], Any]]) -> None:
    """Run all cleanup functions, ignoring errors."""
    for cleanup in reversed(cleanups):
        try:
            result = cleanup()
            if inspect.isawaitable(result):
                await result
        except Exception:
            pass  # Cleanup errors are silently ignored


def _make_result(
    suite: Suite,
    test: Test,
    status: TestStatus,
    duration_ms: float,
    *,
    error: str | None = None,
    expected: Any = MISSING,
    actual: Any = MISSING,
    show_diff: bool = True,
) -> TestResult:
    """Create a TestResult with common fields pre-filled."""
    return TestResult(
        suite_name=suite.name,
        test_name=test.name,
        status=status,
        duration_ms=duration_ms,
        error=error,
        expected=expected,
        actual=actual,
        show_diff=show_diff,
    )


def _print_result(result: TestResult) -> None:
    """Print a single test result line."""
    duration = format_duration(result.duration_ms)
    icon_char, name_style, suffix_type = _STATUS_CONFIG[result.status]

    # Apply color to icon based on status
    icon_colors = {
        TestStatus.PASSED: c.GREEN,
        TestStatus.FAILED: c.RED,
        TestStatus.SKIPPED: c.YELLOW,
    }
    icon = f"{icon_colors[result.status]}{icon_char}{c.RESET}"

    # Apply name styling
    if name_style == "name_red":
        name = f"{c.RED}{result.test_name}{c.RESET}"
    elif name_style == "dim":
        name = f"{c.DIM}{result.test_name}{c.RESET}"
    else:
        name = result.test_name

    # Build status suffix
    if suffix_type == "duration":
        status = f"{c.DIM}({duration}){c.RESET}"
    else:
        status = f"{c.DIM}{suffix_type}{c.RESET}"

    print(f"  {icon} {name} {status}")


def _print_failures(results: list[TestResult]) -> None:
    """Print detailed failure information."""
    failures = [r for r in results if r.status == TestStatus.FAILED]

    if not failures:
        return

    print(f"\n{c.RED}{c.BOLD}Failures:{c.RESET}\n")

    for result in failures:
        print(f"  {c.RED}✗ {result.suite_name} › {result.test_name}{c.RESET}")
        if result.error:
            print(f"    {result.error}")
        if (
            result.show_diff
            and result.expected is not MISSING
            and result.actual is not MISSING
        ):
            print(f"    {c.RED}- Expected: {result.expected!r}{c.RESET}")
            print(f"    {c.GREEN}+ Actual:   {result.actual!r}{c.RESET}")
        print()


async def run_single_test(
    suite: Suite,
    t: Test,
    shared_context: dict[str, Any],
    global_timeout: float | None = None,
    suite_cache: dict[type, Any] | None = None,
    session_cache: dict[type, Any] | None = None,
    suite_cleanups: list[Callable[[], Any]] | None = None,
    session_cleanups: list[Callable[[], Any]] | None = None,
) -> TestResult:
    """Run a single test and return its result."""
    loop = asyncio.get_running_loop()
    start_time = loop.time()

    # Handle skipped tests
    if t.skip:
        return _make_result(suite, t, TestStatus.SKIPPED, 0, error=t.skip_reason)

    # Create fresh instance for this test
    instance = suite.cls()
    instance._shared = shared_context  # type: ignore[attr-defined]

    # Determine timeout: test > suite > global
    timeout = t.timeout or suite.timeout or global_timeout
    result: TestResult | None = None

    # Caches and cleanups for fixture scopes
    test_cache: dict[type, Any] = {}
    suite_cache = suite_cache if suite_cache is not None else {}
    session_cache = session_cache if session_cache is not None else {}
    test_cleanups: list[Callable[[], Any]] = []
    suite_cleanups = suite_cleanups if suite_cleanups is not None else []
    session_cleanups = session_cleanups if session_cleanups is not None else []

    try:
        # Resolve fixtures before running the test
        fixture_kwargs = await _resolve_all_fixtures(
            t.fn,
            test_cache,
            suite_cache,
            session_cache,
            test_cleanups,
            suite_cleanups,
            session_cleanups,
        )

        # Run before_each + test inside timeout (both should be protected)
        async with timeout_context(timeout):
            if suite.before_each:
                await maybe_await(suite.before_each, instance)

            if t.params is not None:
                if isinstance(t.params, dict):
                    await maybe_await(t.fn, instance, **t.params, **fixture_kwargs)
                elif isinstance(t.params, (tuple, list)):
                    await maybe_await(t.fn, instance, *t.params, **fixture_kwargs)
                else:
                    await maybe_await(t.fn, instance, t.params, **fixture_kwargs)
            else:
                await maybe_await(t.fn, instance, **fixture_kwargs)

        duration = (loop.time() - start_time) * 1000
        result = _make_result(suite, t, TestStatus.PASSED, duration)

    except FixtureError as e:
        duration = (loop.time() - start_time) * 1000
        result = _make_result(
            suite, t, TestStatus.FAILED, duration, error=str(e), show_diff=False
        )

    except TestTimeoutError as e:
        duration = (loop.time() - start_time) * 1000
        result = _make_result(
            suite, t, TestStatus.FAILED, duration, error=str(e), show_diff=False
        )

    except ExpectationError as e:
        duration = (loop.time() - start_time) * 1000
        result = _make_result(
            suite,
            t,
            TestStatus.FAILED,
            duration,
            error=str(e),
            expected=e.expected,
            actual=e.actual,
            show_diff=e.show_diff,
        )

    except AssertionError as e:
        from .enhance import enhance_assertion_error

        duration = (loop.time() - start_time) * 1000
        msg, expected, actual = enhance_assertion_error(e)

        if msg is not None:
            result = _make_result(
                suite,
                t,
                TestStatus.FAILED,
                duration,
                error=msg,
                expected=expected,
                actual=actual,
            )
        else:
            result = _make_result(
                suite,
                t,
                TestStatus.FAILED,
                duration,
                error=str(e) or "Assertion failed",
                show_diff=False,
            )

    except Exception as e:
        import traceback

        duration = (loop.time() - start_time) * 1000
        tb_lines = traceback.format_exception(type(e), e, e.__traceback__)
        error_msg = "".join(tb_lines[-3:]).strip()
        result = _make_result(
            suite, t, TestStatus.FAILED, duration, error=error_msg, show_diff=False
        )

    finally:
        # Run test-scoped fixture cleanups
        await _run_cleanups(test_cleanups)

        # Run after_each (outside timeout, always runs for cleanup)
        if suite.after_each:
            try:
                await maybe_await(suite.after_each, instance)
            except Exception as after_err:
                # Don't let after_each failures mask test failures
                # but if test passed, report after_each failure
                if result and result.status == TestStatus.PASSED:
                    import traceback

                    duration = (loop.time() - start_time) * 1000
                    tb_lines = traceback.format_exception(
                        type(after_err), after_err, after_err.__traceback__
                    )
                    error_msg = f"after_each failed: {''.join(tb_lines[-3:]).strip()}"
                    result = _make_result(
                        suite,
                        t,
                        TestStatus.FAILED,
                        duration,
                        error=error_msg,
                        show_diff=False,
                    )

    assert result is not None
    return result


async def run_suite(
    suite: Suite,
    shared_context: dict[str, Any],
    global_timeout: float | None = None,
    session_cache: dict[type, Any] | None = None,
    session_cleanups: list[Callable[[], Any]] | None = None,
) -> tuple[list[TestResult], list[Callable[[], Any]]]:
    """Run all tests in a suite.

    Returns:
        (results, suite_cleanups) - cleanups should be run after suite completes
    """
    results: list[TestResult] = []
    tests_to_run = suite.tests

    # Suite-scoped fixture cache and cleanups
    suite_cache: dict[type, Any] = {}
    suite_cleanups: list[Callable[[], Any]] = []
    session_cache = session_cache if session_cache is not None else {}
    session_cleanups = session_cleanups if session_cleanups is not None else []

    # Run before_all
    if suite.before_all:
        await maybe_await(suite.before_all, shared_context)

    try:
        if len(tests_to_run) > 1:
            # Run tests in parallel using TaskGroup for structured concurrency
            tasks: dict[asyncio.Task[TestResult], Test] = {}
            try:
                async with asyncio.TaskGroup() as tg:
                    for t in tests_to_run:
                        task = tg.create_task(
                            run_single_test(
                                suite,
                                t,
                                shared_context,
                                global_timeout,
                                suite_cache,
                                session_cache,
                                suite_cleanups,
                                session_cleanups,
                            )
                        )
                        tasks[task] = t
                # All tasks completed successfully
                results = [task.result() for task in tasks]
            except* Exception:
                # Some tasks failed - collect results from completed tasks
                for task, t in tasks.items():
                    if task.done() and not task.cancelled():
                        try:
                            results.append(task.result())
                        except Exception as e:
                            # Task raised an unhandled exception
                            results.append(
                                _make_result(
                                    suite,
                                    t,
                                    TestStatus.FAILED,
                                    0,
                                    error=str(e),
                                    show_diff=False,
                                )
                            )
        else:
            # Single test - run directly
            for t in tests_to_run:
                result = await run_single_test(
                    suite,
                    t,
                    shared_context,
                    global_timeout,
                    suite_cache,
                    session_cache,
                    suite_cleanups,
                    session_cleanups,
                )
                results.append(result)

    finally:
        # Run after_all
        if suite.after_all:
            await maybe_await(suite.after_all, shared_context)

    return results, suite_cleanups


# ============== Public API ==============


def run(suites: list[Suite], timeout: float | None = None) -> bool:
    """
    Run all test suites.

    Suites run sequentially, but tests within each suite run concurrently
    via asyncio TaskGroup for maximum parallelism.
    """
    if not suites:
        print(format_summary([], 0))
        return True

    async def run_all() -> list[TestResult]:
        """Run all suites and print results as they complete."""
        all_results: list[TestResult] = []
        session_cache: dict[type, Any] = {}
        session_cleanups: list[Callable[[], Any]] = []

        try:
            for suite in suites:
                # Print suite header
                print(f"{c.BOLD}{suite.name}{c.RESET}")

                # Run suite tests
                results, suite_cleanups = await run_suite(
                    suite, {}, timeout, session_cache, session_cleanups
                )

                # Run suite-scoped fixture cleanups
                await _run_cleanups(suite_cleanups)

                # Print results immediately
                for result in results:
                    _print_result(result)

                all_results.extend(results)
        finally:
            # Run session-scoped fixture cleanups
            await _run_cleanups(session_cleanups)

        return all_results

    start_time = time.perf_counter()
    results = asyncio.run(run_all())
    total_time = (time.perf_counter() - start_time) * 1000

    _print_failures(results)
    print(format_summary(results, total_time))

    return not any(r.status == TestStatus.FAILED for r in results)
