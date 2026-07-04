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


async def add_shopping_items(items: list[str]) -> list[dict]:
    return [await create_task(item, project_id=config.VIKUNJA_SHOPPING_PROJECT_ID)
            for item in items]


async def get_task(ref: dict) -> dict | None:
    """Look up a task by created_ref. None if it was deleted."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{config.VIKUNJA_URL}/api/v1/tasks/{ref['task_id']}",
                             headers=_HEADERS)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


async def update_task(ref: dict, *, title: str | None = None, due: str | None = None,
                      description: str | None = None) -> dict | None:
    """Partial update by created_ref. Vikunja's task update (POST /tasks/{id})
    replaces the task, so fetch-merge-post to keep untouched fields intact.
    due="" clears the due date; due=None leaves it alone."""
    task = await get_task(ref)
    if task is None:
        return None
    if title is not None:
        task["title"] = title
    if description is not None:
        task["description"] = description
    if due == "":
        task["due_date"] = "0001-01-01T00:00:00Z"
    elif due is not None:
        task["due_date"] = due if "T" in due else f"{due}T17:00:00+02:00"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{config.VIKUNJA_URL}/api/v1/tasks/{ref['task_id']}",
                              json=task, headers=_HEADERS)
        r.raise_for_status()
        return r.json()


async def delete_task(ref: dict) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.delete(f"{config.VIKUNJA_URL}/api/v1/tasks/{ref['task_id']}",
                                headers=_HEADERS)
        if r.status_code != 404:  # already gone is fine — deletion is idempotent
            r.raise_for_status()


async def set_task_done(task_id: int, done: bool = True) -> dict | None:
    """Mark a task done/undone. Same fetch-merge-post dance as update_task,
    since Vikunja's task update (POST /tasks/{id}) replaces the whole task.
    None if the task no longer exists."""
    task = await get_task({"task_id": task_id})
    if task is None:
        return None
    task["done"] = done
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{config.VIKUNJA_URL}/api/v1/tasks/{task_id}",
                              json=task, headers=_HEADERS)
        r.raise_for_status()
        return r.json()


# Vikunja encodes "no due date" as the zero timestamp (see update_task above).
_NO_DUE = "0001-01-01"


def _due(t: dict) -> str | None:
    due = t.get("due_date")
    return None if not due or due.startswith(_NO_DUE) else due


async def open_tasks(limit: int = 40) -> list[dict]:
    # Current Vikunja lists tasks across all projects via GET /api/v1/tasks.
    # The old /tasks/all endpoint 400s ("Invalid model provided") once a
    # filter is supplied. `filter=done = false` drops completed tasks
    # server-side; an empty result comes back as JSON null, not [].
    # filter_include_nulls=true is required alongside sort_by=due_date:
    # without it Vikunja silently omits tasks that have no due date set
    # (its own frontend always sends it).
    params = {"filter": "done = false", "sort_by": "due_date",
              "filter_include_nulls": "true", "per_page": limit}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{config.VIKUNJA_URL}/api/v1/tasks",
                             params=params, headers=_HEADERS)
        r.raise_for_status()
    tasks = [t for t in (r.json() or []) if not t.get("done")]
    tasks.sort(key=lambda t: _due(t) or "9999")  # uden frist → nederst
    return [{"title": t["title"], "due": _due(t),
             "project_id": t.get("project_id"), "id": t["id"]} for t in tasks]
