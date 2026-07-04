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
