"""Tests for the decorators module."""

from claro import (
    after_all,
    after_each,
    before_all,
    before_each,
    clear_suites,
    expect,
    get_suites,
    suite,
    test,
)


@suite
class SuiteRegistrationTests:
    @before_each
    def reset_registry(self):
        clear_suites()

    @test
    def suite_is_registered_with_class_name(self):
        @suite
        class MyTestSuite:
            pass

        suites = get_suites()
        expect(suites).to_have_length(1)
        expect(suites[0].name).to_be("MyTestSuite")

    @test
    def suite_timeout_is_set_from_argument(self):
        @suite(timeout=10.0)
        class TimeoutSuite:
            pass

        suites = get_suites()
        expect(suites[0].timeout).to_be(10.0)


@suite
class TestMarkerTests:
    @before_each
    def reset_registry(self):
        clear_suites()

    @test
    def test_decorator_marks_methods_as_tests(self):
        @suite
        class MarkedTests:
            @test
            def a_test(self):
                pass

        suites = get_suites()
        expect(suites[0].tests).to_have_length(1)
        expect(suites[0].tests[0].name).to_be("a_test")

    @test
    def multiple_tests_are_collected(self):
        @suite
        class MultipleTests:
            @test
            def first(self):
                pass

            @test
            def second(self):
                pass

        suites = get_suites()
        test_names = [t.name for t in suites[0].tests]
        expect(test_names).to_contain("first")
        expect(test_names).to_contain("second")


@suite
class TestModifierTests:
    @before_each
    def reset_registry(self):
        clear_suites()

    @test
    def skip_marks_test_as_skipped(self):
        @suite
        class SkippedTests:
            @test.skip
            def skipped_test(self):
                pass

        suites = get_suites()
        expect(suites[0].tests[0].skip).to_be(True)


@suite
class SkipIfTests:
    @before_each
    def reset_registry(self):
        clear_suites()

    @test
    def skip_if_true_skips_test(self):
        @suite
        class ConditionalSkipTests:
            @test.skip_if(True, "condition met")
            def conditional_skip(self):
                pass

        suites = get_suites()
        expect(suites[0].tests[0].skip).to_be(True)
        expect(suites[0].tests[0].skip_reason).to_be("condition met")

    @test
    def skip_if_false_does_not_skip_test(self):
        @suite
        class ConditionalKeepTests:
            @test.skip_if(False, "condition not met")
            def conditional_keep(self):
                pass

        suites = get_suites()
        expect(suites[0].tests[0].skip).to_be(False)


@suite
class TimeoutTests:
    @before_each
    def reset_registry(self):
        clear_suites()

    @test
    def timeout_sets_test_timeout(self):
        @suite
        class TimeoutTests:
            @test.timeout(5.0)
            def slow_test(self):
                pass

        suites = get_suites()
        expect(suites[0].tests[0].timeout).to_be(5.0)


@suite
class ParametrizedTestTests:
    @before_each
    def reset_registry(self):
        clear_suites()

    @test
    def each_creates_parametrized_tests_from_tuples(self):
        @suite
        class ParametrizedTupleTests:
            @test.each([(1, 2), (3, 4)])
            def adds(self, a, b):
                pass

        suites = get_suites()
        expect(suites[0].tests).to_have_length(2)

    @test
    def parametrized_test_names_include_parameters(self):
        @suite
        class ParametrizedNameTests:
            @test.each([(1, 2), (3, 4)])
            def adds(self, a, b):
                pass

        suites = get_suites()
        test_names = [t.name for t in suites[0].tests]
        expect(test_names[0]).to_contain("1, 2")
        expect(test_names[1]).to_contain("3, 4")

    @test
    def parametrized_tests_receive_dict_parameters(self):
        @suite
        class ParametrizedDictTests:
            @test.each([{"a": 1, "b": 2}])
            def adds(self, a, b):
                pass

        suites = get_suites()
        expect(suites[0].tests[0].params).to_be({"a": 1, "b": 2})

    @test
    def parametrized_tests_use_custom_id_from_dict(self):
        @suite
        class ParametrizedIdTests:
            @test.each([{"a": 1, "b": 2, "id": "custom"}])
            def adds(self, a, b):
                pass

        suites = get_suites()
        expect(suites[0].tests[0].param_id).to_be("custom")
        expect(suites[0].tests[0].name).to_contain("custom")


@suite
class LifecycleDecoratorTests:
    @before_each
    def reset_registry(self):
        clear_suites()

    @test
    def before_each_marks_method_correctly(self):
        @before_each
        def setup():
            pass

        expect(getattr(setup, "_is_before_each", False)).to_be(True)

    @test
    def after_each_marks_method_correctly(self):
        @after_each
        def teardown():
            pass

        expect(getattr(teardown, "_is_after_each", False)).to_be(True)

    @test
    def before_all_marks_method_correctly(self):
        @before_all
        def setup_suite():
            pass

        expect(getattr(setup_suite, "_is_before_all", False)).to_be(True)

    @test
    def after_all_marks_method_correctly(self):
        @after_all
        def teardown_suite():
            pass

        expect(getattr(teardown_suite, "_is_after_all", False)).to_be(True)

    @test
    def suite_collects_before_each_hook(self):
        @suite
        class HookedSuite:
            @before_each
            def setup(self):
                pass

            @test
            def example(self):
                pass

        suites = get_suites()
        expect(suites[0].before_each).not_.to_be_none()

    @test
    def suite_collects_after_each_hook(self):
        @suite
        class HookedSuite:
            @after_each
            def teardown(self):
                pass

            @test
            def example(self):
                pass

        suites = get_suites()
        expect(suites[0].after_each).not_.to_be_none()

    @test
    def suite_collects_before_all_hook(self):
        @suite
        class HookedSuite:
            @before_all
            def setup_suite(self):
                pass

            @test
            def example(self):
                pass

        suites = get_suites()
        expect(suites[0].before_all).not_.to_be_none()

    @test
    def suite_collects_after_all_hook(self):
        @suite
        class HookedSuite:
            @after_all
            def teardown_suite(self):
                pass

            @test
            def example(self):
                pass

        suites = get_suites()
        expect(suites[0].after_all).not_.to_be_none()


@suite
class ClearSuitesTests:
    @test
    def clear_suites_empties_registry(self):
        # First, add some suites
        clear_suites()

        @suite
        class TestA:
            pass

        @suite
        class TestB:
            pass

        expect(get_suites()).to_have_length(2)

        # Now clear and verify
        clear_suites()
        expect(get_suites()).to_be_empty()
