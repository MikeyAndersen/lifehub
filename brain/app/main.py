"""LifeHub brain — FastAPI entrypoint."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from . import (ambient_stats, aula, config, dashboard, panel_status, post_actions,
               review, store, telegram, triage, vikunja)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("lifehub")
scheduler = AsyncIOScheduler(timezone=config.TZ)

# Overlap guard: a slow LLM classification (7B on CPU can take minutes per
# mail) must not be overtaken by the next poll tick. Shared by both mail
# streams (Aula + general triage) so they never overlap the LLM either.
_mail_lock = asyncio.Lock()


async def poll_gmail() -> dict:
    if not config.GMAIL_ENABLED:
        return {"enabled": False}
    if _mail_lock.locked():
        log.info("gmail poll skipped — previous run still working")
        return {"skipped": True}
    async with _mail_lock:
        return await aula.poll_and_process()


async def poll_inbox() -> dict:
    if not config.TRIAGE_ENABLED:
        return {"enabled": False}
    if _mail_lock.locked():
        log.info("inbox poll skipped — previous run still working")
        return {"skipped": True}
    async with _mail_lock:
        return await triage.poll_and_process()


async def _poll_mail_job() -> None:
    # Sequentially, so the two streams share one tick and never race the lock.
    for poll in (poll_gmail, poll_inbox):
        try:
            await poll()
        except Exception:
            log.exception("mail poll failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.init()
    scheduler.add_job(dashboard.refresh_calendar, "interval", minutes=5, jitter=30)
    scheduler.add_job(dashboard.refresh_tasks, "interval", minutes=5, jitter=30)
    scheduler.add_job(dashboard.refresh_weather, "interval", minutes=30)
    scheduler.add_job(dashboard.refresh_elpris, "interval", hours=1)
    scheduler.add_job(dashboard.refresh_finance, "interval", hours=6)
    scheduler.add_job(dashboard.refresh_madplan, "interval",
                      minutes=config.MADPLAN_POLL_MINUTES, jitter=30)
    scheduler.add_job(dashboard.refresh_beholdning, "interval",
                      minutes=config.MADPLAN_POLL_MINUTES, jitter=30)
    scheduler.add_job(dashboard.refresh_shopping, "interval", minutes=5, jitter=30)
    scheduler.add_job(dashboard.morning_brief, CronTrigger(hour=6, minute=30))
    if config.GMAIL_ENABLED or config.TRIAGE_ENABLED:
        scheduler.add_job(_poll_mail_job, "interval",
                          minutes=config.GMAIL_POLL_MINUTES, jitter=30)
        # Udløber pending forslag i begge streams (stream-agnostisk).
        scheduler.add_job(aula.expire_proposals, CronTrigger(hour=6, minute=0))
    scheduler.start()
    # Warm the caches once at boot.
    for job in (dashboard.refresh_weather, dashboard.refresh_elpris,
                dashboard.refresh_calendar, dashboard.refresh_tasks,
                dashboard.refresh_madplan, dashboard.refresh_beholdning,
                dashboard.refresh_shopping):
        try:
            await job()
        except Exception:
            pass
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="LifeHub brain", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@app.post("/telegram/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request, bg: BackgroundTasks) -> dict:
    if secret != config.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=403)
    update = await request.json()
    # Answer Telegram immediately; do the LLM/transcription work in the background.
    bg.add_task(telegram.handle_update, update)
    return {"ok": True}


@app.post("/api/review/drain")
async def review_drain(request: Request) -> dict:
    """Called repeatedly by the GPU boot agent until processed == 0.

    Locked behind REVIEW_DRAIN_TOKEN; with no token configured the endpoint
    is closed entirely (fail-closed), matching the opt-in nature of Pass 2.
    """
    auth = request.headers.get("Authorization", "")
    if (not config.REVIEW_DRAIN_TOKEN
            or auth != f"Bearer {config.REVIEW_DRAIN_TOKEN}"):
        raise HTTPException(status_code=403)
    return await review.drain()


@app.get("/api/internal/inventory")
async def api_internal_inventory(request: Request) -> list[dict]:
    """Lager-proxy til madplan (§2.3/§3.2): liste af InventoryItem, begge
    buckets. Bag INTERNAL_API_TOKEN; uden token er endpointet lukket."""
    auth = request.headers.get("Authorization", "")
    if (not config.INTERNAL_API_TOKEN
            or auth != f"Bearer {config.INTERNAL_API_TOKEN}"):
        raise HTTPException(status_code=403)
    try:
        return await vikunja.shopping_inventory()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Vikunja unavailable") from exc


def _viewer_email(request: Request) -> str | None:
    # Cloudflare Access injects the verified identity of the logged-in user.
    return request.headers.get("Cf-Access-Authenticated-User-Email")


@app.get("/api/dashboard")
async def api_dashboard(request: Request) -> dict:
    doc = dashboard.build(_viewer_email(request), ambient=False)
    # Fire-and-forget: opfrisk madplan hvis cachen er stale (§3.3). Rammer
    # næste load; dette svar bruger nuværende cache.
    asyncio.create_task(dashboard.ensure_fresh_madplan())
    return doc


@app.get("/api/ambient")
async def api_ambient(request: Request) -> dict:
    # Shared-surface feed: never contains finance, regardless of viewer.
    doc = dashboard.build(_viewer_email(request), ambient=True)
    asyncio.create_task(dashboard.ensure_fresh_madplan())
    return doc


@app.get("/api/ambient/stats")
async def api_ambient_stats() -> dict:
    """Orbit-skærmens systemstats (DEL 5). Aggregeringen er cachet 45 s i
    ambient_stats; tal uden datagrundlag er null — aldrig opfundne."""
    return ambient_stats.build()


@app.get("/api/ambient/events")
async def api_ambient_events(after_id: int | None = None, limit: int = 30) -> dict:
    """Event-puls til orbit-skærmen: seneste sys_events (polling med
    after_id-cursor). Kun kind/label — aldrig privat indhold."""
    return ambient_stats.events(after_id=after_id, limit=limit)


@app.post("/api/aula/poll")
async def api_aula_poll() -> dict:
    """Manual trigger for testing: curl -X POST .../api/aula/poll"""
    if not config.GMAIL_ENABLED:
        raise HTTPException(status_code=503, detail="GMAIL_ENABLED=false")
    return await poll_gmail()


@app.get("/api/aula/info")
async def api_aula_info(days: int = 7) -> dict:
    """Dashboard feed: info items + recent proposals/autos with status."""
    return aula.feed(days=max(1, min(days, 31)))


@app.post("/api/post/poll")
async def api_post_poll() -> dict:
    """Manual trigger for testing: curl -X POST .../api/post/poll"""
    if not config.TRIAGE_ENABLED:
        raise HTTPException(status_code=503, detail="TRIAGE_ENABLED=false")
    return await poll_inbox()


@app.post("/api/post/{item_id}/action")
async def api_post_action(item_id: int, request: Request) -> dict:
    """Warm Paper-panelets pille-handlinger. Admin-gated som brief/regenerate;
    semantikken ejes af aula.approve_item/reject-flowet (post_actions)."""
    email = _viewer_email(request)
    if not email or email.lower() not in config.ADMIN_EMAILS:
        raise HTTPException(status_code=403)
    try:
        body = await request.json()
    except Exception:
        body = {}
    action = body.get("action") if isinstance(body, dict) else None
    try:
        return await post_actions.apply(item_id, action or "")
    except post_actions.ActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@app.post("/api/post/archive-newsletters")
async def api_post_archive_newsletters(request: Request) -> dict:
    email = _viewer_email(request)
    if not email or email.lower() not in config.ADMIN_EMAILS:
        raise HTTPException(status_code=403)
    now = datetime.now(ZoneInfo(config.TZ)).isoformat(timespec="seconds")
    return {"ok": True, "archived": store.aula_archive_newsletters(now)}


@app.post("/api/tasks/{task_id}/done")
async def api_task_done(task_id: int, request: Request) -> dict:
    """Checkbox write-back from the dashboard: mark a Vikunja task done/undone.

    Sits behind the same Cloudflare Access gate as the rest of /api. Body is
    optional JSON {"done": bool}; omitted means done=true.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    done = bool(body.get("done", True)) if isinstance(body, dict) else True
    try:
        task = await vikunja.set_task_done(task_id, done)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Vikunja unavailable") from exc
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    # Refresh the cache so the next dashboard poll reflects reality.
    await dashboard.refresh_tasks()
    return {"ok": True, "id": task_id, "done": bool(task.get("done", done))}


@app.post("/api/brief/run")
async def run_brief_now(request: Request) -> dict:
    """Manual trigger for testing the FULL morning brief (digests + broadcast)."""
    email = _viewer_email(request)
    if not email or email.lower() not in config.ADMIN_EMAILS:
        raise HTTPException(status_code=403)
    await dashboard.morning_brief()
    return {"ok": True}


@app.post("/api/brief/regenerate")
async def regenerate_brief_now(request: Request) -> dict:
    """Dashboard-knappen ↻: regenerér KUN dagens brief-tekst (ingen
    Aula/post-digest, ingen Telegram-broadcast). Admin-gated som resten.
    Returnerer den nye brief, så dashboardet kan opdatere med det samme."""
    email = _viewer_email(request)
    if not email or email.lower() not in config.ADMIN_EMAILS:
        raise HTTPException(status_code=403)
    if not await dashboard.regenerate_brief():
        raise HTTPException(status_code=503,
                            detail="Kunne ikke generere brief (LLM utilgængelig?)")
    return {"ok": True, "brief": store.get_cache("brief")}


@app.get("/api/panel/status")
async def api_panel_status(request: Request) -> dict:
    """DRIFT-footer til Warm Paper-panelet. Admin-gated: driftsdata er ufarligt
    men panelet er en admin-flade, så samme regel som resten."""
    email = _viewer_email(request)
    if not email or email.lower() not in config.ADMIN_EMAILS:
        raise HTTPException(status_code=403)
    return await panel_status.build()
