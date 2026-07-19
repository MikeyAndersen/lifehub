"""Test-harness: hver test får sin egen SQLite-fil, så store.init() aldrig
rører den rigtige lifehub.db. DB_PATH skal sættes FØR app.config importeres."""
import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp(prefix="lifehub-test-")
os.environ["DB_PATH"] = os.path.join(_tmp, "test.db")


@pytest.fixture()
def db():
    from app import config, store
    # Frisk fil pr. test — filnavnet roteres så CREATE TABLE kører igen.
    config.DB_PATH = os.path.join(_tmp, f"test-{os.urandom(4).hex()}.db")
    store.init()
    return store
