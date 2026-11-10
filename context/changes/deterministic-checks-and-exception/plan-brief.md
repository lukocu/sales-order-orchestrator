# S-03 Sprawdzenia bez agentów i wykrycie wyjątku — Plan Brief

> Full plan: `context/changes/deterministic-checks-and-exception/plan.md`

## What & Why

Po analizie zapytania system bez modelu językowego sprawdza klienta, stan, cenę standardową, rabat i status kredytowy na symulowanych danych firmy i klasyfikuje zapytanie: standard kończy się bez agentów (widoczne w UI, 0 tokenów), brak pełnej ilości jest wyjątkiem dla orkiestracji. To dowodzi drugiej połowy tezy produktu — „standard bez agentów” (PRD FR-003, FR-004, US-01).

## Starting Point

S-02 zapisuje jedną bieżącą analizę na zapytanie (pola, niepewności, korekty) w runie tracingu z krokami `parse` i `resolve-deadline`. Danych firmy nie ma; kody produktów i nazwy klientów to tylko tekst z maila. Skrzynka pokazuje listę zapytań bez stanu przetwarzania.

## Desired End State

Po „Analyze request” panel pokazuje sekcję „Checks” z wynikiem: Biuro Max — **Standard, completed without agents** (run z samymi krokami deterministycznymi); ACME, Delta, Omega — **Exception: insufficient stock** (z ilością brakującą i zgodą na zamiennik); braki danych — **Needs input** z powodem. Korekta pól przelicza wynik. Skrzynka ma znacznik wyniku przy każdym zapytaniu.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) |
| --- | --- | --- |
| Typy wyjątków w MVP (Open Roadmap Q4) | Tylko brak pełnej ilości (ilość > stan) | Zgodne z US-01 i agentami S-04; rabat i kredyt ocenia polityka w S-06. |
| Rabat ponad standard, kredyt | Tylko pokazane, bez wpływu na wynik | Nie dublujemy reguł polityki S-06. |
| Dopasowanie klienta | Nazwa z pola (po korekcie, bez form prawnych, całe słowa); przy pustym polu — domena e-maila | Korekta handlowca jest źródłem prawdy (FR-002), puste pole nie blokuje. |
| Moment uruchomienia | Automatycznie po analizie i po zapisie korekt, zawsze we własnym runie; „Re-run checks” przy błędzie | Jedno kliknięcie jak w US-01; run sprawdzeń czysto deterministyczny (0 tokenów także przy Groq) — plan-review F1. |
| Braki danych | Trzeci wynik `needs_input`; niepewne pola tylko ostrzegają | Nie udaje standardu ani wyjątku na złych danych. |
| Widoczność | Panel + znacznik w skrzynce | Teza „standard bez agentów” widoczna na liście. |
| Zapis | Tabela `inquiry_checks` (upsert, wersja analizy, `stale`) | Wzorzec S-02; wynik nowszego runu wygrywa. |
| Dane firmy | Tabele `customers`, `products` z seedem w migracji `0006` | Wzorzec seedu z `0003`; S-04 doda kolejne dane. |

## Scope

**In scope:**
- Tabele i seed danych firmy, tabela wyniku, czysta logika reguł.
- Sprawdzenia jako kroki `deterministic` w tracingu; przeliczenie po korektach; `POST /checks`.
- `checks` w `AnalysisView`, `outcome` na liście zapytań.
- Sekcja „Checks”, znacznik w skrzynce, README, sprawdzenie na Render.

**Out of scope:** inne typy wyjątków, orkiestracja i agenci (S-04), polityka (S-06), edycja danych firmy, termin dostawy, rezerwacja stanu, historia sprawdzeń, waluty i podatki.

## Architecture / Approach

`app/checks/` = modele (customers, products, inquiry_checks) + schemat wyniku (`CheckResults`, JSONB) + czyste reguły (dopasowanie, 5 sprawdzeń, klasyfikacja) + serwis (odczyt danych, kroki w runie, zapis z blokadą wersji analizy, widok). `parsing.service` woła serwis sprawdzeń po zapisie analizy i po korektach (każde wywołanie to nowy run deterministyczny); API zwraca wynik w `AnalysisView`; frontend dodaje `ChecksSection` i znacznik w `Inbox`.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Dane firmowe i logika sprawdzeń | Migracja `0006` z seedem, `app/checks` (schemat, reguły), testy reguł | Dopasowanie klienta do wariantów nazwy z modelu |
| 2. Integracja z analizą i API | Sprawdzenia w runach, zapis z wersją, `POST /checks`, `outcome` na liście | Wyścig analiza/korekta przy zapisie wyniku |
| 3. UI i wdrożenie | Sekcja „Checks”, znacznik w skrzynce, README, Render | Czytelność wyniku na 375 px |

**Prerequisites:** S-02 zarchiwizowane (gotowe); lokalny Docker; dostęp do Render API do sprawdzenia wdrożenia.
**Estimated effort:** ~3 sesje, po jednej na fazę.

## Open Risks & Assumptions

- Groq może zwrócić nazwę klienta w wariancie, którego reguła „całe słowa nazwy z kartoteki” nie złapie — wtedy wynik to `needs_input`, a handlowiec poprawia pole; sprawdzane ręcznie na Render.
- Istniejące analizy na Render nie mają wyniku sprawdzeń do czasu ponownej analizy lub „Re-run checks”.
- Stan nie jest rezerwowany między zapytaniami — świadome ograniczenie MVP.

## Success Criteria (Summary)

- Handlowiec widzi dla każdego zapytania seed wynik zgodny z planem i szczegóły pięciu sprawdzeń.
- Zapytanie standardowe pokazuje „completed without agents” i run sprawdzeń bez tokenów.
- Korekta pól zmienia wynik w panelu i znacznik w skrzynce.
