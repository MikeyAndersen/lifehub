"""Phase 2/3 feed stubs: wire these up one at a time.

- madplan:  point at madplan.nova-tech.dk's API/JSON export -> tonight's dinner
- transit:  reuse the tog.nova-tech.dk Rejseplanen 2.0 logic -> next departures
- aula:     unofficial Aula client -> unread messages + ugeplan highlights
- affald:   kommune pickup schedule -> next pickup type + date
"""


async def madplan() -> dict:
    return {"tonight": None, "status": "not_configured"}


async def transit() -> dict:
    return {"departures": [], "status": "not_configured"}


async def aula() -> dict:
    return {"unread": 0, "highlights": [], "status": "not_configured"}


async def affald() -> dict:
    return {"next_pickup": None, "status": "not_configured"}
