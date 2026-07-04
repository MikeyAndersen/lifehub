"""LifeHub brain — FastAPI entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from . import config, dashboard, review, store, telegram, vikunja

logging.basicConfig(level=logging.INFO)
scheduler = AsyncIOScheduler(timezone=config.TZ)


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.init()
    scheduler.add_job(dashboard.refresh_calendar, "interval", minutes=5, jitter=30)
    scheduler.add_job(dashboard.refresh_tasks, "interval", minutes=5, jitter=30)
    scheduler.add_job(dashboard.refresh_weather, "interval", minutes=30)
    scheduler.add_job(dashboard.refresh_elpris, "interval", hours=1)
    scheduler.add_job(dashboard.refresh_finance, "interval", hours=6)
    scheduler.add_job(dashboard.morning_brief, CronTrigger(hour=6, minute=30))
    scheduler.start()
    # Warm the caches once at boot.
    for job in (dashboard.refresh_weather, dashboard.refresh_elpris,
                dashboard.refresh_calendar, dashboard.refresh_tasks):
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


def _viewer_email(request: Request) -> str | None:
    # Cloudflare Access injects the verified identity of the logged-in user.
    return request.headers.get("Cf-Access-Authenticated-User-Email")


@app.get("/api/dashboard")
async def api_dashboard(request: Request) -> dict:
    return dashboard.build(_viewer_email(request), ambient=False)


@app.get("/api/ambient")
async def api_ambient(request: Request) -> dict:
    # Shared-surface feed: never contains finance, regardless of viewer.
    return dashboard.build(_viewer_email(request), ambient=True)


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
    """Manual trigger for testing the morning brief."""
    email = _viewer_email(request)
    if not email or email.lower() not in config.ADMIN_EMAILS:
        raise HTTPException(status_code=403)
    await dashboard.morning_brief()
    return {"ok": True}
