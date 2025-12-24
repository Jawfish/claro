"""Async test execution engine."""

import asyncio
import inspect
import io
import threading
import time
from contextlib import asynccontextmanager, redirect_stderr, redirect_stdout
from typing import Any

from .output import c, format_duration, format_summary
from .types import (
    MISSING,
    ExpectationError,
    RunMode,
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
    TestStatus.TODO: ("◌", "dim", "[todo]"),
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
        TestStatus.TODO: c.MAGENTA,
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
) -> TestResult:
    """Run a single test and return its result."""
    loop = asyncio.get_running_loop()
    start_time = loop.time()

    # Handle skipped tests
    if t.skip:
        return _make_result(suite, t, TestStatus.SKIPPED, 0, error=t.skip_reason)

    # Handle todo tests
    if t.todo:
        return _make_result(suite, t, TestStatus.TODO, 0)

    # Create fresh instance for this test
    instance = suite.cls()
    instance._shared = shared_context  # type: ignore[attr-defined]

    # Determine timeout: test > suite > global
    timeout = t.timeout or suite.timeout or global_timeout
    result: TestResult | None = None

    try:
        # Run before_each + test inside timeout (both should be protected)
        async with timeout_context(timeout):
            if suite.before_each:
                await maybe_await(suite.before_each, instance)

            if t.params is not None:
                if isinstance(t.params, dict):
                    await maybe_await(t.fn, instance, **t.params)
                elif isinstance(t.params, (tuple, list)):
                    await maybe_await(t.fn, instance, *t.params)
                else:
                    await maybe_await(t.fn, instance, t.params)
            else:
                await maybe_await(t.fn, instance)

        duration = (loop.time() - start_time) * 1000
        result = _make_result(suite, t, TestStatus.PASSED, duration)

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
    only_mode: bool = False,
) -> list[TestResult]:
    """Run all tests in a suite."""
    results: list[TestResult] = []

    # Determine which tests to run
    tests_to_run = suite.tests

    if only_mode:
        only_tests = [t for t in suite.tests if t.only]
        if only_tests:
            tests_to_run = only_tests
        else:
            tests_to_run = []

    # Run before_all
    if suite.before_all:
        await maybe_await(suite.before_all, shared_context)

    try:
        if suite.mode == RunMode.PARALLEL and len(tests_to_run) > 1:
            # Run tests in parallel using TaskGroup for structured concurrency
            tasks: dict[asyncio.Task[TestResult], Test] = {}
            try:
                async with asyncio.TaskGroup() as tg:
                    for t in tests_to_run:
                        task = tg.create_task(
                            run_single_test(suite, t, shared_context, global_timeout)
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
            # Run tests sequentially
            for t in tests_to_run:
                result = await run_single_test(suite, t, shared_context, global_timeout)
                results.append(result)

    finally:
        # Run after_all
        if suite.after_all:
            await maybe_await(suite.after_all, shared_context)

    return results


def _has_only_tests(s: Suite) -> bool:
    """Check if a suite has any .only tests."""
    return any(t.only for t in s.tests)


def _is_inside_event_loop() -> bool:
    """Check if we're already inside an asyncio event loop."""
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


# ============== Public API ==============


def run(suites: list[Suite], timeout: float | None = None) -> bool:
    """
    Run all test suites.

    Suites run sequentially, but tests within each suite run concurrently
    via asyncio TaskGroup for maximum parallelism.
    """
    if _is_inside_event_loop():
        # Nested run (e.g., a test calling main()) - suppress output
        return _run_silent(suites, timeout)
    return _run_with_output(suites, timeout)


def _run_silent(suites: list[Suite], timeout: float | None = None) -> bool:
    """Run tests without any output (for nested runs).

    Uses a separate thread because we may already be inside an event loop.
    """
    if not suites:
        return True

    only_mode = any(_has_only_tests(s) for s in suites)

    results: list[TestResult] = []
    error_holder: list[Exception] = []

    def worker() -> None:
        """Run all suites in a separate thread with its own event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                for suite in suites:
                    suite_results = loop.run_until_complete(
                        run_suite(suite, {}, timeout, only_mode)
                    )
                    results.extend(suite_results)
        except Exception as e:
            error_holder.append(e)
        finally:
            loop.close()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join()

    if error_holder:
        import traceback

        e = error_holder[0]
        tb_lines = traceback.format_exception(type(e), e, e.__traceback__)
        error_msg = f"Nested run crashed: {''.join(tb_lines[-3:]).strip()}"
        results.append(
            TestResult(
                suite_name="<nested>",
                test_name="<run>",
                status=TestStatus.FAILED,
                error=error_msg,
                show_diff=False,
            )
        )

    return not any(r.status == TestStatus.FAILED for r in results)


def _run_with_output(suites: list[Suite], timeout: float | None = None) -> bool:
    """Run tests with output display using pure async."""
    if not suites:
        print(format_summary([], 0))
        return True

    only_mode = any(_has_only_tests(s) for s in suites)

    if only_mode:
        print(f"{c.YELLOW}Running only focused tests (.only){c.RESET}\n")

    async def run_all() -> list[TestResult]:
        """Run all suites and print results as they complete."""
        all_results: list[TestResult] = []

        for suite in suites:
            # Print suite header
            print(f"{c.BOLD}{suite.name}{c.RESET}")

            # Run suite tests
            results = await run_suite(suite, {}, timeout, only_mode)

            # Print results immediately
            for result in results:
                _print_result(result)

            all_results.extend(results)

        return all_results

    start_time = time.perf_counter()
    results = asyncio.run(run_all())
    total_time = (time.perf_counter() - start_time) * 1000

    _print_failures(results)
    print(format_summary(results, total_time))

    return not any(r.status == TestStatus.FAILED for r in results)
