"""DRIFT-footerens tilstandslogik. Kun de deterministiske dele testes —
ollama-ping mockes."""
import time

from app import panel_status


def test_age_state_thresholds():
    assert panel_status.age_state(60, warn_after_s=900) == "ok"
    assert panel_status.age_state(901, warn_after_s=900) == "warn"
    assert panel_status.age_state(None, warn_after_s=900) == "off"


async def test_build_reports_cache_ages(db, monkeypatch):
    async def fake_ping():
        return True

    monkeypatch.setattr(panel_status, "_ollama_ok", fake_ping)
    db.set_cache("tasks", [])
    doc = await panel_status.build()
    names = [s["name"] for s in doc["services"]]
    assert "vikunja" in names and "ollama" in names
    vik = next(s for s in doc["services"] if s["name"] == "vikunja")
    assert vik["state"] == "ok"
    assert vik["detail"].startswith("sync ")
