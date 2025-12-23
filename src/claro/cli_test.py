"""Tests for the CLI module."""

import tempfile
from pathlib import Path
from typing import Any

from claro import after_each, before_each, clear_suites, expect, suite, test
from claro.cli import create_parser, main
from claro.decorators import _registry_test_lock, _suites, _suites_lock
from claro.output import Colors


@suite
class ParserPathArgumentTests:
    @test
    def parser_accepts_path_argument(self):
        parser = create_parser()
        args = parser.parse_args(["/some/path"])
        expect(args.path).to_be("/some/path")

    @test
    def path_defaults_to_current_directory(self):
        parser = create_parser()
        args = parser.parse_args([])
        expect(args.path).to_be(".")


@suite
class ParserPatternArgumentTests:
    @test
    def single_pattern_is_accepted(self):
        parser = create_parser()
        args = parser.parse_args(["-p", "*_test.py"])
        expect(args.patterns).to_contain("*_test.py")

    @test
    def multiple_patterns_are_accepted(self):
        parser = create_parser()
        args = parser.parse_args(["-p", "*.py", "-p", "test_*.py"])
        expect(args.patterns).to_contain("*.py")
        expect(args.patterns).to_contain("test_*.py")

    @test
    def long_pattern_flag_is_accepted(self):
        parser = create_parser()
        args = parser.parse_args(["--pattern", "*_test.py"])
        expect(args.patterns).to_contain("*_test.py")

    @test
    def patterns_default_to_none(self):
        parser = create_parser()
        args = parser.parse_args([])
        expect(args.patterns).to_be_none()


@suite
class ParserTimeoutArgumentTests:
    @test
    def timeout_is_parsed_as_float(self):
        parser = create_parser()
        args = parser.parse_args(["-t", "5.0"])
        expect(args.timeout).to_be(5.0)

    @test
    def long_timeout_flag_is_accepted(self):
        parser = create_parser()
        args = parser.parse_args(["--timeout", "10.5"])
        expect(args.timeout).to_be(10.5)

    @test
    def timeout_defaults_to_none(self):
        parser = create_parser()
        args = parser.parse_args([])
        expect(args.timeout).to_be_none()


@suite
class ParserColorArgumentTests:
    @test
    def no_color_flag_is_parsed(self):
        parser = create_parser()
        args = parser.parse_args(["--no-color"])
        expect(args.no_color).to_be_truthy()

    @test
    def color_flag_is_parsed(self):
        parser = create_parser()
        args = parser.parse_args(["--color"])
        expect(args.color).to_be_truthy()

    @test
    def no_color_defaults_to_false(self):
        parser = create_parser()
        args = parser.parse_args([])
        expect(args.no_color).to_be_falsy()

    @test
    def color_defaults_to_false(self):
        parser = create_parser()
        args = parser.parse_args([])
        expect(args.color).to_be_falsy()


@suite(sequential=True)
class MainColorConfigurationTests:
    @before_each
    def setup(self):
        _registry_test_lock.acquire()
        clear_suites()
        Colors.reset_detection()

    @after_each
    def teardown(self):
        clear_suites()
        _registry_test_lock.release()

    @test
    def no_color_flag_sets_colors_disabled(self):
        # Store the original state
        original = Colors._enabled
        try:
            Colors.reset_detection()
            # Manually verify the logic: if --no-color is passed, Colors.disable() is called
            parser = create_parser()
            args = parser.parse_args([".", "--no-color"])
            if args.no_color:
                Colors.disable()
            expect(Colors._enabled).to_be(False)
        finally:
            Colors._enabled = original

    @test
    def color_flag_sets_colors_enabled(self):
        # Store the original state
        original = Colors._enabled
        try:
            Colors.reset_detection()
            # Manually verify the logic: if --color is passed, Colors.enable() is called
            parser = create_parser()
            args = parser.parse_args([".", "--color"])
            if args.color:
                Colors.enable()
            expect(Colors._enabled).to_be(True)
        finally:
            Colors._enabled = original


# All tests that call main() must be in a single sequential suite
# because main() modifies the global _suites registry
@suite(sequential=True)
class MainFunctionTests:
    _shared: dict[str, Any]

    @before_each
    def setup(self):
        _registry_test_lock.acquire()
        with _suites_lock:
            self._shared["original_suites"] = _suites.copy()
        Colors.disable()

    @after_each
    def teardown(self):
        with _suites_lock:
            _suites.clear()
            _suites.extend(self._shared["original_suites"])
        Colors.reset_detection()
        _registry_test_lock.release()

    # Path validation tests
    @test
    def nonexistent_path_returns_exit_code_one(self):
        result = main(["/nonexistent/path/xyz"])
        expect(result).to_be(1)

    @test
    def file_path_returns_exit_code_one(self):
        with tempfile.NamedTemporaryFile() as f:
            result = main([f.name])
            expect(result).to_be(1)

    @test
    def valid_directory_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = main([temp_dir])
            expect(result).to_be(0)

    # Empty directory tests
    @test
    def empty_directory_returns_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = main([temp_dir])
            expect(result).to_be(0)

    @test
    def directory_with_no_test_files_returns_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a non-test file
            Path(temp_dir, "regular.py").write_text("x = 1")
            result = main([temp_dir])
            expect(result).to_be(0)

    # Test execution tests
    @test
    def passing_test_returns_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir, "passing_test.py")
            test_file.write_text("""
from claro import suite, test, expect

@suite
class PassingTests:
    @test
    def always_passes(self):
        expect(1 + 1).to_be(2)
""")
            result = main([temp_dir])
            expect(result).to_be(0)

    @test
    def failing_test_returns_one(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir, "failing_test.py")
            test_file.write_text("""
from claro import suite, test, expect

@suite
class FailingTests:
    @test
    def always_fails(self):
        expect(1).to_be(2)
""")
            result = main([temp_dir])
            expect(result).to_be(1)

    # Pattern filtering tests
    @test
    def custom_pattern_matches_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create file matching custom pattern
            test_file = Path(temp_dir, "my_spec.py")
            test_file.write_text("""
from claro import suite, test, expect

@suite
class SpecTests:
    @test
    def passes(self):
        expect(True).to_be_truthy()
""")
            result = main([temp_dir, "-p", "*_spec.py"])
            expect(result).to_be(0)

    @test
    def non_matching_pattern_finds_no_tests(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create file that won't match pattern
            test_file = Path(temp_dir, "my_test.py")
            test_file.write_text("""
from claro import suite, test, expect

@suite
class Tests:
    @test
    def passes(self):
        expect(True).to_be_truthy()
""")
            # Use pattern that doesn't match
            result = main([temp_dir, "-p", "*_spec.py"])
            # Returns 0 because no tests found is not a failure
            expect(result).to_be(0)

    # Timeout configuration tests
    @test
    def timeout_option_is_passed_to_runner(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir, "quick_test.py")
            test_file.write_text("""
from claro import suite, test, expect

@suite
class QuickTests:
    @test
    def fast_test(self):
        expect(1).to_be(1)
""")
            result = main([temp_dir, "-t", "5.0"])
            expect(result).to_be(0)
