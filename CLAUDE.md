# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claro is a modern, async-first Python test framework inspired by Jest/Vitest. It provides a CLI and package API for test-writing with parallel execution by default.

## Commands

```bash
uv run python -m claro          # Run tests (once CLI is implemented)
uv run pytest                   # Run claro's own tests (if using pytest for self-testing)
uv add <package>                # Add dependency
uv sync                         # Sync dependencies
```

## Architecture

### Core Components

The framework follows a decorator-based API pattern:

1. **Suite/Test Registration**: `@suite` class decorator registers test classes, `@test` method decorator marks test methods
2. **Test Modifiers**: `@test.skip`, `@test.only`, `@test.todo`, `@test.timeout()`, `@test.each([...])`
3. **Lifecycle Hooks**: `@before_each`, `@after_each`, `@before_all`, `@after_all`
4. **Assertions**: Fluent `expect(value).to_be(expected)` API with chainable `.not_`

### Execution Model

- **Async-first**: All tests run in asyncio event loop, sync tests are automatically awaited
- **Parallel by default**: Tests within a suite run concurrently using `asyncio.TaskGroup`
- **Sequential mode**: `@suite(sequential=True)` for tests that can't run in parallel
- **Timeout handling**: Per-test, per-suite, and global timeouts via `asyncio.timeout()`

### Key Data Structures

```
Suite
├── tests: list[Test]           # Test cases in this suite
├── children: list[Suite]       # Nested suites
├── before_each/after_each      # Per-test lifecycle
├── before_all/after_all        # Per-suite lifecycle
└── mode: RunMode               # PARALLEL or SEQUENTIAL

Test
├── fn: Callable                # The test function
├── skip/only/todo: bool        # Test modifiers
├── timeout: float | None       # Test-specific timeout
└── params: tuple | dict | None # For parametrized tests
```

### Helper Pattern

- `maybe_await(fn, *args)`: Calls function and awaits if result is awaitable
- `timeout_context(seconds)`: Async context manager wrapping `asyncio.timeout()`

### Assertion Flow

`expect(value)` returns `Expectation` object → chainable methods like `.to_be()`, `.to_contain()` → raises `ExpectationError` with expected/actual for diff output

### Output

- `Colors` class with TTY detection and NO_COLOR/FORCE_COLOR support
- `print_diff()` for unified diff output on failures
- Status icons: ✓ passed, ✗ failed, ○ skipped, ◌ todo

## Design Principles

- Pure functions where possible (assertions, formatting)
- No mocks in tests - use real implementations or fakes
- Structured concurrency with TaskGroup for proper cancellation
- Branded types for domain concepts (consider for TestId, SuiteId, etc.)
