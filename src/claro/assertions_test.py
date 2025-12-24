"""Tests for the assertions module."""

from claro import ExpectationError, expect, suite, test


@suite
class EqualityTests:
    @test
    def equal_values_are_equal(self):
        expect(5).to_be(5)
        expect("hello").to_be("hello")
        expect([1, 2, 3]).to_be([1, 2, 3])

    @test
    def different_values_are_not_equal(self):
        expect(lambda: expect(5).to_be(10)).to_raise_sync(ExpectationError)

    @test
    def not_accepts_different_values(self):
        expect(5).not_.to_be(10)

    @test
    def not_rejects_equal_values(self):
        expect(lambda: expect(5).not_.to_be(5)).to_raise_sync(ExpectationError)


@suite
class TruthinessTests:
    @test
    def non_empty_values_are_truthy(self):
        expect(True).to_be_truthy()
        expect(1).to_be_truthy()
        expect("hello").to_be_truthy()
        expect([1]).to_be_truthy()

    @test
    def empty_values_are_not_truthy(self):
        expect(lambda: expect(False).to_be_truthy()).to_raise_sync(ExpectationError)
        expect(lambda: expect(0).to_be_truthy()).to_raise_sync(ExpectationError)
        expect(lambda: expect("").to_be_truthy()).to_raise_sync(ExpectationError)

    @test
    def empty_values_are_falsy(self):
        expect(False).to_be_falsy()
        expect(0).to_be_falsy()
        expect("").to_be_falsy()
        expect([]).to_be_falsy()

    @test
    def non_empty_values_are_not_falsy(self):
        expect(lambda: expect(True).to_be_falsy()).to_raise_sync(ExpectationError)


@suite
class NoneTests:
    @test
    def none_is_none(self):
        expect(None).to_be_none()

    @test
    def non_none_values_are_not_none(self):
        expect(lambda: expect(5).to_be_none()).to_raise_sync(ExpectationError)

    @test
    def non_none_values_are_defined(self):
        expect(5).to_be_defined()
        expect("").to_be_defined()
        expect(0).to_be_defined()

    @test
    def none_is_not_defined(self):
        expect(lambda: expect(None).to_be_defined()).to_raise_sync(ExpectationError)


@suite
class CollectionTests:
    @test
    def length_matches_expected_count(self):
        expect([1, 2, 3]).to_have_length(3)
        expect("hello").to_have_length(5)
        expect({}).to_have_length(0)

    @test
    def length_mismatch_is_rejected(self):
        expect(lambda: expect([1, 2, 3]).to_have_length(5)).to_raise_sync(
            ExpectationError
        )

    @test
    def empty_collections_are_empty(self):
        expect([]).to_be_empty()
        expect("").to_be_empty()
        expect({}).to_be_empty()

    @test
    def non_empty_collections_are_not_empty(self):
        expect(lambda: expect([1]).to_be_empty()).to_raise_sync(ExpectationError)

    @test
    def present_items_are_found(self):
        expect([1, 2, 3]).to_contain(2)
        expect("hello").to_contain("ell")
        expect({"a": 1}).to_contain("a")

    @test
    def absent_items_are_not_found(self):
        expect(lambda: expect([1, 2, 3]).to_contain(5)).to_raise_sync(ExpectationError)


@suite
class ComparisonTests:
    @test
    def larger_values_are_greater(self):
        expect(5).to_be_greater_than(3)

    @test
    def smaller_values_are_not_greater(self):
        expect(lambda: expect(3).to_be_greater_than(5)).to_raise_sync(ExpectationError)

    @test
    def smaller_values_are_less(self):
        expect(3).to_be_less_than(5)

    @test
    def larger_values_are_not_less(self):
        expect(lambda: expect(5).to_be_less_than(3)).to_raise_sync(ExpectationError)

    @test
    def values_in_range_are_accepted(self):
        expect(5).to_be_between(1, 10)
        expect(1).to_be_between(1, 10)
        expect(10).to_be_between(1, 10)

    @test
    def values_outside_range_are_rejected(self):
        expect(lambda: expect(0).to_be_between(1, 10)).to_raise_sync(ExpectationError)


@suite
class StringTests:
    @test
    def matching_prefix_is_found(self):
        expect("hello world").to_start_with("hello")

    @test
    def wrong_prefix_is_rejected(self):
        expect(lambda: expect("hello").to_start_with("world")).to_raise_sync(
            ExpectationError
        )

    @test
    def matching_suffix_is_found(self):
        expect("hello world").to_end_with("world")

    @test
    def wrong_suffix_is_rejected(self):
        expect(lambda: expect("hello").to_end_with("world")).to_raise_sync(
            ExpectationError
        )

    @test
    def matching_pattern_is_found(self):
        expect("hello123").to_match(r"\d+")

    @test
    def non_matching_pattern_is_rejected(self):
        expect(lambda: expect("hello").to_match(r"\d+")).to_raise_sync(ExpectationError)


@suite
class ExceptionTests:
    @test
    def expected_exception_is_caught(self):
        def raises_value_error():
            raise ValueError("test")

        expect(raises_value_error).to_raise_sync(ValueError)

    @test
    def missing_exception_fails(self):
        def no_raise():
            pass

        expect(lambda: expect(no_raise).to_raise_sync(ValueError)).to_raise_sync(
            ExpectationError
        )

    @test
    def wrong_exception_type_fails(self):
        def raises_type_error():
            raise TypeError("test")

        expect(
            lambda: expect(raises_type_error).to_raise_sync(ValueError)
        ).to_raise_sync(ExpectationError)


@suite
class AliasTests:
    @test
    def to_not_is_alias_for_not_(self):
        # to_not should work the same as not_
        expect(5).to_not.to_be(10)

    @test
    def to_not_rejects_equal_values(self):
        expect(lambda: expect(5).to_not.to_be(5)).to_raise_sync(ExpectationError)

    @test
    def to_equal_is_alias_for_to_be(self):
        expect(5).to_equal(5)
        expect("hello").to_equal("hello")

    @test
    def to_equal_rejects_different_values(self):
        expect(lambda: expect(5).to_equal(10)).to_raise_sync(ExpectationError)


@suite
class IdentityTests:
    @test
    def same_object_passes_identity_check(self):
        obj = {"key": "value"}
        expect(obj).to_be_same(obj)

    @test
    def equal_but_different_objects_fail_identity_check(self):
        obj1 = {"key": "value"}
        obj2 = {"key": "value"}
        expect(lambda: expect(obj1).to_be_same(obj2)).to_raise_sync(ExpectationError)


@suite
class TypeCheckingTests:
    @test
    def value_is_instance_of_class(self):
        expect("hello").to_be_instance_of(str)
        expect(5).to_be_instance_of(int)
        expect([1, 2]).to_be_instance_of(list)

    @test
    def value_is_instance_of_parent_class(self):
        # bool is subclass of int
        expect(True).to_be_instance_of(int)

    @test
    def wrong_instance_type_fails(self):
        expect(lambda: expect("hello").to_be_instance_of(int)).to_raise_sync(
            ExpectationError
        )

    @test
    def exact_type_matches(self):
        expect("hello").to_be_type(str)
        expect(5).to_be_type(int)

    @test
    def subclass_fails_exact_type_check(self):
        # bool is subclass of int, but not exactly int
        expect(lambda: expect(True).to_be_type(int)).to_raise_sync(ExpectationError)


@suite
class FloatComparisonTests:
    @test
    def close_values_pass_with_default_delta(self):
        expect(1.0000000001).to_be_close_to(1.0)

    @test
    def close_values_pass_with_custom_delta(self):
        expect(1.05).to_be_close_to(1.0, delta=0.1)

    @test
    def distant_values_fail(self):
        expect(lambda: expect(1.5).to_be_close_to(1.0, delta=0.1)).to_raise_sync(
            ExpectationError
        )

    @test
    def nan_actual_fails_with_explicit_message(self):
        import math

        expect(lambda: expect(math.nan).to_be_close_to(1.0)).to_raise_sync(
            ExpectationError
        )

    @test
    def nan_expected_fails_with_explicit_message(self):
        import math

        expect(lambda: expect(1.0).to_be_close_to(math.nan)).to_raise_sync(
            ExpectationError
        )

    @test
    def positive_infinity_equals_itself(self):
        import math

        expect(math.inf).to_be_close_to(math.inf)

    @test
    def negative_infinity_equals_itself(self):
        import math

        expect(-math.inf).to_be_close_to(-math.inf)

    @test
    def positive_infinity_not_equal_to_negative(self):
        import math

        expect(lambda: expect(math.inf).to_be_close_to(-math.inf)).to_raise_sync(
            ExpectationError
        )

    @test
    def infinity_not_close_to_finite_number(self):
        import math

        expect(lambda: expect(math.inf).to_be_close_to(1e308)).to_raise_sync(
            ExpectationError
        )


@suite
class NumericComparisonTests:
    @test
    def greater_than_or_equal_with_greater_value(self):
        expect(5).to_be_greater_than_or_equal(3)

    @test
    def greater_than_or_equal_with_equal_value(self):
        expect(5).to_be_greater_than_or_equal(5)

    @test
    def greater_than_or_equal_fails_with_lesser_value(self):
        expect(lambda: expect(3).to_be_greater_than_or_equal(5)).to_raise_sync(
            ExpectationError
        )

    @test
    def less_than_or_equal_with_lesser_value(self):
        expect(3).to_be_less_than_or_equal(5)

    @test
    def less_than_or_equal_with_equal_value(self):
        expect(5).to_be_less_than_or_equal(5)

    @test
    def less_than_or_equal_fails_with_greater_value(self):
        expect(lambda: expect(5).to_be_less_than_or_equal(3)).to_raise_sync(
            ExpectationError
        )

    @test
    def between_exclusive_mode_excludes_boundaries(self):
        expect(5).to_be_between(1, 10, inclusive=False)

    @test
    def between_exclusive_mode_fails_at_boundaries(self):
        expect(lambda: expect(1).to_be_between(1, 10, inclusive=False)).to_raise_sync(
            ExpectationError
        )
        expect(lambda: expect(10).to_be_between(1, 10, inclusive=False)).to_raise_sync(
            ExpectationError
        )

    @test
    def between_rejects_invalid_range(self):
        expect(lambda: expect(5).to_be_between(10, 1)).to_raise_sync(ValueError)

    @test
    def between_allows_equal_low_and_high(self):
        expect(5).to_be_between(5, 5)


@suite
class IncludeTests:
    @test
    def include_passes_when_all_items_present(self):
        expect([1, 2, 3, 4, 5]).to_include(1, 3, 5)

    @test
    def include_fails_when_some_items_missing(self):
        expect(lambda: expect([1, 2, 3]).to_include(1, 5, 6)).to_raise_sync(
            ExpectationError
        )


@suite
class PropertyTests:
    @test
    def has_property_on_dict(self):
        expect({"name": "Alice"}).to_have_property("name")

    @test
    def has_property_with_value_on_dict(self):
        expect({"name": "Alice"}).to_have_property("name", "Alice")

    @test
    def has_property_on_object(self):
        class Person:
            name = "Bob"

        expect(Person()).to_have_property("name")

    @test
    def has_property_with_value_on_object(self):
        class Person:
            name = "Bob"

        expect(Person()).to_have_property("name", "Bob")

    @test
    def missing_property_fails(self):
        expect(lambda: expect({}).to_have_property("missing")).to_raise_sync(
            ExpectationError
        )

    @test
    def wrong_property_value_fails(self):
        expect(
            lambda: expect({"name": "Alice"}).to_have_property("name", "Bob")
        ).to_raise_sync(ExpectationError)


@suite
class MatchObjectTests:
    @test
    def dict_matches_subset(self):
        expect({"a": 1, "b": 2, "c": 3}).to_match_object({"a": 1, "b": 2})

    @test
    def object_matches_subset(self):
        class Obj:
            a = 1
            b = 2
            c = 3

        expect(Obj()).to_match_object({"a": 1, "b": 2})

    @test
    def missing_key_fails(self):
        expect(
            lambda: expect({"a": 1}).to_match_object({"a": 1, "b": 2})
        ).to_raise_sync(ExpectationError)

    @test
    def wrong_value_fails(self):
        expect(
            lambda: expect({"a": 1, "b": 2}).to_match_object({"a": 1, "b": 99})
        ).to_raise_sync(ExpectationError)


@suite
class ContainStringTests:
    @test
    def string_contains_substring(self):
        expect("hello world").to_contain_string("world")

    @test
    def string_missing_substring_fails(self):
        expect(lambda: expect("hello").to_contain_string("world")).to_raise_sync(
            ExpectationError
        )


@suite
class AsyncExceptionTests:
    @test
    async def async_exception_is_caught(self):
        async def raises_async():
            raise ValueError("async error")

        await expect(raises_async).to_raise(ValueError)

    @test
    async def async_missing_exception_fails(self):
        async def no_raise():
            pass

        raised = False
        try:
            await expect(no_raise).to_raise(ValueError)
        except ExpectationError:
            raised = True

        expect(raised).to_be(True)

    @test
    async def async_wrong_exception_type_fails(self):
        async def raises_type_error():
            raise TypeError("wrong type")

        raised = False
        try:
            await expect(raises_type_error).to_raise(ValueError)
        except ExpectationError:
            raised = True

        expect(raised).to_be(True)

    @test
    async def sync_function_in_async_context_works(self):
        def raises_sync():
            raise ValueError("sync error")

        await expect(raises_sync).to_raise(ValueError)
