"""Tests for the runner module."""

import asyncio

from claro import (
    ExpectationError,
    Suite,
    Test,
    TestStatus,
    TestTimeoutError,
    before_each,
    clear_suites,
    expect,
    suite,
    test,
)
from claro.runner import (
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


@suite
class RunIntegrationTests:
    """Integration tests for runner.run() - uses subprocess since run() calls asyncio.run()."""

    @test
    def empty_suites_returns_success(self):
        result = run([], timeout=1.0)
        expect(result).to_be(True)
