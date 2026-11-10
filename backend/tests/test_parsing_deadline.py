from datetime import date

import pytest

from app.parsing.deadline import DeadlineResolution, find_deadline_phrase, resolve_deadline

MONDAY = date(2026, 11, 2)
FRIDAY = date(2026, 11, 6)
SATURDAY = date(2026, 11, 7)


@pytest.mark.parametrize(
    ("text", "reference", "expected"),
    [
        # Seed inquiries, resolved from their received_at.
        ("do piątku", MONDAY, date(2026, 11, 6)),
        ("do końca miesiąca", date(2026, 11, 3), date(2026, 11, 30)),
        ("w ciągu tygodnia", date(2026, 11, 5), date(2026, 11, 12)),
        # Every weekday in the genitive.
        ("do poniedziałku", FRIDAY, date(2026, 11, 9)),
        ("do wtorku", MONDAY, date(2026, 11, 3)),
        ("do środy", MONDAY, date(2026, 11, 4)),
        ("do czwartku", FRIDAY, date(2026, 11, 12)),
        ("do soboty", MONDAY, date(2026, 11, 7)),
        ("do niedzieli", MONDAY, date(2026, 11, 8)),
        ("do końca tygodnia", MONDAY, FRIDAY),
        ("do końca tygodnia", FRIDAY, FRIDAY),
        ("w ciągu 10 dni", MONDAY, date(2026, 11, 12)),
        ("za 3 dni", MONDAY, date(2026, 11, 5)),
        ("jutro", MONDAY, date(2026, 11, 3)),
        ("pojutrze", MONDAY, date(2026, 11, 4)),
        ("do 15.11", MONDAY, date(2026, 11, 15)),
        ("02.11", MONDAY, MONDAY),
        ("dostawa 3.1.2027", MONDAY, date(2027, 1, 3)),
        # Case, missing diacritics and surrounding words do not matter.
        ("Z dostawą DO PIĄTKU, proszę", MONDAY, FRIDAY),
        ("do piatku", MONDAY, FRIDAY),
        ("W CIAGU TYGODNIA", MONDAY, date(2026, 11, 9)),
    ],
)
def test_phrase_resolves_to_date(text: str, reference: date, expected: date) -> None:
    assert resolve_deadline(text, reference) == DeadlineResolution(expected, ambiguous=False)


def test_weekday_on_the_same_weekday_is_ambiguous() -> None:
    assert resolve_deadline("do piątku", FRIDAY) == DeadlineResolution(FRIDAY, ambiguous=True)


@pytest.mark.parametrize("reference", [SATURDAY, date(2026, 11, 8)])
def test_end_of_week_from_weekend_is_next_friday_and_ambiguous(reference: date) -> None:
    assert resolve_deadline("do końca tygodnia", reference) == DeadlineResolution(
        date(2026, 11, 13), ambiguous=True
    )


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        (date(2026, 2, 10), date(2026, 2, 28)),
        (date(2028, 2, 1), date(2028, 2, 29)),
        (date(2026, 12, 31), date(2026, 12, 31)),
        (date(2026, 12, 5), date(2026, 12, 31)),
    ],
)
def test_end_of_month(reference: date, expected: date) -> None:
    assert resolve_deadline("do końca miesiąca", reference) == DeadlineResolution(expected)


def test_date_without_year_before_reference_rolls_to_next_year_and_is_ambiguous() -> None:
    assert resolve_deadline("do 10.01", date(2026, 12, 20)) == DeadlineResolution(
        date(2027, 1, 10), ambiguous=True
    )


def test_week_and_month_cross_the_year() -> None:
    assert resolve_deadline("w ciągu tygodnia", date(2026, 12, 28)) == DeadlineResolution(
        date(2027, 1, 4)
    )


@pytest.mark.parametrize(
    "text",
    ["jak najszybciej", "", "rabat 25%", "31.02", "29.02.2027", "do 45.13", "w przyszłym roku"],
)
def test_unrecognized_or_invalid_phrase_has_no_date(text: str) -> None:
    assert resolve_deadline(text, MONDAY) == DeadlineResolution(None)


def test_find_phrase_returns_original_spelling() -> None:
    body = "prosimy o ofertę na 80 szt. ABC-100 z dostawą Do Piątku. Pozdrawiam"

    assert find_deadline_phrase(body) == "Do Piątku"
    assert find_deadline_phrase("Czekamy na ofertę z terminem realizacji.") is None
