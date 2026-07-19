"""Shopping-blokken i dashboard-dokumentet (Warm Paper tablet INDKØB)."""
from app import dashboard


def test_build_includes_shopping_when_cached(db):
    db.set_cache("shopping", [{"id": 7, "title": "Mælk"}, {"id": 9, "title": "Rugbrød"}])
    doc = dashboard.build(None, ambient=False)
    assert doc["shopping"]["items"] == [{"id": 7, "title": "Mælk"},
                                        {"id": 9, "title": "Rugbrød"}]
    assert doc["shopping"]["stale"] is False


def test_ambient_doc_never_has_shopping(db):
    db.set_cache("shopping", [{"id": 7, "title": "Mælk"}])
    doc = dashboard.build(None, ambient=True)
    assert "shopping" not in doc


def test_no_cache_no_block(db):
    doc = dashboard.build(None, ambient=False)
    assert "shopping" not in doc
