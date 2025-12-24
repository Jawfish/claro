"""Command-line interface for claro."""

import argparse
import sys
from pathlib import Path

from . import runner
from .discovery import DEFAULT_PATTERNS, collect_tests
from .output import Colors, c


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="claro",
        description="Claro - async-first Python test framework",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to search for test files (default: current directory)",
    )
    parser.add_argument(
        "-p",
        "--pattern",
        action="append",
        dest="patterns",
        metavar="PATTERN",
        help="File patterns to match (can be specified multiple times)",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Global timeout in seconds for each test",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    parser.add_argument(
        "--color",
        action="store_true",
        help="Force colored output",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """
    Main entry point for the claro CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Configure colors
    if args.no_color:
        Colors.disable()
    elif args.color:
        Colors.enable()

    # Determine patterns
    patterns = tuple(args.patterns) if args.patterns else DEFAULT_PATTERNS

    # Resolve path
    path = Path(args.path).resolve()
    if not path.exists():
        print(f"{c.RED}Error: Path does not exist: {path}{c.RESET}", file=sys.stderr)
        return 1

    if not path.is_dir():
        print(
            f"{c.RED}Error: Path is not a directory: {path}{c.RESET}",
            file=sys.stderr,
        )
        return 1

    # Collect tests
    try:
        suites = collect_tests(path, patterns)
    except Exception as e:
        print(f"{c.RED}Error collecting tests: {e}{c.RESET}", file=sys.stderr)
        return 1

    if not suites:
        print(f"{c.YELLOW}No test suites found in {path}{c.RESET}")
        return 0

    # Run tests
    success = runner.run(suites, timeout=args.timeout)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
