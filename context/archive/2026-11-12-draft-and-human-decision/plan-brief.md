# Draft and human decision (S-07) — Plan Brief

> Full plan: `context/changes/draft-and-human-decision/plan.md`
> Research: `context/changes/draft-and-human-decision/research.md`

## What & Why

Zamykamy przepływ wyjątku z US-01: handlowiec dostaje szkic odpowiedzi do klienta z liczbami z wyliczonych
danych i sekcją „Why this recommendation?”, a potem zatwierdza, edytuje albo odrzuca go z zapisem kto,
kiedy i dlaczego (FR-009/010/011). Guardrail PRD: nic nie trafia do klienta bez człowieka, a edycja nie
może obejść polityki.

## Starting Point

Po S-06 każde zapytanie z wyjątkiem ma rekomendację z wybraną opcją (wszystkie liczby: linie, ceny,
ilości, daty, wartość, marża) i werdykt polityki z czystym rdzeniem `evaluate()`. Nie ma żadnego stanu
szkicu, decyzji ani statusu zapytania, a reguła rabatu ocenia prośbę klienta, nie cenę w ofercie.

## Desired End State

Sekcja Draft pokazuje e-mail po polsku (liczby z kodu, dwa akapity z LLM bez cyfr), uzasadnienie i
obowiązujący werdykt. Approve daje READY TO SEND (wysyłka symulowana) albo AWAITING SUPERVISOR, gdy polityka
wymaga przełożonego; edycja opcji/ceny/ilości przelicza wartość, marżę i politykę (z rabatem w ofercie);
Reject wymaga powodu. Historia decyzji przeżywa zmiany upstream.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Approve przy `requires_supervisor` | Status AWAITING SUPERVISOR, S-08 dokończy | Guardrail zachowany, a S-08 dostaje gotowy stan zgodny z US-02 | Plan |
| Zakres edycji | Inna policzona opcja + cena jednostkowa + ilość linii | Koszt zawsze znany, więc marża rzetelna; reużywa `options.py` | Plan |
| Kształt szkicu | Kod składa e-mail z liczbami, LLM pisze wstęp i zamknięcie bez cyfr, PL | Liczby fizycznie nie mogą pochodzić z modelu (FR-010) | Plan |
| Zakres zapytań | Tylko ścieżka wyjątku z rekomendacją | Zgodne z US-01 i pinem do `recommended_at` | Plan / Research |
| Model decyzji | Szkic przypięty do `recommended_at` + historia append-only | Pełny ślad FR-009; nowa rekomendacja zeruje szkic, nie historię | Plan (rekomendacja przyjęta) |
| Reject i powód | REJECTED końcowy, wyjście przez Regenerate; powód wymagany dla Reject i Edit | Jasny stan końcowy, „dlaczego” tam, gdzie najważniejsze | Plan (rekomendacja przyjęta) |
| Polityka edycji | `offered_discount_percent`; reguła rabatu nie przechodzi, gdy za duży jest rabat z prośby klienta lub w ofercie | Obniżka ceny ani pozorna edycja nie omijają reguły rabatu | Research / Plan review F1 |
| Werdykt nieedytowanej oferty | Werdykt etapu S-06, musi być aktualny | Bez zmiany semantyki S-06 | Plan |
| Awaria LLM | Retry, potem stały tekst zapasowy | Szkic nigdy nie blokuje decyzji | Plan |

## Scope

**In scope:**
- Migracja `0012_drafts_decisions` (szkic + historia decyzji), moduł `backend/app/draft/`
- Drafter LLM (fake / unconfigured / OpenAI-compatible) z walidacją „bez cyfr”
- Auto-szkic po polityce, `POST /draft`, `PUT /draft`, `POST /draft/decision`
- `ReplyDraftSection` z akcjami i historią (historia widoczna także poza ścieżką wyjątku)

**Out of scope:**
- Akceptacja przełożonego i egzekwowanie ról (S-08)
- Prawdziwa wysyłka, szkic dla zapytań standardowych
- Dowolny produkt z katalogu, dodawanie/usuwanie linii, cofanie decyzji

## Architecture / Approach

Nowy etap `draft` na wzór `policy`: czysty rdzeń (`offer.py`: oferta, edycja, wejście polityki, render
treści), drafter jak rekomender, serwis z pinem do `recommended_at` i `lock_analysis`. Hook szkicu idzie po
polityce w tych samych miejscach łańcucha i nie nadpisuje szkicu tej samej wersji rekomendacji. Decyzje
dopisują wiersz historii ze snapshotem oferty i werdyktu; `AnalysisView` dostaje `draft` i `decisions`.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Model danych i rdzeń oferty | Tabele, schematy, edycja i rabat w ofercie, render e-maila | Zmiana `evaluate_discount` musi zostawić S-06 bez zmian |
| 2. Drafter LLM i etap szkicu | Auto-szkic po polityce, regeneracja, widok | Przekazanie `drafter` przez cały łańcuch hooków |
| 3. Decyzje handlowca | Edit / Approve / Reject z historią i 409 | Spójność statusu i historii pod blokadą |
| 4. Frontend i wdrożenie | `DraftSection`, deploy na Render | Groq może zwracać cyfry → częsty tekst zapasowy |

**Prerequisites:** S-06 wdrożone (jest), Docker lokalnie, klucz Groq na Render.
**Estimated effort:** 4 fazy, podobnie jak S-06 plus jedna faza decyzji.
