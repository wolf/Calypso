from pathlib import Path

import pytest

from code_reader.code_reader import get_code_files, CodeSectionRecursionError, NoRootCodeSectionsFoundError, FileIncludeRecursionError


def read_golden_record(path: str):
    with open(path + ".golden-record", "r") as f:
        golden_record = f.read()
    return golden_record


def test_get_roots():
    code_files = get_code_files(Path("tests/data/test-get-roots.w"))
    golden_record = read_golden_record("tests/data/test-get-roots")
    assert code_files["generated_output"] == golden_record


def test_section_boundaries():
    golden_record = read_golden_record("tests/data/test-section-boundaries")

    code_files = get_code_files(Path("tests/data/test-section-boundary-eof.w"))
    assert code_files["generated_output_eof_test"] == golden_record

    code_files = get_code_files(Path("tests/data/test-section-boundary-doc.w"))
    assert code_files["generated_output_doc_test"] == golden_record

    code_files = get_code_files(Path("tests/data/test-section-boundary-code.w"))
    assert code_files["generated_output_code_test"] == golden_record

    code_files = get_code_files(Path("tests/data/test-section-boundary-include.w"))
    assert code_files["generated_output_code_test"] == golden_record


def test_multiple_root_sections():
    code_files = get_code_files(Path("tests/data/test-multiple-root-sections.w"))

    golden_record = read_golden_record("tests/data/test-multiple-root-sections-A")
    assert code_files["generated_output_A"] == golden_record

    golden_record = read_golden_record("tests/data/test-multiple-root-sections-B")
    assert code_files["generated_output_B"] == golden_record

    golden_record = read_golden_record("tests/data/test-multiple-root-sections-C")
    assert code_files["generated_output_C"] == golden_record


def test_same_named_sections_concatenate():
    code_files = get_code_files(Path("tests/data/test-same-named-sections-concatenate.w"))
    golden_record = read_golden_record("tests/data/test-same-named-sections-concatenate")
    assert code_files["generated_output"] == golden_record


def test_doc_is_ignored():
    code_files = get_code_files(Path("tests/data/test-doc-is-ignored.w"))
    golden_record = read_golden_record("tests/data/test-doc-is-ignored")
    assert code_files["generated_output"] == golden_record


def test_sections_can_include_sections():
    code_files = get_code_files(Path("tests/data/test-sections-can-include-sections.w"))
    golden_record = read_golden_record("tests/data/test-sections-can-include-sections")
    assert code_files["generated_output"] == golden_record


def test_section_names_ignore_surrounding_whitespace():
    code_files = get_code_files(Path("tests/data/test-section-names-ignore-surrounding-whitespace.w"))
    golden_record = read_golden_record("tests/data/test-section-names-ignore-surrounding-whitespace")
    assert code_files["generated_output"] == golden_record


def test_inline_substitution():
    code_files = get_code_files(Path("tests/data/test-inline-substitution.w"))
    golden_record = read_golden_record("tests/data/test-inline-substitution")
    assert code_files["generated_output"] == golden_record


def test_indentation_is_preserved():
    code_files = get_code_files(Path("tests/data/test-indentation-is-preserved.w"))
    golden_record = read_golden_record("tests/data/test-indentation-is-preserved")
    assert code_files["generated_output"] == golden_record


def test_newlines_are_trimmed_at_eof():
    code_files = get_code_files(Path("tests/data/test-root-ends-with-the-right-number-of-newlines.w"))
    golden_record = read_golden_record("tests/data/test-root-ends-with-the-right-number-of-newlines")
    assert code_files["generated_output"] == golden_record


def test_newlines_are_preserved_between_section_pieces():
    code_files = get_code_files(Path("tests/data/test-newlines-are-preserved-between-section-pieces.w"))
    golden_record = read_golden_record("tests/data/test-newlines-are-preserved-between-section-pieces")
    assert code_files["generated_output"] == golden_record


def test_include_files():
    code_files = get_code_files(Path("tests/data/test-include-files.w"))
    golden_record = read_golden_record("tests/data/test-include-files")
    assert code_files["generated_output"] == golden_record


def test_nested_include_files():
    code_files = get_code_files(Path("tests/data/test-nested-include-files.w"))
    golden_record = read_golden_record("tests/data/test-nested-include-files")
    assert code_files["generated_output"] == golden_record


def test_recursive_include_files_fail():
    with pytest.raises(FileIncludeRecursionError):
        get_code_files(Path("tests/data/test-recursive-include-files-fail.w"))


def test_recursive_sections_fail():
    with pytest.raises(CodeSectionRecursionError):
        get_code_files(Path("tests/data/test-recursive-sections-fail.w"))
    with pytest.raises(NoRootCodeSectionsFoundError):
        get_code_files(Path("tests/data/test-no-roots-means-recursion.w"))
