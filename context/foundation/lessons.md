# Lessons Learned

> Append-only register of recurring rules and patterns. Re-read at start by /10x-frame, /10x-research, /10x-plan, /10x-plan-review, /10x-implement, /10x-impl-review.

## Zmiana schematu pól zapisanych w JSONB wymaga migracji danych

- **Context**: backend/app/parsing/service.py:203-204 (ParsedFields.model_validate na kolumnach JSONB inquiry_analyses)
- **Problem**: ParsedFields ma extra="forbid" i jest walidowany ściśle przy odczycie; po zmianie schematu stare wiersze JSONB rzucają ValidationError, którego handlery nie łapią → GET/POST/PUT zwracają gołe 500.
- **Rule**: Każda zmiana modelu pydantic czytanego z JSONB (dodanie/usunięcie/zmiana typu pola) idzie w parze z migracją Alembic przepisującą istniejące wiersze, albo z polem dodanym jako opcjonalne z wartością domyślną.
- **Applies to**: backend/app/parsing/schema.py (ParsedFields) i każdy przyszły model zapisywany jako JSONB
