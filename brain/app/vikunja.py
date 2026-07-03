"""Minimal Vikunja REST client for tasks and the shopping list."""
from __future__ import annotations

import httpx

from . import config

_HEADERS = {"Authorization": f"Bearer {config.VIKUNJA_TOKEN}"}


async def create_task(title: str, due: str | None = None,
                      project_id: int | None = None, description: str = "") -> dict:
    project_id = project_id or config.VIKUNJA_DEFAULT_PROJECT_ID
    body: dict = {"title": title, "description": description}
    if due:
        body["due_date"] = due if "T" in due else f"{due}T17:00:00+02:00"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.put(f"{config.VIKUNJA_URL}/api/v1/projects/{project_id}/tasks",
                             json=body, headers=_HEADERS)
        r.raise_for_status()
        return r.json()


async def add_shopping_items(items: list[str]) -> None:
    for item in items:
        await create_task(item, project_id=config.VIKUNJA_SHOPPING_PROJECT_ID)


async def open_tasks(limit: int = 40) -> list[dict]:
    # Current Vikunja lists tasks across all projects via GET /api/v1/tasks.
    # The old /tasks/all endpoint 400s ("Invalid model provided") once a
    # filter is supplied. `filter=done = false` drops completed tasks
    # server-side; an empty result comes back as JSON null, not [].
    params = {"filter": "done = false", "sort_by": "due_date", "per_page": limit}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{config.VIKUNJA_URL}/api/v1/tasks",
                             params=params, headers=_HEADERS)
        r.raise_for_status()
    tasks = [t for t in (r.json() or []) if not t.get("done")]
    tasks.sort(key=lambda t: t.get("due_date") or "9999")
    return [{"title": t["title"], "due": t.get("due_date"),
             "project_id": t.get("project_id"), "id": t["id"]} for t in tasks]
