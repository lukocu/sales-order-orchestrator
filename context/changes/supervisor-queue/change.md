---
change_id: supervisor-queue
title: Supervisor queue
status: implementing
created: 2026-11-18
updated: 2026-11-18
archived_at: null
---

## Notes

Weryfikacja kodu fazy 1 (2026-11-18):

- Ruff i formatowanie całego backendu przechodzą; kompilacja źródeł Python przechodzi.
- Sprawdzanie typów 11 zmienionych plików z `--follow-imports=silent` przechodzi. Pełny mypy jest blokowany przez brak zainstalowanych `pwdlib` i `genai_prices`; próba `uv sync --locked` zakończyła się błędem dostępu do serwera pakietów.
- Osiem testów `tests/unit/test_mutation_context.py` przeszło osobno, z `--confcutdir=tests/unit` i użyciem dostępnych źródeł Python SQLAlchemy zamiast opcjonalnych rozszerzeń binarnych blokowanych przez Windows.
- Testy integracyjne dodano w `backend/tests/test_inquiry_mutations.py`, ale nie zostały wykonane: brak dostępu do silnika Docker, brak lokalnego PostgreSQL i blokada binarnego sterownika psycopg w Windows.
- Wymagana pełna bramka: `docker compose run --rm backend sh check.sh`. Kryteria fazy 1 w `plan.md` pozostają nieodhaczone do czasu jej wykonania; nie utworzono commita.

Weryfikacja fazy 1 (2026-11-18):

- docker compose run --rm backend sh check.sh przechodzi: Ruff, formatowanie, mypy, migracje Alembic oraz 1025 testów backendu.
- Poprawiono fixture testu wyścigu orkiestracji: przełączenie wyniku kontroli na standard czyści teraz również exception_type, zgodnie z ograniczeniem bazy.
- Kryteria automatyczne fazy 1 oznaczone jako ukończone. Bez commita.
