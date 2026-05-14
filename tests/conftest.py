from pathlib import Path
import sqlite3
import pytest

from pogo_scout.db.repo import init_db

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def db(tmp_path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "test.db", detect_types=sqlite3.PARSE_DECLTYPES)
    init_db(conn)
    yield conn
    conn.close()
