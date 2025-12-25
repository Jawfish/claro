"""Tests for the fixtures module."""

from collections.abc import AsyncGenerator, Generator
from typing import Annotated

from claro import (
    Inject,
    before_each,
    clear_fixtures,
    expect,
    fixture,
    get_fixtures,
    suite,
    test,
)
from claro.fixtures import (
    FixtureDef,
    FixtureError,
    get_injectable_params,
    is_inject_annotation,
)


@suite
class FixtureRegistrationTests:
    @before_each
    def reset_registry(self):
        clear_fixtures()

    @test
    def fixture_is_registered_by_return_type(self):
        class Database:
            pass

        @fixture
        def database() -> Database:
            return Database()

        fixtures = get_fixtures()
        expect(fixtures).to_have_length(1)
        expect(Database in fixtures).to_be(True)
        expect(fixtures[Database].return_type).to_be(Database)

    @test
    def fixture_stores_the_function(self):
        class Service:
            pass

        @fixture
        def service() -> Service:
            return Service()

        fixtures = get_fixtures()
        expect(fixtures[Service].fn).to_be(service)

    @test
    def fixture_without_return_type_raises_type_error(self):
        def register_invalid():
            @fixture
            def invalid_fixture():
                return "no type annotation"

        expect(register_invalid).to_raise(TypeError)

    @test
    def duplicate_fixture_for_same_type_raises_type_error(self):
        class Database:
            pass

        @fixture
        def first_db() -> Database:
            return Database()

        def register_duplicate():
            @fixture
            def second_db() -> Database:
                return Database()

        expect(register_duplicate).to_raise(TypeError)

    @test
    def fixture_defaults_to_test_scope(self):
        class Config:
            pass

        @fixture
        def config() -> Config:
            return Config()

        fixtures = get_fixtures()
        expect(fixtures[Config].scope).to_be("test")

    @test
    def fixture_with_suite_scope_is_registered(self):
        class SharedResource:
            pass

        @fixture(scope="suite")
        def shared_resource() -> SharedResource:
            return SharedResource()

        fixtures = get_fixtures()
        expect(fixtures[SharedResource].scope).to_be("suite")

    @test
    def fixture_with_session_scope_is_registered(self):
        class GlobalConfig:
            pass

        @fixture(scope="session")
        def global_config() -> GlobalConfig:
            return GlobalConfig()

        fixtures = get_fixtures()
        expect(fixtures[GlobalConfig].scope).to_be("session")


@suite
class GeneratorFixtureTests:
    @before_each
    def reset_registry(self):
        clear_fixtures()

    @test
    def sync_generator_fixture_is_detected(self):
        class Connection:
            pass

        @fixture
        def connection() -> Generator[Connection, None, None]:
            conn = Connection()
            yield conn

        fixtures = get_fixtures()
        expect(fixtures[Connection].is_generator).to_be(True)

    @test
    def async_generator_fixture_is_detected(self):
        class AsyncConnection:
            pass

        @fixture
        async def async_connection() -> AsyncGenerator[AsyncConnection, None]:
            conn = AsyncConnection()
            yield conn

        fixtures = get_fixtures()
        expect(fixtures[AsyncConnection].is_generator).to_be(True)

    @test
    def regular_fixture_is_not_generator(self):
        class SimpleValue:
            pass

        @fixture
        def simple_value() -> SimpleValue:
            return SimpleValue()

        fixtures = get_fixtures()
        expect(fixtures[SimpleValue].is_generator).to_be(False)

    @test
    def generator_return_type_extracts_inner_type(self):
        class Resource:
            pass

        @fixture
        def resource() -> Generator[Resource, None, None]:
            yield Resource()

        fixtures = get_fixtures()
        expect(Resource in fixtures).to_be(True)
        expect(fixtures[Resource].return_type).to_be(Resource)


@suite
class RegistryManagementTests:
    @before_each
    def reset_registry(self):
        clear_fixtures()

    @test
    def clear_fixtures_empties_registry(self):
        class TempFixture:
            pass

        @fixture
        def temp_fixture() -> TempFixture:
            return TempFixture()

        expect(get_fixtures()).to_have_length(1)
        clear_fixtures()
        expect(get_fixtures()).to_be_empty()

    @test
    def get_fixtures_returns_copy_of_registry(self):
        class Original:
            pass

        @fixture
        def original() -> Original:
            return Original()

        fixtures_copy = get_fixtures()
        fixtures_copy.clear()

        # Original registry should be unaffected
        expect(get_fixtures()).to_have_length(1)


@suite
class InjectAnnotationTests:
    @test
    def is_inject_annotation_recognizes_annotated_inject(self):
        hint = Annotated[str, Inject]
        is_injectable, inner_type = is_inject_annotation(hint)

        expect(is_injectable).to_be(True)
        expect(inner_type).to_be(str)

    @test
    def is_inject_annotation_returns_false_for_plain_type(self):
        is_injectable, inner_type = is_inject_annotation(str)

        expect(is_injectable).to_be(False)
        expect(inner_type).to_be_none()

    @test
    def is_inject_annotation_returns_false_for_annotated_without_inject(self):
        hint = Annotated[str, "some other marker"]
        is_injectable, inner_type = is_inject_annotation(hint)

        expect(is_injectable).to_be(False)
        expect(inner_type).to_be_none()

    @test
    def is_inject_annotation_returns_false_for_none(self):
        is_injectable, inner_type = is_inject_annotation(None)

        expect(is_injectable).to_be(False)
        expect(inner_type).to_be_none()

    @test
    def is_inject_annotation_extracts_custom_class_type(self):
        class CustomService:
            pass

        hint = Annotated[CustomService, Inject]
        is_injectable, inner_type = is_inject_annotation(hint)

        expect(is_injectable).to_be(True)
        expect(inner_type).to_be(CustomService)


@suite
class GetInjectableParamsTests:
    @test
    def extracts_single_injectable_param(self):
        class Database:
            pass

        def test_fn(db: Annotated[Database, Inject]):
            pass

        params = get_injectable_params(test_fn)

        expect(params).to_have_length(1)
        expect("db" in params).to_be(True)
        expect(params["db"]).to_be(Database)

    @test
    def extracts_multiple_injectable_params(self):
        class Database:
            pass

        class Cache:
            pass

        def test_fn(db: Annotated[Database, Inject], cache: Annotated[Cache, Inject]):
            pass

        params = get_injectable_params(test_fn)

        expect(params).to_have_length(2)
        expect(params["db"]).to_be(Database)
        expect(params["cache"]).to_be(Cache)

    @test
    def ignores_non_injectable_params(self):
        class Database:
            pass

        def test_fn(self, db: Annotated[Database, Inject], regular_arg: str):
            pass

        params = get_injectable_params(test_fn)

        expect(params).to_have_length(1)
        expect("db" in params).to_be(True)
        expect("self" in params).to_be(False)
        expect("regular_arg" in params).to_be(False)

    @test
    def returns_empty_dict_for_function_without_injectables(self):
        def test_fn(a: int, b: str):
            pass

        params = get_injectable_params(test_fn)

        expect(params).to_be_empty()

    @test
    def returns_empty_dict_for_function_without_annotations(self):
        def test_fn(a, b):
            pass

        params = get_injectable_params(test_fn)

        expect(params).to_be_empty()

    @test
    def excludes_return_type_from_injectable_params(self):
        class Database:
            pass

        def test_fn(db: Annotated[Database, Inject]) -> str:
            return "result"

        params = get_injectable_params(test_fn)

        expect(params).to_have_length(1)
        expect("return" in params).to_be(False)


@suite
class FixtureDefTests:
    @test
    def fixture_def_stores_all_properties(self):
        class Service:
            pass

        def service_fn() -> Service:
            return Service()

        fixture_def = FixtureDef(
            fn=service_fn,
            return_type=Service,
            scope="suite",
            is_generator=False,
        )

        expect(fixture_def.fn).to_be(service_fn)
        expect(fixture_def.return_type).to_be(Service)
        expect(fixture_def.scope).to_be("suite")
        expect(fixture_def.is_generator).to_be(False)


@suite
class FixtureErrorTests:
    @test
    def fixture_error_is_exception_subclass(self):
        error = FixtureError("fixture not found")

        expect(isinstance(error, Exception)).to_be(True)

    @test
    def fixture_error_stores_message(self):
        message = "No fixture found for type Database"
        error = FixtureError(message)

        expect(str(error)).to_be(message)
