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
