from pathlib import Path

import pytest

from blue import db_gateway, errors, scanner


@pytest.fixture()
def shared_context():
    class MockContext:
        def __init__(self):
            self.obj = dict()

    return MockContext()


@pytest.fixture()
def db(shared_context):
    return db_gateway.create_database(shared_context, ":memory:")


def read_golden_record(path: str):
    with open(path + ".golden-record", "r") as f:
        golden_record = f.read()
    return golden_record


# TODO: test no code-sections found fails
# TODO: test case insensitive code-section names match
# TODO: test first unabbreviated version of a name is the canonical case, can't possibly work!!!


def test_get_roots(shared_context):
    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-get-roots.w"))
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output"] == read_golden_record("tests/data/test-get-roots")


def test_section_boundaries(shared_context):
    golden_record = read_golden_record("tests/data/test-section-boundaries")

    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-section-boundary-eof.w"))
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output_eof_test"] == golden_record

    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-section-boundary-doc.w"))
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output_doc_test"] == golden_record

    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-section-boundary-code.w"))
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output_code_test"] == golden_record

    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-section-boundary-include.w"))
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output_code_test"] == golden_record


def test_multiple_root_sections(shared_context):
    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-multiple-root-sections.w"))
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output_A"] == read_golden_record("tests/data/test-multiple-root-sections-A")
    assert code_files["generated_output_B"] == read_golden_record("tests/data/test-multiple-root-sections-B")
    assert code_files["generated_output_C"] == read_golden_record("tests/data/test-multiple-root-sections-C")


def test_same_named_sections_concatenate(shared_context):
    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-same-named-sections-concatenate.w"))
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output"] == read_golden_record("tests/data/test-same-named-sections-concatenate")


def test_doc_is_ignored(shared_context):
    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-doc-is-ignored.w"))
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output"] == read_golden_record("tests/data/test-doc-is-ignored")


def test_sections_can_include_sections(shared_context):
    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-sections-can-include-sections.w"))
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output"] == read_golden_record("tests/data/test-sections-can-include-sections")


def test_section_names_ignore_surrounding_whitespace(shared_context):
    scanner.parse_source_file(
        shared_context, ":memory:", Path("tests/data/test-section-names-ignore-surrounding-whitespace.w")
    )
    code_files = scanner.get_code_files(shared_context)
    golden_record = read_golden_record("tests/data/test-section-names-ignore-surrounding-whitespace")
    assert code_files["generated_output"] == golden_record


def test_inline_substitution(shared_context):
    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-inline-substitution.w"))
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output"] == read_golden_record("tests/data/test-inline-substitution")


def test_consecutive_section_includes(shared_context):
    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-consecutive-section-includes.w"))
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output"] == read_golden_record("tests/data/test-consecutive-section-includes")


def test_indentation_is_preserved(shared_context):
    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-indentation-is-preserved.w"))
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output"] == read_golden_record("tests/data/test-indentation-is-preserved")


def test_newlines_are_trimmed_at_eof(shared_context):
    scanner.parse_source_file(
        shared_context, ":memory:", Path("tests/data/test-root-ends-with-the-right-number-of-newlines.w")
    )
    code_files = scanner.get_code_files(shared_context)
    golden_record = read_golden_record("tests/data/test-root-ends-with-the-right-number-of-newlines")
    assert code_files["generated_output"] == golden_record


def test_last_character_preserved_when_file_does_not_end_with_newline(shared_context):
    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-last-character-preserved.w"))
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output"] == read_golden_record("tests/data/test-last-character-preserved")


def test_newlines_are_preserved_between_section_pieces(shared_context):
    scanner.parse_source_file(
        shared_context, ":memory:", Path("tests/data/test-newlines-are-preserved-between-section-pieces.w")
    )
    code_files = scanner.get_code_files(shared_context)
    golden_record = read_golden_record("tests/data/test-newlines-are-preserved-between-section-pieces")
    assert code_files["generated_output"] == golden_record


def test_include_files(shared_context):
    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-include-files.w"))
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output"] == read_golden_record("tests/data/test-nested-include-files")


def test_nested_include_files(shared_context):
    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-nested-include-files.w"))
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output"] == read_golden_record("tests/data/test-nested-include-files")


def test_included_section_name_is_abbreviated(shared_context):
    scanner.parse_source_file(
        shared_context, ":memory:", Path("tests/data/test-included-section-name-is-abbreviated.w")
    )
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output"] == read_golden_record("tests/data/test-included-section-name-is-abbreviated")


def test_only_code_sections_are_assigned_presentation_numbers(shared_context):
    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-code-section-sequence-numbers.w"))
    db = db_gateway.get_database_connection(shared_context)
    count_document_sections_with_presentation_numbers = """
        SELECT count(*) AS count
        FROM document_section
        JOIN document_section_kind ON document_section_kind.id = document_section.kind_id
        WHERE document_section_kind.description = 'documentation'
            AND document_section.code_section_presentation_number IS NOT NULL
    """
    with db_gateway.open_cursor(db) as section_reader:
        section_reader.execute(count_document_sections_with_presentation_numbers)
        assert section_reader.fetchone()["count"] == 0


def test_all_code_sections_are_assigned_presentation_numbers(shared_context):
    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-code-section-sequence-numbers.w"))
    db = db_gateway.get_database_connection(shared_context)
    count_code_sections_without_presentation_numbers = """
        SELECT count(*) AS count
        FROM document_section
        JOIN document_section_kind ON document_section_kind.id = document_section.kind_id
        WHERE document_section_kind.description = 'code'
            AND document_section.code_section_presentation_number IS NULL
    """
    with db_gateway.open_cursor(db) as section_reader:
        section_reader.execute(count_code_sections_without_presentation_numbers)
        assert section_reader.fetchone()["count"] == 0


def test_presentation_numbers_are_in_order(shared_context):
    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-code-section-sequence-numbers.w"))
    db = db_gateway.get_database_connection(shared_context)
    find_code_sections = """
        SELECT document_section.id, code_section_presentation_number
        FROM document_section
        JOIN document_section_kind ON document_section_kind.id = document_section.kind_id
        WHERE document_section_kind.description = 'code'
        ORDER BY document_section.id
    """
    with db_gateway.open_cursor(db) as code_section_reader:
        code_section_reader.execute(find_code_sections)
        required_presentation_number = 1
        for row in code_section_reader.fetchall():
            assert row["code_section_presentation_number"] == required_presentation_number
            required_presentation_number += 1


def test_section_definition_is_abbreviated_but_included_section_is_not(shared_context):
    scanner.parse_source_file(
        shared_context,
        ":memory:",
        Path("tests/data/test-section-definition-is-abbreviated-but-included-section-is-not.w"),
    )
    code_files = scanner.get_code_files(shared_context)
    assert code_files["generated_output"] == read_golden_record("tests/data/test-included-section-name-is-abbreviated")


def test_empty_definition_is_ok(shared_context):
    # should not raise errors.NoSuchCodeSectionError
    scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-empty-definition-is-ok.w"))


def test_non_unique_abbreviation_fails(shared_context):
    with pytest.raises(errors.NonUniqueAbbreviationError):
        scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-non-unique-abbreviation-fails.w"))


def test_bad_section_names_fail(shared_context):
    with pytest.raises(errors.BadSectionNameError):
        scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-bad-section-names-fail.w"))
    with pytest.raises(errors.BadSectionNameError):
        scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-empty-section-name-fails.w"))


def test_bad_reference_names_fail(shared_context):
    with pytest.raises(errors.BadSectionNameError):
        scanner.parse_source_file(
            shared_context, ":memory:", Path("tests/data/test-reference-with-bad-pattern-fails.w")
        )


def test_section_name_not_found_fails(shared_context):
    with pytest.raises(errors.NoSuchCodeSectionError):
        scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-section-name-not-found-fails.w"))


def test_recursive_include_files_fail(shared_context):
    with pytest.raises(errors.FileIncludeRecursionError):
        scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-recursive-include-files-fail.w"))


def test_recursive_sections_fail(shared_context):
    with pytest.raises(errors.CodeSectionRecursionError):
        scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-recursive-sections-fail.w"))
    with pytest.raises(errors.CodeSectionRecursionError):
        scanner.parse_source_file(shared_context, ":memory:", Path("tests/data/test-no-roots-means-recursion.w"))
