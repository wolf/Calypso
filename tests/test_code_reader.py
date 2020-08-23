from pathlib import Path

import pytest

from code_reader.code_reader import get_code_files, CodeSectionRecursionError, NoRootCodeSectionsFound


def test_get_roots():
    code_files = get_code_files(Path("tests/data/test-get-roots.w"))
    with open("tests/data/test-get-roots.golden-record", "r") as f:
        golden_record = f.read()
    assert code_files["generated_output"] == golden_record


def test_section_boundaries():
    with open("tests/data/test-section-boundaries.golden-record", "r") as f:
        golden_record = f.read()

    code_files = get_code_files(Path("tests/data/test-section-boundary-eof.w"))
    assert code_files["generated_output_eof_test"] == golden_record

    code_files = get_code_files(Path("tests/data/test-section-boundary-doc.w"))
    assert code_files["generated_output_doc_test"] == golden_record

    code_files = get_code_files(Path("tests/data/test-section-boundary-code.w"))
    assert code_files["generated_output_code_test"] == golden_record


def test_multiple_root_sections():
    code_files = get_code_files(Path("tests/data/test-multiple-root-sections.w"))

    with open("tests/data/test-multiple-root-sections-A.golden-record", "r") as f:
        golden_record = f.read()
    assert code_files["generated_output_A"] == golden_record

    with open("tests/data/test-multiple-root-sections-B.golden-record", "r") as f:
        golden_record = f.read()
    assert code_files["generated_output_B"] == golden_record

    with open("tests/data/test-multiple-root-sections-C.golden-record", "r") as f:
        golden_record = f.read()
    assert code_files["generated_output_C"] == golden_record


def test_doc_is_ignored():
    code_files = get_code_files(Path("tests/data/test-doc-is-ignored.w"))
    with open("tests/data/test-doc-is-ignored.golden-record", "r") as f:
        golden_record = f.read()
    assert code_files["generated_output"] == golden_record


def test_sections_can_include_sections():
    code_files = get_code_files(Path("tests/data/test-sections-can-include-sections.w"))
    with open("tests/data/test-sections-can-include-sections.golden-record", "r") as f:
        golden_record = f.read()
    assert code_files["generated_output"] == golden_record


def test_inline_substitution():
    code_files = get_code_files(Path("tests/data/test-inline-substitution.w"))
    with open("tests/data/test-inline-substitution.golden-record", "r") as f:
        golden_record = f.read()
    assert code_files["generated_output"] == golden_record


def test_indentation_is_preserved():
    code_files = get_code_files(Path("tests/data/test-indentation-is-preserved.w"))
    with open("tests/data/test-indentation-is-preserved.golden-record", "r") as f:
        golden_record = f.read()
    assert code_files["generated_output"] == golden_record


def test_include_files():
    code_files = get_code_files(Path("tests/data/test-include-files.w"))
    with open("tests/data/test-include-files.golden-record", "r") as f:
        golden_record = f.read()
    assert code_files["generated_output"] == golden_record


def test_nested_include_files():
    code_files = get_code_files(Path("tests/data/test-nested-include-files.w"))
    with open("tests/data/test-nested-include-files.golden-record", "r") as f:
        golden_record = f.read()
    assert code_files["generated_output"] == golden_record


def test_recursive_sections_fail():
    with pytest.raises(CodeSectionRecursionError):
        get_code_files(Path("tests/data/test-recursive-sections-fail.w"))
    with pytest.raises(NoRootCodeSectionsFound):
        get_code_files(Path("tests/data/test-no-roots-means-recursion.w"))
