"""Minimal Vikunja REST client for tasks and the shopping list."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

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


def _parse_ts(value: str | None) -> datetime | None:
    if not value or value.startswith(_NO_DUE):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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


async def done_tasks(hours: int = 48, limit: int = 40) -> list[dict]:
    """Tasks completed within the last `hours`, newest first."""
    params = {"filter": "done = true", "sort_by": "done_at",
              "order_by": "desc", "per_page": limit}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{config.VIKUNJA_URL}/api/v1/tasks",
                             params=params, headers=_HEADERS)
        r.raise_for_status()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out = []
    for t in (r.json() or []):
        done_at = _parse_ts(t.get("done_at"))
        if not t.get("done") or done_at is None or done_at < cutoff:
            continue
        out.append({"title": t["title"], "done_at": t.get("done_at"),
                    "project_id": t.get("project_id"), "id": t["id"]})
    return out


# ── Lager-proxy til madplan (Fase 3, INTEGRATION_SPEC §2.3/§3.2) ─────
# Indkøbsprojektet (VIKUNJA_SHOPPING_PROJECT_ID) er "lageret". To buckets:
#   open          = åbne tasks  → "kommer ind i huset snart"
#   recently_done = afsluttet inden for INVENTORY_DONE_DAYS → "er på lager"
# Madplan afgør selv vægtningen (§4.2). Vikunja-finurligheder (null-resultat,
# filter_include_nulls) håndteres her, ét sted (§A4).

# Match-navn: lowercase uden mængde/enhed-hale. "Kyllingebryst 500g" → "kyllingebryst".
_QTY_TAIL = re.compile(
    r"\s*[-–,x×·]?\s*\d+(?:[.,]\d+)?\s*"
    r"(?:kg|g|gram|dl|cl|ml|l|liter|stk|pk|ps|pose(?:r)?|bdt|dåse(?:r)?|x)?\.?$",
    re.IGNORECASE,
)


def _norm_name(title: str) -> str:
    s = title.strip()
    prev = None
    while s and s != prev:
        prev = s
        s = _QTY_TAIL.sub("", s).strip(" ,-–x×·")
    return (s or title).strip().lower()


def _inv_item(t: dict, *, bucket: str, done: bool) -> dict:
    return {
        "name": _norm_name(t["title"]),
        "raw_title": t["title"],
        "done": done,
        "bucket": bucket,
        "vikunja_task_id": t["id"],
        "updated_at": t.get("done_at") if done else t.get("updated"),
    }


async def shopping_inventory(done_days: int | None = None, limit: int = 100) -> list[dict]:
    """Lager som liste af InventoryItem (§2.3), begge buckets, nyeste-agtigt.
    Kaster ved Vikunja-fejl — kalderen (endpointet) mapper til 502."""
    done_days = config.INVENTORY_DONE_DAYS if done_days is None else done_days
    proj = config.VIKUNJA_SHOPPING_PROJECT_ID
    async with httpx.AsyncClient(timeout=15) as client:
        r_open = await client.get(
            f"{config.VIKUNJA_URL}/api/v1/tasks", headers=_HEADERS,
            params={"filter": "done = false", "filter_include_nulls": "true",
                    "per_page": limit})
        r_open.raise_for_status()
        r_done = await client.get(
            f"{config.VIKUNJA_URL}/api/v1/tasks", headers=_HEADERS,
            params={"filter": "done = true", "sort_by": "done_at",
                    "order_by": "desc", "per_page": limit})
        r_done.raise_for_status()
    cutoff = datetime.now(timezone.utc) - timedelta(days=done_days)
    items: list[dict] = []
    for t in (r_open.json() or []):
        if t.get("done") or t.get("project_id") != proj:
            continue
        items.append(_inv_item(t, bucket="open", done=False))
    for t in (r_done.json() or []):
        done_at = _parse_ts(t.get("done_at"))
        if not t.get("done") or t.get("project_id") != proj:
            continue
        if done_at is None or done_at < cutoff:
            continue
        items.append(_inv_item(t, bucket="recently_done", done=True))
    return items
