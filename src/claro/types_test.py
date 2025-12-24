"""Tests for claro.types module."""

from claro import expect, suite, test
from claro.types import (
    MISSING,
    ExpectationError,
    Suite,
    Test,
    TestResult,
    TestStatus,
    TestTimeoutError,
    _Missing,
)


@suite
class MissingSentinelTests:
    """Tests for the MISSING sentinel value."""

    @test
    def missing_repr_shows_descriptive_string(self) -> None:
        expect(repr(MISSING)).to_be("<MISSING>")

    @test
    def missing_is_singleton_instance(self) -> None:
        expect(MISSING).to_be_instance_of(_Missing)

    @test
    def new_missing_instances_are_distinct(self) -> None:
        other = _Missing()
        expect(MISSING).not_.to_be(other)


@suite
class TestStatusEnumTests:
    """Tests for TestStatus enum."""

    @test
    def all_status_values_exist(self) -> None:
        expect(TestStatus.PASSED).to_be_instance_of(TestStatus)
        expect(TestStatus.FAILED).to_be_instance_of(TestStatus)
        expect(TestStatus.SKIPPED).to_be_instance_of(TestStatus)

    @test
    def status_values_are_distinct(self) -> None:
        statuses = [
            TestStatus.PASSED,
            TestStatus.FAILED,
            TestStatus.SKIPPED,
        ]
        unique_values = {s.value for s in statuses}
        expect(len(unique_values)).to_be(3)


@suite
class TestDataclassTests:
    """Tests for Test dataclass."""

    @test
    def test_requires_name_and_fn(self) -> None:
        def dummy() -> None:
            pass

        t = Test(name="example", fn=dummy)
        expect(t.name).to_be("example")
        expect(t.fn).to_be(dummy)

    @test
    def test_has_false_defaults_for_modifiers(self) -> None:
        t = Test(name="example", fn=lambda: None)
        expect(t.skip).to_be(False)

    @test
    def test_has_none_defaults_for_optional_fields(self) -> None:
        t = Test(name="example", fn=lambda: None)
        expect(t.skip_reason).to_be(None)
        expect(t.timeout).to_be(None)
        expect(t.params).to_be(None)
        expect(t.param_id).to_be(None)

    @test
    def test_accepts_all_optional_fields(self) -> None:
        t = Test(
            name="example",
            fn=lambda: None,
            skip=True,
            skip_reason="not ready",
            timeout=5.0,
            params=(1, 2, 3),
            param_id="case_1",
        )
        expect(t.skip).to_be(True)
        expect(t.skip_reason).to_be("not ready")
        expect(t.timeout).to_be(5.0)
        expect(t.params).to_be((1, 2, 3))
        expect(t.param_id).to_be("case_1")


@suite
class SuiteDataclassTests:
    """Tests for Suite dataclass."""

    @test
    def suite_requires_name_and_cls(self) -> None:
        class DummySuite:
            pass

        s = Suite(name="MySuite", cls=DummySuite)
        expect(s.name).to_be("MySuite")
        expect(s.cls).to_be(DummySuite)

    @test
    def suite_has_empty_list_defaults(self) -> None:
        class DummySuite:
            pass

        s = Suite(name="MySuite", cls=DummySuite)
        expect(s.tests).to_be([])

    @test
    def suite_has_none_defaults_for_lifecycle_hooks(self) -> None:
        class DummySuite:
            pass

        s = Suite(name="MySuite", cls=DummySuite)
        expect(s.before_each).to_be(None)
        expect(s.after_each).to_be(None)
        expect(s.before_all).to_be(None)
        expect(s.after_all).to_be(None)

    @test
    def suite_has_none_default_for_timeout(self) -> None:
        class DummySuite:
            pass

        s = Suite(name="MySuite", cls=DummySuite)
        expect(s.timeout).to_be(None)


@suite
class TestResultDataclassTests:
    """Tests for TestResult dataclass."""

    @test
    def result_requires_suite_name_test_name_and_status(self) -> None:
        r = TestResult(
            suite_name="MySuite", test_name="my_test", status=TestStatus.PASSED
        )
        expect(r.suite_name).to_be("MySuite")
        expect(r.test_name).to_be("my_test")
        expect(r.status).to_be(TestStatus.PASSED)

    @test
    def result_has_zero_duration_by_default(self) -> None:
        r = TestResult(
            suite_name="MySuite", test_name="my_test", status=TestStatus.PASSED
        )
        expect(r.duration_ms).to_be(0)

    @test
    def result_has_none_error_by_default(self) -> None:
        r = TestResult(
            suite_name="MySuite", test_name="my_test", status=TestStatus.PASSED
        )
        expect(r.error).to_be(None)

    @test
    def result_has_missing_sentinel_for_expected_and_actual_by_default(self) -> None:
        r = TestResult(
            suite_name="MySuite", test_name="my_test", status=TestStatus.PASSED
        )
        expect(r.expected).to_be(MISSING)
        expect(r.actual).to_be(MISSING)

    @test
    def result_has_show_diff_true_by_default(self) -> None:
        r = TestResult(
            suite_name="MySuite", test_name="my_test", status=TestStatus.PASSED
        )
        expect(r.show_diff).to_be(True)


@suite
class ExpectationErrorTests:
    """Tests for ExpectationError exception."""

    @test
    def error_stores_message(self) -> None:
        err = ExpectationError("something went wrong")
        expect(str(err)).to_be("something went wrong")

    @test
    def error_stores_expected_and_actual_values(self) -> None:
        err = ExpectationError("mismatch", expected=42, actual=43)
        expect(err.expected).to_be(42)
        expect(err.actual).to_be(43)

    @test
    def error_has_missing_sentinel_for_expected_and_actual_by_default(self) -> None:
        err = ExpectationError("generic error")
        expect(err.expected).to_be(MISSING)
        expect(err.actual).to_be(MISSING)

    @test
    def error_has_show_diff_true_by_default(self) -> None:
        err = ExpectationError("mismatch")
        expect(err.show_diff).to_be(True)

    @test
    def error_accepts_show_diff_false(self) -> None:
        err = ExpectationError("mismatch", show_diff=False)
        expect(err.show_diff).to_be(False)

    @test
    def error_is_assertion_error_subclass(self) -> None:
        err = ExpectationError("mismatch")
        expect(err).to_be_instance_of(AssertionError)


@suite
class TestTimeoutErrorTests:
    """Tests for TestTimeoutError exception."""

    @test
    def timeout_error_stores_timeout_value(self) -> None:
        err = TestTimeoutError(5.0)
        expect(err.timeout).to_be(5.0)

    @test
    def timeout_error_has_descriptive_message(self) -> None:
        err = TestTimeoutError(3.5)
        expect(str(err)).to_be("Test timed out after 3.5s")

    @test
    def timeout_error_is_exception_subclass(self) -> None:
        err = TestTimeoutError(1.0)
        expect(err).to_be_instance_of(Exception)
