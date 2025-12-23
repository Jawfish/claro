"""Tests for the enhance module."""

import linecache
import tempfile
import textwrap
from pathlib import Path

from claro import expect, suite, test
from claro.enhance import enhance_assertion_error
from claro.types import MISSING


def run_assert_and_enhance(code: str) -> tuple[str | None, object, object]:
    """
    Execute an assert statement and return the enhanced error info.

    Creates a temp file with the code so linecache can find the source.
    Returns (msg, expected, actual) tuple.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        filepath = Path(f.name)

    # Force linecache to read the new file
    linecache.checkcache(str(filepath))

    try:
        # Execute the code - exec creates its own frame with locals/globals
        exec(compile(code, str(filepath), "exec"))  # noqa: S102
        filepath.unlink()
        msg = "Expected AssertionError"
        raise RuntimeError(msg)
    except AssertionError as e:
        # File must exist during enhancement for linecache
        result = enhance_assertion_error(e)
        filepath.unlink()
        linecache.clearcache()
        return result


@suite
class EqualityEnhancementTests:
    @test
    def equality_assertion_extracts_operand_values(self):
        code = textwrap.dedent("""
            x = 5
            y = 10
            assert x == y
        """).strip()
        msg, expected, actual = run_assert_and_enhance(code)
        expect(actual).to_be(5)
        expect(expected).to_be(10)
        expect(msg).to_contain("to equal")

    @test
    def inequality_assertion_extracts_operand_values(self):
        code = textwrap.dedent("""
            x = 5
            assert x != 5
        """).strip()
        msg, expected, actual = run_assert_and_enhance(code)
        expect(actual).to_be(5)
        expect(expected).to_be(5)
        expect(msg).to_contain("to not equal")


@suite
class ComparisonEnhancementTests:
    @test
    def less_than_assertion_extracts_operand_values(self):
        code = textwrap.dedent("""
            x = 10
            y = 5
            assert x < y
        """).strip()
        msg, expected, actual = run_assert_and_enhance(code)
        expect(actual).to_be(10)
        expect(expected).to_be(5)
        expect(msg).to_contain("to be less than")

    @test
    def greater_than_assertion_extracts_operand_values(self):
        code = textwrap.dedent("""
            x = 5
            y = 10
            assert x > y
        """).strip()
        msg, expected, actual = run_assert_and_enhance(code)
        expect(actual).to_be(5)
        expect(expected).to_be(10)
        expect(msg).to_contain("to be greater than")

    @test
    def less_than_or_equal_assertion_extracts_operand_values(self):
        code = textwrap.dedent("""
            x = 10
            y = 5
            assert x <= y
        """).strip()
        msg, expected, actual = run_assert_and_enhance(code)
        expect(actual).to_be(10)
        expect(expected).to_be(5)
        expect(msg).to_contain("to be at most")

    @test
    def greater_than_or_equal_assertion_extracts_operand_values(self):
        code = textwrap.dedent("""
            x = 5
            y = 10
            assert x >= y
        """).strip()
        msg, expected, actual = run_assert_and_enhance(code)
        expect(actual).to_be(5)
        expect(expected).to_be(10)
        expect(msg).to_contain("to be at least")


@suite
class MembershipEnhancementTests:
    @test
    def in_assertion_extracts_operand_values(self):
        code = textwrap.dedent("""
            item = "x"
            collection = ["a", "b", "c"]
            assert item in collection
        """).strip()
        msg, expected, actual = run_assert_and_enhance(code)
        expect(actual).to_be("x")
        expect(expected).to_be(["a", "b", "c"])
        expect(msg).to_contain("to be in")

    @test
    def not_in_assertion_extracts_operand_values(self):
        code = textwrap.dedent("""
            item = "a"
            collection = ["a", "b", "c"]
            assert item not in collection
        """).strip()
        msg, expected, actual = run_assert_and_enhance(code)
        expect(actual).to_be("a")
        expect(expected).to_be(["a", "b", "c"])
        expect(msg).to_contain("to not be in")


@suite
class IdentityEnhancementTests:
    @test
    def is_assertion_extracts_operand_values(self):
        code = textwrap.dedent("""
            x = [1, 2, 3]
            y = [1, 2, 3]
            assert x is y
        """).strip()
        msg, expected, actual = run_assert_and_enhance(code)
        expect(actual).to_be([1, 2, 3])
        expect(expected).to_be([1, 2, 3])
        expect(msg).to_contain("to be")

    @test
    def is_not_assertion_extracts_operand_values(self):
        code = textwrap.dedent("""
            x = None
            assert x is not None
        """).strip()
        msg, expected, actual = run_assert_and_enhance(code)
        expect(actual).to_be_none()
        expect(expected).to_be_none()
        expect(msg).to_contain("to not be")


@suite
class AssertionWithMessageTests:
    @test
    def assertion_with_message_returns_missing(self):
        # Note: The current implementation doesn't handle assertions with messages
        # because 'x == y, "message"' parses as a valid tuple expression
        code = textwrap.dedent("""
            x = 5
            y = 10
            assert x == y, "custom message"
        """).strip()
        msg, expected, actual = run_assert_and_enhance(code)
        expect(expected).to_be(MISSING)
        expect(actual).to_be(MISSING)
        expect(msg).to_be_none()


@suite
class EnhancementFailureTests:
    @test
    def non_assert_exception_returns_missing(self):
        try:
            raise AssertionError("plain assertion error")
        except AssertionError as e:
            # Create a traceback manually but it won't have assert statement
            msg, expected, actual = enhance_assertion_error(e)
            # Without a traceback pointing to an assert statement, returns MISSING
            expect(expected).to_be(MISSING)
            expect(actual).to_be(MISSING)
            expect(msg).to_be_none()

    @test
    def assertion_without_traceback_returns_missing(self):
        exc = AssertionError("no traceback")
        exc.__traceback__ = None
        msg, expected, actual = enhance_assertion_error(exc)
        expect(expected).to_be(MISSING)
        expect(actual).to_be(MISSING)
        expect(msg).to_be_none()

    @test
    def chained_comparison_returns_missing(self):
        # Chained comparisons like 'a < b < c' have multiple ops and aren't supported
        code = textwrap.dedent("""
            x = 5
            assert 0 < x < 3
        """).strip()
        msg, expected, actual = run_assert_and_enhance(code)
        expect(expected).to_be(MISSING)
        expect(actual).to_be(MISSING)
        expect(msg).to_be_none()

    @test
    def boolean_expression_returns_missing(self):
        # Boolean expressions without comparison operators aren't enhanced
        code = textwrap.dedent("""
            x = False
            assert x
        """).strip()
        msg, expected, actual = run_assert_and_enhance(code)
        expect(expected).to_be(MISSING)
        expect(actual).to_be(MISSING)
        expect(msg).to_be_none()


@suite
class ExpressionEnhancementTests:
    @test
    def assertion_with_expression_extracts_values(self):
        code = textwrap.dedent("""
            values = [1, 2, 3]
            assert sum(values) == 10
        """).strip()
        msg, expected, actual = run_assert_and_enhance(code)
        expect(actual).to_be(6)
        expect(expected).to_be(10)

    @test
    def assertion_with_string_literals_extracts_values(self):
        code = textwrap.dedent("""
            result = "hello"
            assert result == "world"
        """).strip()
        msg, expected, actual = run_assert_and_enhance(code)
        expect(actual).to_be("hello")
        expect(expected).to_be("world")
