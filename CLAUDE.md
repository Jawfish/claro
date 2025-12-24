# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claro is a modern, async-first Python test framework inspired by Jest/Vitest. It provides a CLI and package API for test-writing with parallel execution by default.

## Commands

```bash
uv run claro                    # Run all tests in current directory
uv run claro src/claro          # Run tests in specific directory
uv run claro -t 5.0             # Run with 5 second timeout per test
uv add <package>                # Add dependency
uv sync                         # Sync dependencies
```

## Module Structure

```
src/claro/
├── __init__.py       # Public API exports
├── types.py          # Data classes, enums (Suite, Test, TestResult, etc.)
├── decorators.py     # @suite, @test, @before_each, etc. + global registry
├── assertions.py     # expect() and Expectation class
├── runner.py         # Async test execution engine
├── discovery.py      # Test file discovery and import
├── output.py         # Colors, formatting, reporting
└── cli.py            # argparse CLI entry point
```

## Test File Convention

Tests are colocated with source files using `*_test.py` suffix:
```
src/claro/assertions.py      → src/claro/assertions_test.py
src/claro/runner.py          → src/claro/runner_test.py
```

Only the `*_test.py` pattern is matched (not `test_*.py`).

## Architecture

### Core Components

The framework follows a decorator-based API pattern:

1. **Suite/Test Registration**: `@suite` class decorator registers test classes, `@test` method decorator marks test methods
2. **Test Modifiers**: `@test.skip`, `@test.skip_if()`, `@test.timeout()`, `@test.each([...])`
3. **Lifecycle Hooks**: `@before_each`, `@after_each`, `@before_all`, `@after_all`
4. **Assertions**: Fluent `expect(value).to_be(expected)` API with chainable `.not_`

### Execution Model

- **Async-first**: All tests run in asyncio event loop, sync tests are automatically awaited
- **Parallel by default**: Tests within a suite run concurrently using `asyncio.TaskGroup`
- **Timeout handling**: Per-test, per-suite, and global timeouts via `asyncio.timeout()`

### Key Data Structures

```
Suite
├── tests: list[Test]           # Test cases in this suite
├── before_each/after_each      # Per-test lifecycle
├── before_all/after_all        # Per-suite lifecycle
└── timeout: float | None       # Suite-level timeout

Test
├── fn: Callable                # The test function
├── skip: bool                  # Skip this test
├── timeout: float | None       # Test-specific timeout
└── params: tuple | dict | None # For parametrized tests
```

### Execution Flow

```
CLI (argparse)
    ↓
discovery.collect_tests(path, patterns)
    ↓ discover files matching patterns
    ↓ import each file (triggers @suite decorator)
    ↓ return get_suites()
    ↓
runner.run(suites, timeout)
    ↓ for each suite: run_suite()
    ↓   parallel execution via TaskGroup
    ↓   lifecycle: before_all → (before_each → test → after_each)* → after_all
    ↓
output.format_summary() → stdout
```

### Helper Patterns

- `maybe_await(fn, *args)`: Calls function and awaits if result is awaitable
- `timeout_context(seconds)`: Async context manager wrapping `asyncio.timeout()`

### Assertion Flow

`expect(value)` returns `Expectation` object → chainable methods like `.to_be()`, `.to_contain()` → raises `ExpectationError` with expected/actual for diff output

### Output

- `Colors` class with TTY detection and NO_COLOR/FORCE_COLOR support
- `format_diff()` for unified diff output on failures
- Status icons: ✓ passed, ✗ failed, ○ skipped

## Design Principles

- Pure functions where possible (assertions, formatting)
- No mocks in tests - use real implementations or fakes
- Structured concurrency with TaskGroup for proper cancellation
- Claro tests itself (dogfooding)
