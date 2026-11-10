"""Deterministic resolution of Polish deadline phrases against a reference date.

Matching ignores case and Polish diacritics ("do piątku" and "DO PIATKU" are the same
phrase). Folding keeps one character per character, so match positions in the folded text
point at the same span of the original text.
"""

import calendar
import datetime as dt
import re
from dataclasses import dataclass

_FOLD = str.maketrans("ąćęłńóśźż", "acelnoszz")

# Genitive weekday forms ("do piątku"), folded; index = date.weekday().
_WEEKDAYS = ("poniedzialku", "wtorku", "srody", "czwartku", "piatku", "soboty", "niedzieli")

_PHRASE = re.compile(
    r"\b(?:"
    r"do\s+konca\s+(?P<end_of>tygodnia|miesiaca)"
    rf"|do\s+(?P<weekday>{'|'.join(_WEEKDAYS)})"
    r"|w\s+ciagu\s+(?:(?P<within_days>\d{1,3})\s+dni|(?P<within_week>tygodnia))"
    r"|za\s+(?P<in_days>\d{1,3})\s+dni"
    r"|(?P<relative_day>pojutrze|jutro)"
    r"|(?P<day>\d{1,2})\.(?P<month>\d{1,2})(?:\.(?P<year>\d{4}))?(?![.\d])"
    r")\b"
)


@dataclass(frozen=True)
class DeadlineResolution:
    date: dt.date | None
    ambiguous: bool = False


def resolve_deadline(text: str, reference: dt.date) -> DeadlineResolution:
    """Resolve the first recognized deadline phrase in `text`; unrecognized → `date=None`."""
    match = _PHRASE.search(_fold(text))
    if match is None:
        return DeadlineResolution(None)
    return _resolve(match, reference)


def find_deadline_phrase(text: str) -> str | None:
    """The first recognized deadline phrase as written in `text`, or `None`."""
    match = _PHRASE.search(_fold(text))
    return None if match is None else text[match.start() : match.end()]


def _fold(text: str) -> str:
    # Per-character lower() keeps the length even for characters whose lowercase is longer.
    return "".join(char.lower() if len(char.lower()) == 1 else char for char in text).translate(
        _FOLD
    )


def _resolve(match: re.Match[str], reference: dt.date) -> DeadlineResolution:
    groups = match.groupdict()
    if groups["end_of"] == "tygodnia":
        return _end_of_week(reference)
    if groups["end_of"] == "miesiaca":
        last_day = calendar.monthrange(reference.year, reference.month)[1]
        return DeadlineResolution(reference.replace(day=last_day))
    if groups["weekday"] is not None:
        return _next_weekday(reference, _WEEKDAYS.index(groups["weekday"]))
    if groups["within_week"] is not None:
        return DeadlineResolution(reference + dt.timedelta(days=7))
    days = groups["within_days"] or groups["in_days"]
    if days is not None:
        return DeadlineResolution(reference + dt.timedelta(days=int(days)))
    if groups["relative_day"] is not None:
        offset = 2 if groups["relative_day"] == "pojutrze" else 1
        return DeadlineResolution(reference + dt.timedelta(days=offset))
    return _explicit_date(groups, reference)


def _next_weekday(reference: dt.date, weekday: int) -> DeadlineResolution:
    """Nearest such weekday from `reference` inclusive; the same day is ambiguous."""
    offset = (weekday - reference.weekday()) % 7
    return DeadlineResolution(reference + dt.timedelta(days=offset), ambiguous=offset == 0)


def _end_of_week(reference: dt.date) -> DeadlineResolution:
    """Friday of the reference week; from a weekend, the next week's Friday (ambiguous)."""
    friday = 4
    if reference.weekday() > friday:
        return DeadlineResolution(
            reference + dt.timedelta(days=7 - reference.weekday() + friday), ambiguous=True
        )
    return DeadlineResolution(reference + dt.timedelta(days=friday - reference.weekday()))


def _explicit_date(groups: dict[str, str | None], reference: dt.date) -> DeadlineResolution:
    day, month, year = groups["day"], groups["month"], groups["year"]
    if day is None or month is None:
        return DeadlineResolution(None)
    try:
        if year is not None:
            return DeadlineResolution(dt.date(int(year), int(month), int(day)))
        candidate = dt.date(reference.year, int(month), int(day))
        if candidate < reference:
            return DeadlineResolution(
                dt.date(reference.year + 1, int(month), int(day)), ambiguous=True
            )
        return DeadlineResolution(candidate)
    except ValueError:  # e.g. 31.02, or 29.02 rolled into a non-leap year
        return DeadlineResolution(None)
