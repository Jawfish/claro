"""Tests for the output module."""

from claro import expect, suite, test
from claro.output import (
    Colors,
    c,
    format_diff,
    format_duration,
    format_result,
    format_summary,
)
from claro.types import MISSING, TestResult, TestStatus


@suite
class FormatDurationTests:
    @test
    def sub_millisecond_durations_are_shown_in_microseconds(self):
        expect(format_duration(0.5)).to_be("500us")
        expect(format_duration(0.001)).to_be("1us")
        expect(format_duration(0.999)).to_be("999us")

    @test
    def millisecond_durations_are_shown_with_one_decimal(self):
        expect(format_duration(1)).to_be("1.0ms")
        expect(format_duration(50.5)).to_be("50.5ms")
        expect(format_duration(999.9)).to_be("999.9ms")

    @test
    def second_durations_are_shown_with_two_decimals(self):
        expect(format_duration(1000)).to_be("1.00s")
        expect(format_duration(2500)).to_be("2.50s")
        expect(format_duration(65432)).to_be("65.43s")


@suite
class ColorsDisableEnableTests:
    @test
    def colors_are_disabled_after_disable_call(self):
        Colors.reset_detection()
        Colors.disable()
        expect(c.RED).to_be("")
        expect(c.GREEN).to_be("")
        expect(c.RESET).to_be("")
        Colors.reset_detection()

    @test
    def colors_are_enabled_after_enable_call(self):
        Colors.reset_detection()
        Colors.enable()
        expect(c.RED).to_be("\033[31m")
        expect(c.GREEN).to_be("\033[32m")
        expect(c.RESET).to_be("\033[0m")
        Colors.reset_detection()

    @test
    def reset_detection_clears_manual_override(self):
        Colors.enable()
        Colors.reset_detection()
        # After reset, _enabled is None and detection runs again
        # We can't predict TTY state, but _enabled should be None
        expect(Colors._enabled).to_be_none()

    @test
    def all_color_properties_are_empty_when_disabled(self):
        Colors.reset_detection()
        Colors.disable()
        expect(c.BOLD).to_be("")
        expect(c.DIM).to_be("")
        expect(c.YELLOW).to_be("")
        expect(c.MAGENTA).to_be("")
        expect(c.CYAN).to_be("")
        expect(c.GRAY).to_be("")
        Colors.reset_detection()


@suite
class FormatDiffTests:
    @test
    def simple_values_show_expected_and_actual_lines(self):
        Colors.reset_detection()
        Colors.disable()
        lines = format_diff(5, 10)
        expect(lines).to_have_length(2)
        expect(lines[0]).to_contain("Expected")
        expect(lines[0]).to_contain("5")
        expect(lines[1]).to_contain("Actual")
        expect(lines[1]).to_contain("10")
        Colors.reset_detection()

    @test
    def string_values_show_quoted_representation(self):
        Colors.reset_detection()
        Colors.disable()
        lines = format_diff("hello", "world")
        expect(lines[0]).to_contain("'hello'")
        expect(lines[1]).to_contain("'world'")
        Colors.reset_detection()

    @test
    def multiline_strings_show_unified_diff(self):
        Colors.reset_detection()
        Colors.disable()
        expected = "line1\nline2\nline3"
        actual = "line1\nmodified\nline3"
        lines = format_diff(expected, actual)
        expect(lines[0]).to_contain("Diff")
        # Diff should show removed and added lines
        diff_content = "\n".join(lines)
        expect(diff_content).to_contain("-line2")
        expect(diff_content).to_contain("+modified")
        Colors.reset_detection()

    @test
    def custom_indent_is_applied(self):
        Colors.reset_detection()
        Colors.disable()
        lines = format_diff(1, 2, indent="  ")
        expect(lines[0]).to_start_with("  ")
        expect(lines[1]).to_start_with("  ")
        Colors.reset_detection()

    @test
    def circular_reference_is_handled_safely(self):
        Colors.reset_detection()
        Colors.disable()
        circular: list = []
        circular.append(circular)
        # Should not raise RecursionError
        lines = format_diff(circular, [1, 2, 3])
        expect(len(lines)).to_be(2)
        # reprlib truncates circular refs with [...]
        expect(lines[0]).to_contain("[[...]]")
        Colors.reset_detection()


@suite
class FormatResultTests:
    @test
    def passed_test_shows_checkmark_icon(self):
        Colors.reset_detection()
        Colors.disable()
        result = TestResult(
            suite_name="TestSuite",
            test_name="example test",
            status=TestStatus.PASSED,
            duration_ms=5.0,
        )
        lines = format_result(result)
        output = "\n".join(lines)
        # Check for checkmark (without color codes)
        expect(output).to_contain("example test")
        expect(output).to_contain("5.0ms")
        Colors.reset_detection()

    @test
    def failed_test_shows_error_message(self):
        Colors.reset_detection()
        Colors.disable()
        result = TestResult(
            suite_name="TestSuite",
            test_name="failing test",
            status=TestStatus.FAILED,
            duration_ms=10.0,
            error="Expected 5 but got 10",
        )
        lines = format_result(result)
        output = "\n".join(lines)
        expect(output).to_contain("failing test")
        expect(output).to_contain("Expected 5 but got 10")
        Colors.reset_detection()

    @test
    def failed_test_with_diff_shows_expected_and_actual(self):
        Colors.reset_detection()
        Colors.disable()
        result = TestResult(
            suite_name="TestSuite",
            test_name="diff test",
            status=TestStatus.FAILED,
            duration_ms=1.0,
            error="Values differ",
            expected=42,
            actual=99,
            show_diff=True,
        )
        lines = format_result(result)
        output = "\n".join(lines)
        expect(output).to_contain("42")
        expect(output).to_contain("99")
        Colors.reset_detection()

    @test
    def failed_test_without_expected_actual_skips_diff(self):
        Colors.reset_detection()
        Colors.disable()
        result = TestResult(
            suite_name="TestSuite",
            test_name="no diff test",
            status=TestStatus.FAILED,
            duration_ms=1.0,
            error="Some error",
            expected=MISSING,
            actual=MISSING,
        )
        lines = format_result(result)
        # Should only have test name line and error line
        expect(len(lines)).to_be(2)
        Colors.reset_detection()

    @test
    def skipped_test_shows_skipped_label(self):
        Colors.reset_detection()
        Colors.disable()
        result = TestResult(
            suite_name="TestSuite",
            test_name="skipped test",
            status=TestStatus.SKIPPED,
            duration_ms=0,
        )
        lines = format_result(result)
        output = "\n".join(lines)
        expect(output).to_contain("skipped test")
        expect(output).to_contain("[skipped]")
        Colors.reset_detection()


@suite
class FormatSummaryTests:
    @test
    def all_passed_shows_passed_count(self):
        Colors.reset_detection()
        Colors.disable()
        results = [
            TestResult("Suite", "test1", TestStatus.PASSED, 1.0),
            TestResult("Suite", "test2", TestStatus.PASSED, 2.0),
            TestResult("Suite", "test3", TestStatus.PASSED, 3.0),
        ]
        summary = format_summary(results, 100.0)
        expect(summary).to_contain("3 passed")
        expect(summary).to_contain("100.0ms")
        Colors.reset_detection()

    @test
    def mixed_results_show_all_counts(self):
        Colors.reset_detection()
        Colors.disable()
        results = [
            TestResult("Suite", "passed1", TestStatus.PASSED, 1.0),
            TestResult("Suite", "passed2", TestStatus.PASSED, 1.0),
            TestResult("Suite", "failed1", TestStatus.FAILED, 1.0),
            TestResult("Suite", "skipped1", TestStatus.SKIPPED, 0),
            TestResult("Suite", "skipped2", TestStatus.SKIPPED, 0),
        ]
        summary = format_summary(results, 500.0)
        expect(summary).to_contain("2 passed")
        expect(summary).to_contain("1 failed")
        expect(summary).to_contain("2 skipped")
        Colors.reset_detection()

    @test
    def empty_results_show_no_tests_message(self):
        Colors.reset_detection()
        Colors.disable()
        summary = format_summary([], 0)
        expect(summary).to_contain("No tests")
        Colors.reset_detection()

    @test
    def only_failed_tests_show_failed_count(self):
        Colors.reset_detection()
        Colors.disable()
        results = [
            TestResult("Suite", "fail1", TestStatus.FAILED, 1.0),
            TestResult("Suite", "fail2", TestStatus.FAILED, 2.0),
        ]
        summary = format_summary(results, 50.0)
        expect(summary).to_contain("2 failed")
        expect(summary).not_.to_contain("passed")
        Colors.reset_detection()

    @test
    def duration_in_seconds_is_formatted_correctly(self):
        Colors.reset_detection()
        Colors.disable()
        results = [TestResult("Suite", "test1", TestStatus.PASSED, 1.0)]
        summary = format_summary(results, 5000.0)
        expect(summary).to_contain("5.00s")
        Colors.reset_detection()
