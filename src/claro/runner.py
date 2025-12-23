"""Async test execution engine with suite-level thread parallelism."""

import asyncio
import inspect
import io
import json
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import asynccontextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
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


# Pre-computed icon strings
_ICON_SKIP = f"{c.YELLOW}○{c.RESET}"
_ICON_TODO = f"{c.MAGENTA}◌{c.RESET}"
_ICON_PASS = f"{c.GREEN}✓{c.RESET}"
_ICON_FAIL = f"{c.RED}✗{c.RESET}"
_STATUS_SKIP = f"{c.DIM}[skipped]{c.RESET}"
_STATUS_TODO = f"{c.DIM}[todo]{c.RESET}"


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


def _append_result(results_file: Path, result: TestResult) -> None:
    """Append a test result to the JSONL file (thread-safe via atomic append)."""
    line = json.dumps(
        {
            "suite": result.suite_name,
            "test": result.test_name,
            "status": result.status.value,
            "duration_ms": result.duration_ms,
            "error": result.error,
            "expected": repr(result.expected)
            if result.expected is not MISSING
            else None,
            "actual": repr(result.actual) if result.actual is not MISSING else None,
            "show_diff": result.show_diff,
        }
    )
    with open(results_file, "a") as f:
        f.write(line + "\n")


def _print_result(result: TestResult) -> None:
    """Print a single test result line."""
    duration = format_duration(result.duration_ms)

    if result.status == TestStatus.PASSED:
        icon = _ICON_PASS
        name = result.test_name
        status = f"{c.DIM}({duration}){c.RESET}"
    elif result.status == TestStatus.FAILED:
        icon = _ICON_FAIL
        name = f"{c.RED}{result.test_name}{c.RESET}"
        status = f"{c.DIM}({duration}){c.RESET}"
    elif result.status == TestStatus.SKIPPED:
        icon = _ICON_SKIP
        name = f"{c.DIM}{result.test_name}{c.RESET}"
        status = _STATUS_SKIP
    else:  # TODO
        icon = _ICON_TODO
        name = f"{c.DIM}{result.test_name}{c.RESET}"
        status = _STATUS_TODO

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
    results_file: Path | None = None,
) -> TestResult:
    """Run a single test and return its result."""
    # Cache event loop reference
    loop = asyncio.get_running_loop()
    start_time = loop.time()

    # Handle skipped tests
    if t.skip:
        result = TestResult(
            suite_name=suite.name,
            test_name=t.name,
            status=TestStatus.SKIPPED,
            duration_ms=0,
            error=t.skip_reason,
        )
        if results_file:
            _append_result(results_file, result)
        return result

    # Handle todo tests
    if t.todo:
        result = TestResult(
            suite_name=suite.name,
            test_name=t.name,
            status=TestStatus.TODO,
            duration_ms=0,
        )
        if results_file:
            _append_result(results_file, result)
        return result

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
        result = TestResult(
            suite_name=suite.name,
            test_name=t.name,
            status=TestStatus.PASSED,
            duration_ms=duration,
        )

    except TestTimeoutError as e:
        duration = (loop.time() - start_time) * 1000
        result = TestResult(
            suite_name=suite.name,
            test_name=t.name,
            status=TestStatus.FAILED,
            duration_ms=duration,
            error=str(e),
            show_diff=False,
        )

    except ExpectationError as e:
        duration = (loop.time() - start_time) * 1000
        result = TestResult(
            suite_name=suite.name,
            test_name=t.name,
            status=TestStatus.FAILED,
            duration_ms=duration,
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
            result = TestResult(
                suite_name=suite.name,
                test_name=t.name,
                status=TestStatus.FAILED,
                duration_ms=duration,
                error=msg,
                expected=expected,
                actual=actual,
                show_diff=True,
            )
        else:
            result = TestResult(
                suite_name=suite.name,
                test_name=t.name,
                status=TestStatus.FAILED,
                duration_ms=duration,
                error=str(e) or "Assertion failed",
                show_diff=False,
            )

    except Exception as e:
        import traceback

        duration = (loop.time() - start_time) * 1000
        tb_lines = traceback.format_exception(type(e), e, e.__traceback__)
        error_msg = "".join(tb_lines[-3:]).strip()

        result = TestResult(
            suite_name=suite.name,
            test_name=t.name,
            status=TestStatus.FAILED,
            duration_ms=duration,
            error=error_msg,
            show_diff=False,
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
                    result = TestResult(
                        suite_name=suite.name,
                        test_name=t.name,
                        status=TestStatus.FAILED,
                        duration_ms=duration,
                        error=error_msg,
                        show_diff=False,
                    )

    # result should always be set by now
    assert result is not None

    if results_file:
        _append_result(results_file, result)

    return result


async def run_suite(
    suite: Suite,
    shared_context: dict[str, Any],
    global_timeout: float | None = None,
    only_mode: bool = False,
    results_file: Path | None = None,
) -> list[TestResult]:
    """Run all tests in a suite and its children."""
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
                            run_single_test(
                                suite, t, shared_context, global_timeout, results_file
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
                                TestResult(
                                    suite_name=suite.name,
                                    test_name=t.name,
                                    status=TestStatus.FAILED,
                                    error=str(e),
                                    show_diff=False,
                                )
                            )
        else:
            # Run tests sequentially
            for t in tests_to_run:
                result = await run_single_test(
                    suite, t, shared_context, global_timeout, results_file
                )
                results.append(result)

        # Run child suites
        for child in suite.children:
            child_results = await run_suite(
                child, shared_context, global_timeout, only_mode, results_file
            )
            results.extend(child_results)

    finally:
        # Run after_all
        if suite.after_all:
            await maybe_await(suite.after_all, shared_context)

    return results


def collect_all_tests(
    suites: list[Suite], only_mode: bool
) -> Iterator[tuple[Suite, list[Test]]]:
    """Collect all suites and their tests to run (generator to avoid intermediate lists)."""
    for suite in suites:
        tests = suite.tests
        if only_mode:
            only_tests = [t for t in tests if t.only]
            if only_tests:
                tests = only_tests
            else:
                tests = []

        if tests:
            yield (suite, tests)

        # Recurse into children
        yield from collect_all_tests(suite.children, only_mode)


# ============== Thread Workers ==============


def _suite_worker(
    suite: Suite,
    shared_context: dict[str, Any],
    timeout: float | None,
    only_mode: bool,
    results_file: Path,
    done_event: threading.Event,
) -> None:
    """Run a single suite in its own thread with a dedicated event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Note: We don't redirect stdout/stderr here because redirect_* affects
    # ALL threads globally, not just this one. Nested test output is handled
    # by _run_silent() which spawns its own isolated thread.

    try:
        loop.run_until_complete(
            run_suite(suite, shared_context, timeout, only_mode, results_file)
        )
    except Exception as e:
        # Don't let thread crash silently - report as suite failure
        import traceback

        tb_lines = traceback.format_exception(type(e), e, e.__traceback__)
        error_msg = f"Suite crashed: {''.join(tb_lines[-3:]).strip()}"
        _append_result(
            results_file,
            TestResult(
                suite_name=suite.name,
                test_name="<suite>",
                status=TestStatus.FAILED,
                error=error_msg,
                show_diff=False,
            ),
        )
    finally:
        loop.close()
        done_event.set()


def _has_only_tests(s: Suite) -> bool:
    """Check if a suite or its children have any .only tests."""
    if any(t.only for t in s.tests):
        return True
    return any(_has_only_tests(child) for child in s.children)


# ============== Public API ==============

# Global flag to detect nested runs (when tests call main())
_running_lock = threading.Lock()
_running = False


def run(suites: list[Suite], timeout: float | None = None) -> bool:
    """
    Run all test suites with suite-level thread parallelism.

    Each top-level suite runs in its own thread with a dedicated asyncio event loop.
    Tests within a suite run concurrently via TaskGroup.
    A dedicated output thread handles all terminal updates.
    """
    global _running

    # Check if this is a nested run (e.g., a test calling main())
    with _running_lock:
        nested = _running
        if not nested:
            _running = True

    try:
        if nested:
            # Nested run - suppress all output, just return results
            return _run_silent(suites, timeout)
        else:
            return _run_with_output(suites, timeout)
    finally:
        if not nested:
            with _running_lock:
                _running = False


def _run_silent(suites: list[Suite], timeout: float | None = None) -> bool:
    """Run tests without any output (for nested runs).

    Spawns a separate thread because asyncio event loops cannot be nested
    within the same thread. Each thread gets its own event loop.
    """
    if not suites:
        return True

    only_mode = any(_has_only_tests(s) for s in suites)
    nested_suite_ids = {id(child) for s in suites for child in s.children}
    top_level_suites = [s for s in suites if id(s) not in nested_suite_ids]

    # Use lists to capture results from the worker thread
    results: list[TestResult] = []
    error_holder: list[Exception] = []

    def worker() -> None:
        """Run all suites in a separate thread with its own event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Capture all output to prevent pollution
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                for suite in top_level_suites:
                    suite_results = loop.run_until_complete(
                        run_suite(suite, {}, timeout, only_mode, None)
                    )
                    results.extend(suite_results)
        except Exception as e:
            error_holder.append(e)
        finally:
            loop.close()

    # Run in separate thread to avoid "event loop already running" error
    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    # Check for errors from the worker thread
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


def _read_results(results_file: Path) -> list[TestResult]:
    """Read all results from the JSONL file."""
    results = []
    if not results_file.exists():
        return results

    with open(results_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            results.append(
                TestResult(
                    suite_name=data["suite"],
                    test_name=data["test"],
                    status=TestStatus(data["status"]),
                    duration_ms=data["duration_ms"],
                    error=data["error"],
                    expected=data["expected"] if data["expected"] else MISSING,
                    actual=data["actual"] if data["actual"] else MISSING,
                    show_diff=data["show_diff"],
                )
            )
    return results


def _run_with_output(suites: list[Suite], timeout: float | None = None) -> bool:
    """Run tests with normal output display using file-based result streaming."""
    if not suites:
        print(format_summary([], 0))
        return True

    # Determine if we're in "only" mode
    only_mode = any(_has_only_tests(s) for s in suites)

    if only_mode:
        print(f"{c.YELLOW}Running only focused tests (.only){c.RESET}\n")

    # Find top-level suites (exclude those that are children of other suites)
    nested_suite_ids = {id(child) for s in suites for child in s.children}
    top_level_suites = [s for s in suites if id(s) not in nested_suite_ids]

    # Create temp file for results
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        results_file = Path(f.name)

    start_time = time.perf_counter()

    # Track completion with events
    done_events = []

    # Start suite threads (1 per top-level suite)
    suite_threads = []
    for suite in top_level_suites:
        done_event = threading.Event()
        done_events.append(done_event)
        t = threading.Thread(
            target=_suite_worker,
            args=(suite, {}, timeout, only_mode, results_file, done_event),
        )
        suite_threads.append(t)
        t.start()

    # Poll file and print new results until all threads are done
    printed_suites: set[str] = set()
    printed_count = 0

    while not all(e.is_set() for e in done_events):
        # Read new results
        results = _read_results(results_file)

        # Print any new results
        for result in results[printed_count:]:
            if result.suite_name not in printed_suites:
                printed_suites.add(result.suite_name)
                print(f"{c.BOLD}{result.suite_name}{c.RESET}")
            _print_result(result)
            printed_count += 1

        time.sleep(0.05)  # 50ms poll interval

    # Wait for all threads to fully complete
    for t in suite_threads:
        t.join()

    # Final read to catch any remaining results
    results = _read_results(results_file)
    for result in results[printed_count:]:
        if result.suite_name not in printed_suites:
            printed_suites.add(result.suite_name)
            print(f"{c.BOLD}{result.suite_name}{c.RESET}")
        _print_result(result)

    # Print failures and summary
    total_time = (time.perf_counter() - start_time) * 1000

    _print_failures(results)
    print(format_summary(results, total_time))

    # Cleanup temp file
    try:
        results_file.unlink()
    except OSError:
        pass

    return not any(r.status == TestStatus.FAILED for r in results)
