from pathlib import Path

import pytest

from blue.bootstrap.original_scanner import get_code_files
from blue.code_writer import write_code_files


@pytest.fixture()
def output_root():
    return Path("tests/output")


def any_output_files(output_root):
    return any(p.is_file() for p in output_root.glob("*"))


def unlink_all_output_files(output_root):
    for f in output_root.glob("*"):
        if f.is_file():
            f.unlink()
        elif f.is_dir():
            unlink_all_output_files(f)
            f.rmdir()


@pytest.fixture()
def manage_output(output_root):
    if not output_root.exists():
        output_root.mkdir(parents=True)
    unlink_all_output_files(output_root)
    yield
    unlink_all_output_files(output_root)


@pytest.fixture()
def shared_context():
    return dict(obj={})


def test_writes_file(output_root, manage_output, shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-writes-file.w"))
    write_code_files(shared_context, code_files)
    assert (output_root / "test-writes-file.out").exists()


def test_writes_multiple_files(output_root, manage_output, shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-writes-multiple-files.w"))
    write_code_files(shared_context, code_files)
    assert (output_root / "test-writes-multiple-files1.out").exists()
    assert (output_root / "test-writes-multiple-files2.out").exists()
    assert (output_root / "test-writes-multiple-files3.out").exists()


def test_writes_select_files(output_root, manage_output, shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-writes-multiple-files.w"))
    write_code_files(shared_context, code_files, {"tests/output/test-writes-multiple-files2.out", "tests/output/test-writes-multiple-files3.out"})
    assert not (output_root / "test-writes-multiple-files1.out").exists()
    assert (output_root / "test-writes-multiple-files2.out").exists()
    assert (output_root / "test-writes-multiple-files3.out").exists()


def test_creates_directories(output_root, manage_output, shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-creates-directories.w"))
    write_code_files(shared_context, code_files)
    assert (output_root / "deeper" / "test-creates-directories.out").exists()


def test_respects_supplied_base_directory(output_root, manage_output, shared_context):
    code_files = get_code_files(shared_context, Path("tests/data/test-respects-supplied-base-directory.w"))
    write_code_files(shared_context, code_files, base_directory=output_root)
    assert (output_root / "a.out").exists()
    assert (output_root / "b" / "c.out").exists()
