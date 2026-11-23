import os
from pathlib import Path

import pytest

os.environ.setdefault("HELLOC_TEST", "1")

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "heloc_test.db"


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    import app.store as store

    monkeypatch.setattr(store, "DB_PATH", DB)
    if DB.exists():
        DB.unlink()
    store.init_db()
    yield
    if DB.exists():
        DB.unlink()


@pytest.fixture
def seeded(fresh_db):
    import app.store as store
    from app.seed import load_all

    load_all()
    return store