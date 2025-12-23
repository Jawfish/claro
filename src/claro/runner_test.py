"""Tests for the runner module."""

import asyncio

from claro import (
    ExpectationError,
    Suite,
    Test,
    TestStatus,
    TestTimeoutError,
    after_each,
    before_each,
    clear_suites,
    expect,
    get_suites,
    suite,
    test,
)
from claro.decorators import _registry_test_lock
from claro.runner import (
    _has_only_tests,
    collect_all_tests,
    maybe_await,
    run,
    run_single_test,
    timeout_context,
)


@suite
class MaybeAwaitTests:
    @test
    async def sync_function_is_called_and_returns_result(self):
        def sync_fn(x):
            return x * 2

        result = await maybe_await(sync_fn, 5)
        expect(result).to_be(10)

    @test
    async def async_function_is_awaited_and_returns_result(self):
        async def async_fn(x):
            return x * 2

        result = await maybe_await(async_fn, 5)
        expect(result).to_be(10)

    @test
    async def kwargs_are_passed_to_function(self):
        def fn(a, b=0):
            return a + b

        result = await maybe_await(fn, 10, b=5)
        expect(result).to_be(15)

    @test
    async def multiple_args_are_passed_to_function(self):
        def add(a, b, c):
            return a + b + c

        result = await maybe_await(add, 1, 2, 3)
        expect(result).to_be(6)


@suite
class TimeoutContextTests:
    @test
    async def no_timeout_when_none(self):
        """Context manager completes when no timeout is set."""
        completed = False
        async with timeout_context(None):
            await asyncio.sleep(0.01)
            completed = True
        expect(completed).to_be(True)

    @test
    async def operation_completes_before_timeout(self):
        completed = False
        async with timeout_context(1.0):
            await asyncio.sleep(0.001)
            completed = True
        expect(completed).to_be(True)

    @test
    async def slow_operation_raises_test_timeout_error(self):
        raised = False
        try:
            async with timeout_context(0.001):
                await asyncio.sleep(1.0)
        except TestTimeoutError as e:
            raised = True
            expect(e.timeout).to_be(0.001)

        expect(raised).to_be(True)


@suite
class HasOnlyTestsTests:
    @test
    def suite_with_only_test_is_detected(self):
        t = Test(name="focused", fn=lambda: None, only=True)
        s = Suite(name="FocusedSuite", cls=object, tests=[t])
        expect(_has_only_tests(s)).to_be(True)

    @test
    def suite_without_only_tests_is_not_flagged(self):
        t = Test(name="normal", fn=lambda: None, only=False)
        s = Suite(name="NormalSuite", cls=object, tests=[t])
        expect(_has_only_tests(s)).to_be(False)

    @test
    def nested_suite_with_only_test_is_detected(self):
        child_test = Test(name="focused", fn=lambda: None, only=True)
        child = Suite(name="Child", cls=object, tests=[child_test])
        parent = Suite(name="Parent", cls=object, tests=[], children=[child])
        expect(_has_only_tests(parent)).to_be(True)

    @test
    def deeply_nested_only_test_is_detected(self):
        deep_test = Test(name="deep_only", fn=lambda: None, only=True)
        grandchild = Suite(name="Grandchild", cls=object, tests=[deep_test])
        child = Suite(name="Child", cls=object, tests=[], children=[grandchild])
        parent = Suite(name="Parent", cls=object, tests=[], children=[child])
        expect(_has_only_tests(parent)).to_be(True)

    @test
    def empty_suite_has_no_only_tests(self):
        s = Suite(name="Empty", cls=object, tests=[], children=[])
        expect(_has_only_tests(s)).to_be(False)


@suite
class CollectAllTestsTests:
    @test
    def collects_all_tests_from_single_suite(self):
        t1 = Test(name="test1", fn=lambda: None)
        t2 = Test(name="test2", fn=lambda: None)
        s = Suite(name="TestSuite", cls=object, tests=[t1, t2])

        result = list(collect_all_tests([s], only_mode=False))
        expect(len(result)).to_be(1)
        expect(result[0][0].name).to_be("TestSuite")
        expect(len(result[0][1])).to_be(2)

    @test
    def filters_to_only_tests_when_only_mode_is_enabled(self):
        normal = Test(name="normal", fn=lambda: None, only=False)
        focused = Test(name="focused", fn=lambda: None, only=True)
        s = Suite(name="Mixed", cls=object, tests=[normal, focused])

        result = list(collect_all_tests([s], only_mode=True))
        expect(len(result)).to_be(1)
        expect(len(result[0][1])).to_be(1)
        expect(result[0][1][0].name).to_be("focused")

    @test
    def excludes_suite_with_no_only_tests_in_only_mode(self):
        t = Test(name="normal", fn=lambda: None, only=False)
        s = Suite(name="NoOnly", cls=object, tests=[t])

        result = list(collect_all_tests([s], only_mode=True))
        expect(len(result)).to_be(0)

    @test
    def collects_tests_from_nested_suites(self):
        child_test = Test(name="child_test", fn=lambda: None)
        child = Suite(name="Child", cls=object, tests=[child_test])
        parent_test = Test(name="parent_test", fn=lambda: None)
        parent = Suite(name="Parent", cls=object, tests=[parent_test], children=[child])

        result = list(collect_all_tests([parent], only_mode=False))
        expect(len(result)).to_be(2)
        expect(result[0][0].name).to_be("Parent")
        expect(result[1][0].name).to_be("Child")

    @test
    def empty_suite_is_excluded(self):
        s = Suite(name="Empty", cls=object, tests=[])
        result = list(collect_all_tests([s], only_mode=False))
        expect(len(result)).to_be(0)


@suite
class RunSingleTestTests:
    @before_each
    def setup(self):
        clear_suites()

    @test
    async def passing_test_returns_passed_status(self):
        def passing(self):
            pass

        t = Test(name="passing", fn=passing)
        s = Suite(name="S", cls=type("S", (), {"passing": passing}))

        result = await run_single_test(s, t, {})
        expect(result.status).to_be(TestStatus.PASSED)
        expect(result.test_name).to_be("passing")

    @test
    async def failing_test_returns_failed_status(self):
        def failing(self):
            raise ExpectationError("expected failure")

        t = Test(name="failing", fn=failing)
        s = Suite(name="S", cls=type("S", (), {"failing": failing}))

        result = await run_single_test(s, t, {})
        expect(result.status).to_be(TestStatus.FAILED)
        expect(result.error).to_contain("expected failure")

    @test
    async def skipped_test_returns_skipped_status(self):
        t = Test(name="skipped", fn=lambda: None, skip=True)
        s = Suite(name="S", cls=type("S", (), {}))

        result = await run_single_test(s, t, {})
        expect(result.status).to_be(TestStatus.SKIPPED)

    @test
    async def todo_test_returns_todo_status(self):
        t = Test(name="todo", fn=lambda: None, todo=True)
        s = Suite(name="S", cls=type("S", (), {}))

        result = await run_single_test(s, t, {})
        expect(result.status).to_be(TestStatus.TODO)

    @test
    async def test_with_params_receives_tuple_args(self):
        received = []

        def parametrized(self, a, b):
            received.extend([a, b])

        t = Test(name="param", fn=parametrized, params=(1, 2))
        s = Suite(name="S", cls=type("S", (), {"param": parametrized}))

        result = await run_single_test(s, t, {})
        expect(result.status).to_be(TestStatus.PASSED)
        expect(received).to_be([1, 2])

    @test
    async def test_with_dict_params_receives_kwargs(self):
        received = {}

        def parametrized(self, x=0, y=0):
            received["x"] = x
            received["y"] = y

        t = Test(name="param", fn=parametrized, params={"x": 10, "y": 20})
        s = Suite(name="S", cls=type("S", (), {"param": parametrized}))

        result = await run_single_test(s, t, {})
        expect(result.status).to_be(TestStatus.PASSED)
        expect(received).to_be({"x": 10, "y": 20})

    @test
    async def before_each_is_called_before_test(self):
        call_order = []

        def before_each_fn(self):
            call_order.append("before")

        def test_fn(self):
            call_order.append("test")

        t = Test(name="t", fn=test_fn)
        s = Suite(
            name="S",
            cls=type("S", (), {"before_each": before_each_fn, "test_fn": test_fn}),
            before_each=before_each_fn,
        )

        await run_single_test(s, t, {})
        expect(call_order).to_be(["before", "test"])

    @test
    async def after_each_is_called_after_test(self):
        call_order = []

        def after_each_fn(self):
            call_order.append("after")

        def test_fn(self):
            call_order.append("test")

        t = Test(name="t", fn=test_fn)
        s = Suite(
            name="S",
            cls=type("S", (), {"after_each": after_each_fn, "test_fn": test_fn}),
            after_each=after_each_fn,
        )

        await run_single_test(s, t, {})
        expect(call_order).to_be(["test", "after"])

    @test
    async def after_each_runs_even_when_test_fails(self):
        after_called = []

        def after_each_fn(self):
            after_called.append(True)

        def failing_test(self):
            raise ExpectationError("fail")

        t = Test(name="t", fn=failing_test)
        s = Suite(
            name="S",
            cls=type("S", (), {"after_each": after_each_fn, "test_fn": failing_test}),
            after_each=after_each_fn,
        )

        result = await run_single_test(s, t, {})
        expect(result.status).to_be(TestStatus.FAILED)
        expect(after_called).to_be([True])


@suite(sequential=True)
class RunIntegrationTests:
    @before_each
    def setup(self):
        _registry_test_lock.acquire()
        clear_suites()

    @after_each
    def teardown(self):
        clear_suites()
        _registry_test_lock.release()

    @test
    def empty_suites_returns_success(self):
        result = run([], timeout=1.0)
        expect(result).to_be(True)

    @test
    def passing_tests_return_success(self):
        @suite
        class PassingTests:
            @test
            def passes(self):
                expect(1).to_be(1)

        suites = get_suites()
        result = run(suites, timeout=5.0)
        expect(result).to_be(True)

    @test
    def failing_test_returns_failure(self):
        @suite
        class FailingTests:
            @test
            def fails(self):
                expect(1).to_be(2)

        suites = get_suites()
        result = run(suites, timeout=5.0)
        expect(result).to_be(False)

    @test
    def only_mode_runs_focused_tests_exclusively(self):
        executed = []

        @suite
        class MixedTests:
            @test.only
            def focused(self):
                executed.append("focused")

            @test
            def normal(self):
                executed.append("normal")

        suites = get_suites()
        run(suites, timeout=5.0)
        expect(executed).to_be(["focused"])

    @test
    def skipped_tests_are_not_executed(self):
        executed = []

        @suite
        class SkipTests:
            @test.skip
            def skipped(self):
                executed.append("skipped")

            @test
            def runs(self):
                executed.append("runs")

        suites = get_suites()
        run(suites, timeout=5.0)
        expect(executed).to_be(["runs"])

    @test
    def before_all_runs_once_per_suite(self):
        before_all_calls = []

        def before_all_fn(ctx):
            before_all_calls.append("before_all")

        def test1_fn(self):
            pass

        def test2_fn(self):
            pass

        # Create suite manually to avoid global registry pollution
        s = Suite(
            name="BeforeAllTests",
            cls=type("BeforeAllTests", (), {}),
            tests=[
                Test(name="test1", fn=test1_fn),
                Test(name="test2", fn=test2_fn),
            ],
            before_all=before_all_fn,
        )

        run([s], timeout=5.0)
        expect(len(before_all_calls)).to_be(1)
