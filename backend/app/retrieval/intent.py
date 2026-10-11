"""Temporal intent parsing — deterministic, no LLM in the loop.

Kinds:
- current   : "what is the leave policy?" / no explicit date → today's date
- as_of     : "what was the allowance in February 2025?" → representative date
- compare   : "what changed between 2024 and 2026?" → two representative dates

Conventions (documented, mirrored in the frontend date picker):
- bare year YYYY            -> July 1 (mid-year representative point)
- month+year "February 2025" -> the 15th (mid-month)
- "current"/"today"/"now"   -> server-local date.today()
- unclear relative dates    -> current, but `ambiguous=True` so the API can
                               surface a warning instead of guessing silently.
"""

import re
from dataclasses import dataclass
from datetime import date

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
_MONTH_NAMES = "|".join(_MONTHS)

_RE_FULL_DATE = re.compile(
    rf"(?:on\s+)?({_MONTH_NAMES})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})",
    re.IGNORECASE,
)
_RE_MONTH_YEAR = re.compile(
    rf"(?:in|of|during|as of)?\s*({_MONTH_NAMES})\s+(\d{{4}})", re.IGNORECASE
)
_RE_BETWEEN_YEARS = re.compile(
    r"between\s+(\d{4})\s+and\s+(\d{4})|from\s+(\d{4})\s+to\s+(\d{4})",
    re.IGNORECASE,
)
_RE_YEAR = re.compile(r"\b(19|20)\d{2}\b")
_RE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_RE_COMPARE = re.compile(
    r"\b(compare|differ|change[sd]?|what changed|versus|vs\.?)\b", re.IGNORECASE
)
_RE_CURRENT = re.compile(r"\b(current|currently|today|now|latest|present)\b", re.IGNORECASE)
_RE_PAST = re.compile(r"\b(was|were|used to|previous|previously|before|earlier)\b", re.IGNORECASE)


@dataclass
class TemporalIntent:
    kind: str  # "current" | "as_of" | "compare"
    as_of: date | None = None          # for current/as_of
    compare_a: date | None = None      # for compare
    compare_b: date | None = None
    ambiguous: bool = False            # surfaced as a warning to the client
    resolved_by: str = "default"       # how the date was chosen


def _year_point(y: int) -> date:
    return date(y, 7, 1)


def parse_temporal_intent(question: str, *, today: date | None = None) -> TemporalIntent:
    today = today or date.today()
    q = question.lower()

    # Comparison intent wins — it needs two periods.
    between = _RE_BETWEEN_YEARS.search(q)
    if between:
        a, b = (int(g) for g in between.groups() if g is not None)
        return TemporalIntent(
            kind="compare",
            compare_a=_year_point(min(a, b)),
            compare_b=_year_point(max(a, b)),
            resolved_by="explicit_range",
        )
    if _RE_COMPARE.search(q):
        # "compare previous and current" — previous period is ambiguous without
        # a date; flag it so the client can ask, but provide a usable default:
        # today vs one year ago.
        if not (_RE_FULL_DATE.search(q) or _RE_MONTH_YEAR.search(q) or _RE_YEAR.search(q)):
            return TemporalIntent(
                kind="compare",
                compare_a=date(today.year - 1, today.month, min(today.day, 28)),
                compare_b=today,
                ambiguous=True,
                resolved_by="default_previous_year",
            )

    # Explicit full date: "on March 15, 2026" / "March 15, 2026".
    if m := _RE_FULL_DATE.search(q):
        d = date(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
        return TemporalIntent(kind="as_of", as_of=d, resolved_by="explicit_date")

    # ISO date 2026-03-15.
    if m := _RE_ISO.search(q):
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return TemporalIntent(kind="as_of", as_of=d, resolved_by="explicit_date")

    # Month + year: "in February 2025" -> the 15th.
    if m := _RE_MONTH_YEAR.search(q):
        d = date(int(m.group(2)), _MONTHS[m.group(1).lower()], 15)
        return TemporalIntent(kind="as_of", as_of=d, resolved_by="month_year_midpoint")

    # Bare year: "in 2024" -> July 1.
    if m := _RE_YEAR.search(q):
        d = _year_point(int(m.group(0)))
        return TemporalIntent(kind="as_of", as_of=d, resolved_by="year_midpoint")

    # Past tense without a date: "what WAS the allowance?" — genuinely
    # ambiguous; use a documented default and flag it.
    if _RE_PAST.search(q) and not _RE_CURRENT.search(q):
        return TemporalIntent(
            kind="as_of",
            as_of=date(today.year - 1, today.month, min(today.day, 28)),
            ambiguous=True,
            resolved_by="default_previous_year",
        )

    # Default: current policy questions.
    return TemporalIntent(kind="current", as_of=today, resolved_by="default_today")
