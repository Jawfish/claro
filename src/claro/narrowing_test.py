"""Tests for the narrowing module."""

from claro import ExpectationError, expect, suite, test
from claro.narrowing import narrow, require


@suite
class RequireTests:
    @test
    def value_is_returned_when_not_none(self):
        result = require("hello")
        expect(result).to_be("hello")

    @test
    def expectation_error_is_raised_when_none(self):
        expect(lambda: require(None)).to_raise_sync(ExpectationError)

    @test
    def custom_message_is_used_when_none(self):
        try:
            require(None, "custom message")
        except ExpectationError as e:
            expect(str(e)).to_be("custom message")
            return
        raise AssertionError("Expected ExpectationError")


@suite
class NarrowTests:
    @test
    def value_is_returned_when_correct_type(self):
        result = narrow("hello", str)
        expect(result).to_be("hello")

    @test
    def expectation_error_is_raised_when_wrong_type(self):
        expect(lambda: narrow("hello", int)).to_raise_sync(ExpectationError)

    @test
    def subclass_is_accepted(self):
        # bool is a subclass of int
        result = narrow(True, int)
        expect(result).to_be(True)

    @test
    def custom_message_is_used_when_wrong_type(self):
        try:
            narrow("hello", int, "custom narrow message")
        except ExpectationError as e:
            expect(str(e)).to_be("custom narrow message")
            return
        raise AssertionError("Expected ExpectationError")

    @test
    def default_message_includes_type_names(self):
        try:
            narrow("hello", int)
        except ExpectationError as e:
            expect(str(e)).to_contain("int")
            expect(str(e)).to_contain("str")
            return
        raise AssertionError("Expected ExpectationError")
