"""Pydantic schemas for the Aula pipeline (Del 3).

Layer 3 of the injection hardening: strict parsing with extra="forbid", an
intent whitelist via Literal, and length limits on every string. Anything the
LLM produces outside this schema is a parse error, which the pipeline turns
into the fail-safe item below (info, confidence 0 — never auto, never lost).
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_CTRL = re.compile(r"[\x00-\x1f\x7f]")

AmbiguityFlag = Literal["relative_date_unresolved", "recurring",
                        "multiple_dates", "unclear"]


class AulaItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["event", "handling", "info"]
    title: str = Field(max_length=120)
    summary: str = Field(max_length=200)
    # dt-alias: feltnavnene date/time ville ellers skygge for typerne
    # når Pydantic opløser annotationerne.
    date: dt.date | None = None       # absolut dato (LLM opløser relativt ift. NU-anker)
    time: dt.time | None = None
    all_day: bool = False
    deadline: dt.datetime | None = None  # primært for handling/urgent-info
    confidence: float = Field(ge=0.0, le=1.0)
    ambiguity_flags: list[AmbiguityFlag] = []

    @field_validator("title", "summary", mode="before")
    @classmethod
    def _clean_text(cls, v, info):
        # Strip control chars/newlines and collapse whitespace before the
        # length check; truncate rather than fail so a verbose model answer
        # doesn't needlessly demote a good item to the fail-safe path.
        if isinstance(v, str):
            v = re.sub(r"\s+", " ", _CTRL.sub(" ", v)).strip()
            return v[:120] if info.field_name == "title" else v[:200]
        return v

    @field_validator("date", "time", "deadline", mode="before")
    @classmethod
    def _empty_is_none(cls, v):
        return None if v == "" else v


def fail_safe_item(subject: str) -> AulaItem:
    """The whole mail as one info item: never auto-creatable, never lost."""
    return AulaItem(intent="info", title=(subject or "(uden emne)")[:120],
                    summary="Kunne ikke klassificeres automatisk — se mailen i Gmail.",
                    confidence=0.0, ambiguity_flags=["unclear"])


# ── Generel post-triage (Del 4) ─────────────────────────────────────
# One verdict per mail. Arbitrary senders are fully untrusted, so there is
# no auto path at all — the schema only feeds highlights and button
# proposals. Same strictness as AulaItem.

SenderKind = Literal["kommune", "bank", "forsikring", "sundhed", "skole",
                     "forening", "butik", "nyhedsbrev", "andet"]


class TriageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    importance: Literal["high", "normal", "low"]
    summary: str = Field(max_length=200)
    sender_kind: SenderKind = "andet"
    action_required: bool = False
    action_title: str | None = Field(default=None, max_length=120)
    deadline: dt.datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("summary", "action_title", mode="before")
    @classmethod
    def _clean(cls, v, info):
        if isinstance(v, str):
            v = re.sub(r"\s+", " ", _CTRL.sub(" ", v)).strip()
            v = v[:120] if info.field_name == "action_title" else v[:200]
            return v or None if info.field_name == "action_title" else v
        return v

    @field_validator("deadline", mode="before")
    @classmethod
    def _empty_deadline(cls, v):
        return None if v == "" else v


def fail_safe_triage() -> TriageItem:
    """Unparseable answer -> a normal, action-free highlight: the mail shows
    up in the digest but can never trigger a proposal or urgency."""
    return TriageItem(importance="normal",
                      summary="Kunne ikke klassificeres automatisk — se mailen i Gmail.",
                      action_required=False, confidence=0.0)
