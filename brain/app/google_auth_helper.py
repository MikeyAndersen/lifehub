"""Shared Google OAuth credentials loader.

One token file carries all scopes (calendar + gmail.readonly after the Del-3
re-auth). Loaded without a scopes filter so both gcal.py and gmail.py build
their services on the same credentials object.
"""
from __future__ import annotations

from google.oauth2.credentials import Credentials

from . import config


def google_creds() -> Credentials:
    return Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_PATH)
