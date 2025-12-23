"""Test file discovery and importing."""

import ast
import importlib.util
import sys
from itertools import chain
from pathlib import Path

from .decorators import clear_suites, get_suites
from .types import Suite

DEFAULT_PATTERNS = ("*_test.py",)


class AssertMessageError(SyntaxError):
    """Raised when an assert statement is missing a message."""


class _AssertMessageChecker(ast.NodeVisitor):
    """AST visitor that enforces all assert statements have messages."""

    def __init__(self, filename: str):
        self.filename = filename
        self.errors: list[tuple[int, int]] = []

    def visit_Assert(self, node: ast.Assert) -> None:
        if node.msg is None:
            self.errors.append((node.lineno, node.col_offset))
        self.generic_visit(node)


def check_assert_messages(file_path: Path) -> None:
    """
    Check that all assert statements in a file have messages.

    Raises:
        AssertMessageError: If any assert is missing a message.
    """
    source = file_path.read_text()
    tree = ast.parse(source, filename=str(file_path))

    checker = _AssertMessageChecker(str(file_path))
    checker.visit(tree)

    if checker.errors:
        lineno, col = checker.errors[0]
        msg = (
            f"Assert statement missing message at {file_path}:{lineno}\n"
            f'  Use: assert condition, "natural-language description of what failed"'
        )
        raise AssertMessageError(msg)


def discover_test_files(
    path: Path,
    patterns: tuple[str, ...] = DEFAULT_PATTERNS,
) -> list[Path]:
    """
    Find all test files matching patterns.

    Args:
        path: Directory to search recursively.
        patterns: Glob patterns to match (default: *_test.py).

    Returns:
        Sorted list of matching file paths.
    """
    # Use chain.from_iterable to avoid repeated set.update calls
    files = set(chain.from_iterable(path.rglob(p) for p in patterns))
    return sorted(files)


def import_test_file(file_path: Path, *, check_asserts: bool = True) -> None:
    """
    Import a test file, triggering decorator registration.

    Args:
        file_path: Path to the Python test file.
        check_asserts: If True, verify all asserts have messages.
    """
    # Lint: all assert statements must have messages
    if check_asserts:
        check_assert_messages(file_path)

    # Create a unique module name to avoid collisions
    module_name = f"claro_test_{file_path.stem}_{id(file_path)}"

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        msg = f"Could not load spec for {file_path}"
        raise ImportError(msg)

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception:
        # Clean up on failure
        sys.modules.pop(module_name, None)
        raise


def collect_tests(
    path: Path,
    patterns: tuple[str, ...] = DEFAULT_PATTERNS,
) -> list[Suite]:
    """
    Discover and import all test files, returning collected suites.

    Args:
        path: Directory to search for test files.
        patterns: Glob patterns to match test files.

    Returns:
        List of registered test suites.
    """
    clear_suites()

    files = discover_test_files(path, patterns)
    for file_path in files:
        import_test_file(file_path)

    return get_suites()
