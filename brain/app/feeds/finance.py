"""GoCardless Bank Account Data (ex-Nordigen) — free PSD2 access to Danish banks.

Setup once: create a free account at bankaccountdata.gocardless.com, create a
requisition for your bank, and store SECRET_ID/SECRET_KEY + requisition id.
TODO: full token dance is sketched here; finish when you enable phase 2.
"""
from .. import store


async def fetch() -> dict:
    # TODO: exchange SECRET_ID/SECRET_KEY -> access token, list accounts on the
    # requisition, pull /balances and /transactions?date_from=..., normalise.
    # Until then the widget renders the manually noted expenses from Telegram.
    return {
        "accounts": [],
        "recent_expenses": store.recent_expenses(8),
        "status": "not_configured",
    }
