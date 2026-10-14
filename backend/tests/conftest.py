import pytest

from apps.db.connection import Database, database_context


@pytest.fixture
def isolated_database(tmp_path):
    database = Database(tmp_path / "sessions.db")
    database.migrate()
    with database_context(database):
        yield database
