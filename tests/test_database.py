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


def test_can_get_just_root_names(shared_context):
    scanner.parse_source_file(
        shared_context,
        "test_names.sqlite",
        Path("tests/data/test-code-section-sequence-numbers.w")
    )
    db = db_gateway.get_database_connection(shared_context)
    all_names = dict(db_gateway.unabbreviated_names(db))
    root_names = dict(db_gateway.unabbreviated_names(db, roots_only=True))
    assert len(all_names) == 4
    assert len(root_names) == 1
