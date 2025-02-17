from pathlib import Path

import pytest

from blue import errors
from blue.bootstrap.original_scanner import get_code_files


@pytest.fixture()
def shared_context():
    return dict(obj={})


def read_golden_record(path: str):
    with open(path + ".golden-record", "r") as f:
        golden_record = f.read()
    return golden_record


def test_get_roots(shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-get-roots.w"))
    assert code_files["generated_output"] == read_golden_record("tests/data/test-get-roots")


def test_section_boundaries(shared_context):
    golden_record = read_golden_record("tests/data/test-section-boundaries")

    code_files = get_code_files(shared_context, Path("tests/data/test-section-boundary-eof.w"))
    assert code_files["generated_output_eof_test"] == golden_record

    code_files = get_code_files(shared_context, Path("tests/data/test-section-boundary-doc.w"))
    assert code_files["generated_output_doc_test"] == golden_record

    code_files = get_code_files(shared_context, Path("tests/data/test-section-boundary-code.w"))
    assert code_files["generated_output_code_test"] == golden_record

    code_files = get_code_files(shared_context, Path("tests/data/test-section-boundary-include.w"))
    assert code_files["generated_output_code_test"] == golden_record


def test_multiple_root_sections(shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-multiple-root-sections.w"))
    assert code_files["generated_output_A"] == read_golden_record("tests/data/test-multiple-root-sections-A")
    assert code_files["generated_output_B"] == read_golden_record("tests/data/test-multiple-root-sections-B")
    assert code_files["generated_output_C"] == read_golden_record("tests/data/test-multiple-root-sections-C")


def test_same_named_sections_concatenate(shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-same-named-sections-concatenate.w"))
    assert code_files["generated_output"] == read_golden_record("tests/data/test-same-named-sections-concatenate")


def test_doc_is_ignored(shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-doc-is-ignored.w"))
    assert code_files["generated_output"] == read_golden_record("tests/data/test-doc-is-ignored")


def test_sections_can_include_sections(shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-sections-can-include-sections.w"))
    assert code_files["generated_output"] == read_golden_record("tests/data/test-sections-can-include-sections")


def test_section_names_ignore_surrounding_whitespace(shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-section-names-ignore-surrounding-whitespace.w"))
    golden_record = read_golden_record("tests/data/test-section-names-ignore-surrounding-whitespace")
    assert code_files["generated_output"] == golden_record


def test_inline_substitution(shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-inline-substitution.w"))
    assert code_files["generated_output"] == read_golden_record("tests/data/test-inline-substitution")


def test_consecutive_section_includes(shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-consecutive-section-includes.w"))
    assert code_files["generated_output"] == read_golden_record("tests/data/test-consecutive-section-includes")


def test_escaped_references_are_not_expanded(shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-escaped-references-are-not-expanded.w"))
    assert code_files["generated_output"] == read_golden_record("tests/data/test-escaped-references-are-not-expanded")


def test_indentation_is_preserved(shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-indentation-is-preserved.w"))
    assert code_files["generated_output"] == read_golden_record("tests/data/test-indentation-is-preserved")


def test_newlines_are_trimmed_at_eof(shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-root-ends-with-the-right-number-of-newlines.w"))
    golden_record = read_golden_record("tests/data/test-root-ends-with-the-right-number-of-newlines")
    assert code_files["generated_output"] == golden_record


def test_last_character_preserved_when_file_does_not_end_with_newline(shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-last-character-preserved.w"))
    assert code_files["generated_output"] == read_golden_record("tests/data/test-last-character-preserved")


def test_newlines_are_preserved_between_section_pieces(shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-newlines-are-preserved-between-section-pieces.w"))
    golden_record = read_golden_record("tests/data/test-newlines-are-preserved-between-section-pieces")
    assert code_files["generated_output"] == golden_record


def test_include_files(shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-include-files.w"))
    assert code_files["generated_output"] == read_golden_record("tests/data/test-nested-include-files")


def test_nested_include_files(shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-nested-include-files.w"))
    assert code_files["generated_output"] == read_golden_record("tests/data/test-nested-include-files")


def test_bad_section_names_fail(shared_context):
    with pytest.raises(errors.BadSectionNameError):
        get_code_files(shared_context, Path("tests/data/test-bad-section-names-fail.w"))
    with pytest.raises(errors.BadSectionNameError):
        get_code_files(shared_context, Path("tests/data/test-empty-section-name-fails.w"))


def test_bad_reference_names_fail(shared_context):
    with pytest.raises(errors.BadSectionNameError):
        get_code_files(shared_context, Path("tests/data/test-reference-with-bad-pattern-fails.w"))


def test_section_name_not_found_fails(shared_context):
    with pytest.raises(errors.NoSuchCodeSectionError):
        get_code_files(shared_context, Path("tests/data/test-section-name-not-found-fails.w"))


def test_recursive_include_files_fail(shared_context):
    with pytest.raises(errors.FileIncludeRecursionError):
        get_code_files(shared_context, Path("tests/data/test-recursive-include-files-fail.w"))


def test_recursive_sections_fail(shared_context):
    with pytest.raises(errors.CodeSectionRecursionError):
        get_code_files(shared_context, Path("tests/data/test-recursive-sections-fail.w"))
    with pytest.raises(errors.NoRootCodeSectionsFoundError):
        get_code_files(shared_context, Path("tests/data/test-no-roots-means-recursion.w"))
