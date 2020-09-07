import pytest

from blue import database, errors, scanner


@pytest.fixture()
def shared_context():
    class MockContext:
        def __init__(self):
            self.obj = dict()

    return MockContext()


@pytest.fixture()
def db(shared_context):
    return database.create_database(shared_context, ":memory:")


def test_initial_db_state(db):
    assert scanner.get_parser_state(db) == scanner.ParserState.NO_WORK_DONE_YET


def test_set_parser_state(db):
    assert scanner.get_parser_state(db) == scanner.ParserState.NO_WORK_DONE_YET
    scanner.set_parser_state(db, scanner.ParserState.ALL_ABBREVIATIONS_RESOLVED)
    assert scanner.get_parser_state(db) == scanner.ParserState.ALL_ABBREVIATIONS_RESOLVED


