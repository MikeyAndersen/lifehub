"""Deterministisk dansk relativ-dato-resolver.

Små sprogmodeller regner ofte relative datoer forkert ("på torsdag", "om 14
dage"). Denne resolver oversætter de ALMINDELIGE, ENTYDIGE danske udtryk til en
absolut ISO-dato i kode, så vi kan overtrumfe modellens gæt på selve datoen
(intent og klokkeslæt lader vi fortsat modellen om).

Bevidst konservativ: finder vi 0 eller FLERE end ét datoudtryk, returnerer vi
None og rører ikke modellens dato — det er bedre at lade tvivlstilfælde stå end
at "rette" en dato der måske var rigtig.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

# KUN fulde ugedagsnavne (+ ascii-varianter). Korte former som "man"/"søn"
# er også helt almindelige danske ord ("man skal…", "søn") og ville give
# falske match — de udelades bevidst.
_WEEKDAYS = {
    "mandag": 0,
    "tirsdag": 1,
    "onsdag": 2,
    "torsdag": 3,
    "fredag": 4,
    "lørdag": 5, "loerdag": 5,
    "søndag": 6, "soendag": 6,
}

# Talord 1-14 så "om to dage" også fanges.
_NUMWORDS = {
    "en": 1, "én": 1, "et": 1, "to": 2, "tre": 3, "fire": 4, "fem": 5, "seks": 6,
    "syv": 7, "otte": 8, "ni": 9, "ti": 10, "elleve": 11, "tolv": 12,
    "tretten": 13, "fjorten": 14,
}


def _next_weekday(today: date, target_wd: int) -> date:
    """Førstkommende <ugedag> EFTER i dag (samme ugedag ⇒ +7), jf. prompten."""
    ahead = (target_wd - today.weekday()) % 7
    return today + timedelta(days=ahead or 7)


def _num(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    return _NUMWORDS.get(token)


def _all_matches(text: str, today: date) -> list[date]:
    """Alle entydige datoudtryk i teksten, i fundet rækkefølge."""
    t = text.lower()
    hits: list[date] = []

    # Faste udtryk med ordgrænser, så fx "i dagevis" ikke matcher "i dag".
    # "i overmorgen" tjekkes før "i morgen" (og deler ikke substring).
    for phrase, delta in (("i overmorgen", 2), ("i morgen", 1), ("imorgen", 1),
                          ("i dag", 0), ("idag", 0), ("i går", -1), ("igår", -1)):
        if re.search(rf"\b{phrase}\b", t):
            hits.append(today + timedelta(days=delta))

    # "weekenden" / "i weekenden" → førstkommende lørdag.
    if re.search(r"\bweekend", t):
        hits.append(_next_weekday(today, 5))

    # "næste uge" → mandag i næste uge.
    if re.search(r"\bn[æa]ste uge\b", t):
        hits.append(_next_weekday(today, 0))

    # "om N dage/uger" (tal eller talord).
    for m in re.finditer(r"\bom\s+([a-zæøå]+|\d+)\s+(dag|dage|uge|uger)\b", t):
        n = _num(m.group(1))
        if n is not None:
            hits.append(today + timedelta(days=n * (7 if m.group(2).startswith("uge") else 1)))

    # "(på|i|næste) <ugedag>" og bare "<ugedag>" som helt ord.
    for name, wd in _WEEKDAYS.items():
        if re.search(rf"\b{name}\b", t):
            hits.append(_next_weekday(today, wd))

    return hits


def resolve(text: str, today: date) -> str | None:
    """Absolut ISO-dato ("YYYY-MM-DD") hvis teksten indeholder præcis ÉT
    entydigt datoudtryk der peger på én dato; ellers None."""
    hits = _all_matches(text, today)
    unique = {d.isoformat() for d in hits}
    return next(iter(unique)) if len(unique) == 1 else None
