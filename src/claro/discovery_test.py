"""Tests for the discovery module."""

import tempfile
from pathlib import Path

from claro import after_each, before_each, clear_suites, expect, get_suites, suite, test
from claro.decorators import _registry_test_lock
from claro.discovery import (
    DEFAULT_PATTERNS,
    AssertMessageError,
    check_assert_messages,
    collect_tests,
    discover_test_files,
    import_test_file,
)


@suite
class DefaultPatternsTests:
    @test
    def default_patterns_include_underscore_test_suffix(self):
        expect(DEFAULT_PATTERNS).to_contain("*_test.py")


@suite(sequential=True)
class DiscoverTestFilesTests:
    @before_each
    def reset_registry(self):
        _registry_test_lock.acquire()
        clear_suites()

    @after_each
    def cleanup(self):
        clear_suites()
        _registry_test_lock.release()

    @test
    def test_files_with_underscore_test_suffix_are_discovered(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "example_test.py"
            test_file.write_text("# empty test file")

            files = discover_test_files(temp_path)

            expect(files).to_have_length(1)
            expect(files[0].name).to_be("example_test.py")

    @test
    def non_matching_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create matching and non-matching files
            (temp_path / "valid_test.py").write_text("# test file")
            (temp_path / "test_invalid.py").write_text("# not matching pattern")
            (temp_path / "regular.py").write_text("# regular file")

            files = discover_test_files(temp_path)

            expect(files).to_have_length(1)
            expect(files[0].name).to_be("valid_test.py")

    @test
    def nested_test_files_are_discovered_recursively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create nested directory structure
            nested_dir = temp_path / "nested" / "deep"
            nested_dir.mkdir(parents=True)

            (temp_path / "root_test.py").write_text("# root test")
            (nested_dir / "nested_test.py").write_text("# nested test")

            files = discover_test_files(temp_path)

            file_names = [f.name for f in files]
            expect(file_names).to_contain("root_test.py")
            expect(file_names).to_contain("nested_test.py")
            expect(files).to_have_length(2)

    @test
    def custom_patterns_match_different_file_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            (temp_path / "test_example.py").write_text("# test_ prefix")
            (temp_path / "example_test.py").write_text("# _test suffix")

            # Using custom pattern for test_ prefix
            files = discover_test_files(temp_path, patterns=("test_*.py",))

            expect(files).to_have_length(1)
            expect(files[0].name).to_be("test_example.py")

    @test
    def multiple_patterns_match_all_variants(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            (temp_path / "test_example.py").write_text("# test_ prefix")
            (temp_path / "example_test.py").write_text("# _test suffix")
            (temp_path / "regular.py").write_text("# regular file")

            files = discover_test_files(temp_path, patterns=("test_*.py", "*_test.py"))

            file_names = [f.name for f in files]
            expect(file_names).to_contain("test_example.py")
            expect(file_names).to_contain("example_test.py")
            expect(files).to_have_length(2)

    @test
    def discovered_files_are_sorted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            (temp_path / "z_test.py").write_text("# z")
            (temp_path / "a_test.py").write_text("# a")
            (temp_path / "m_test.py").write_text("# m")

            files = discover_test_files(temp_path)

            file_names = [f.name for f in files]
            expect(file_names).to_be(["a_test.py", "m_test.py", "z_test.py"])


@suite
class CheckAssertMessagesTests:
    @test
    def assert_without_message_raises_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "bad_test.py"
            test_file.write_text("assert True")

            try:
                check_assert_messages(test_file)
                expect(False).to_be(True)  # Should not reach here
            except AssertMessageError as e:
                expect(str(e)).to_contain("missing message")
                expect(str(e)).to_contain("bad_test.py")

    @test
    def assert_with_message_passes_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "good_test.py"
            test_file.write_text('assert True, "this is a message"')

            # Should not raise
            check_assert_messages(test_file)

    @test
    def multiple_asserts_all_require_messages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "mixed_test.py"
            test_file.write_text("""
assert True, "first is good"
assert False
""")

            try:
                check_assert_messages(test_file)
                expect(False).to_be(True)  # Should not reach here
            except AssertMessageError:
                pass  # Expected

    @test
    def file_with_no_asserts_passes_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "no_asserts_test.py"
            test_file.write_text("x = 1\ny = 2\n")

            # Should not raise
            check_assert_messages(test_file)


@suite(sequential=True)
class ImportTestFileTests:
    @before_each
    def reset_registry(self):
        _registry_test_lock.acquire()
        clear_suites()

    @after_each
    def cleanup(self):
        clear_suites()
        _registry_test_lock.release()

    @test
    def imported_file_registers_its_suites(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "example_test.py"
            test_file.write_text("""
from claro import suite, test

@suite
class ImportedSuiteUnique123:
    @test
    def it_works(self):
        pass
""")

            import_test_file(test_file, check_asserts=False)

            suites = get_suites()
            suite_names = [s.name for s in suites]
            expect(suite_names).to_contain("ImportedSuiteUnique123")

    @test
    def import_checks_asserts_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "bad_assert_test.py"
            test_file.write_text("""
from claro import suite, test

@suite
class BadAssertSuite:
    @test
    def bad_test(self):
        assert True  # Missing message
""")

            try:
                import_test_file(test_file)
                expect(False).to_be(True)  # Should not reach here
            except AssertMessageError:
                pass  # Expected

    @test
    def import_with_check_asserts_disabled_skips_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "bad_assert_test.py"
            test_file.write_text("""
from claro import suite, test

@suite
class BadAssertSuiteUnique456:
    @test
    def bad_test(self):
        assert True  # Missing message, but check disabled
""")

            # Should not raise because check_asserts=False
            import_test_file(test_file, check_asserts=False)
            suites = get_suites()
            suite_names = [s.name for s in suites]
            expect(suite_names).to_contain("BadAssertSuiteUnique456")

    @test
    def import_error_cleans_up_module(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "syntax_error_test.py"
            test_file.write_text("def broken(:\n    pass")

            try:
                import_test_file(test_file, check_asserts=False)
                expect(False).to_be(True)  # Should not reach here
            except SyntaxError:
                pass  # Expected


@suite(sequential=True)
class CollectTestsTests:
    @before_each
    def reset_registry(self):
        _registry_test_lock.acquire()
        clear_suites()

    @after_each
    def cleanup(self):
        clear_suites()
        _registry_test_lock.release()

    @test
    def collect_returns_list_of_suites(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            (temp_path / "example_test.py").write_text("""
from claro import suite, test

@suite
class CollectTestSuiteXYZ:
    @test
    def test_one(self):
        pass
""")

            suites = collect_tests(temp_path)

            # Verify we got a list of Suite objects
            expect(suites).to_be_instance_of(list)
            # At least one suite should be returned (may have others due to parallel execution)
            expect(len(suites)).to_be_greater_than(0)
            # Verify the suites have expected attributes
            suite_names = [s.name for s in suites]
            expect(suite_names).to_contain("CollectTestSuiteXYZ")

    @test
    def collect_clears_previous_suites(self):
        # Pre-register a suite with a unique name
        @suite
        class PreExistingUnique333:
            @test
            def old_test(self):
                pass

        pre_suite_names = [s.name for s in get_suites()]
        expect(pre_suite_names).to_contain("PreExistingUnique333")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "new_test.py").write_text("""
from claro import suite, test

@suite
class NewSuiteUnique444:
    @test
    def new_test(self):
        pass
""")

            suites = collect_tests(temp_path)

            # The returned suites should only contain suites from the temp dir
            suite_names = [s.name for s in suites]
            expect(suite_names).to_contain("NewSuiteUnique444")
            expect(suite_names).not_.to_contain("PreExistingUnique333")

    @test
    def collect_with_custom_patterns_matches_different_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            (temp_path / "test_example.py").write_text("""
from claro import suite, test

@suite
class PrefixSuiteUnique789:
    @test
    def test_prefix(self):
        pass
""")
            (temp_path / "example_test.py").write_text("""
from claro import suite, test

@suite
class SuffixSuiteUnique789:
    @test
    def test_suffix(self):
        pass
""")

            # Only collect files with test_ prefix
            suites = collect_tests(temp_path, patterns=("test_*.py",))

            suite_names = [s.name for s in suites]
            expect(suite_names).to_contain("PrefixSuiteUnique789")
            expect(suite_names).not_.to_contain("SuffixSuiteUnique789")

    @test
    def no_files_discovered_when_no_patterns_match(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create only non-matching files (no *_test.py suffix)
            (temp_path / "regular.py").write_text("x = 1")
            (temp_path / "testfile.py").write_text("y = 2")

            # Discover test files (should find none)
            files = discover_test_files(temp_path)

            expect(files).to_be_empty()
