# Komunikaty biznesowe i błędy API — Plan Brief

> Pełny plan: [plan.md](plan.md)

## What & Why

Użytkownik ma rozumieć wyniki i błędy w wybranym języku PL/EN.
S-16 obejmuje sprawdzenia, powody polityki i sygnały pewności.
Użytkownik rozszerzył zakres o błędy API: odbiorcą jest osoba nietechniczna.

## Starting Point

Sprawdzenia są już tłumaczone po kodach. Polityka pokazuje angielskie powody,
a sygnały pewności mają polskie etykiety z częścią danych tylko w tekście.
Błędy żądań często trafiają do UI jako surowe message lub detail.
Część logiki konfliktów zależy od brzmienia tych zdań.

## Desired End State

Komunikaty biznesowe zachowują szczegóły i zmieniają język natychmiast.
Błąd wyjaśnia sytuację oraz następny krok bez słownictwa technicznego.
Zmiana języka nie ponawia operacji i nie modyfikuje historii.

## Key Decisions Made

| Decyzja | Wybór | Dlaczego | Źródło |
| --- | --- | --- | --- |
| Języki i miejsce tłumaczenia | PL/EN przy renderowaniu | Zachowanie danych i historii | FR-021 |
| Stare zapisy | Ogólny opis po kodzie | Bez analizy dawnych zdań i migracji | Użytkownik |
| Nieznany opis biznesowy | Oryginalny tekst | Zachowanie dostępnej informacji | Użytkownik |
| Nowe komunikaty | Kody powodów i pełne parametry | Daty, ilości i produkty pozostają widoczne | Użytkownik |
| Zakres błędów | Wszystkie obecne żądania API | Użytkownik nietechniczny potrzebuje dalszego kroku | Użytkownik |
| Nieznany błąd API | Lokalny komunikat ogólny | Surowy wyjątek nie pomaga odbiorcy | Zatwierdzone fazy |
| Kompatybilność | Opcjonalne pola i zachowane detail | Stare JSONB i klienci nadal działają | Lessons / badanie |
| Niepewny zapis | Najpierw sprawdź aktualny stan | Utrata odpowiedzi nie oznacza braku zapisu | Plan |

## Scope

**In scope:** wspólne tłumaczenia biznesowe, kody błędów HTTP, klient health,
logowanie i sesja, konflikty, walidacja, odmowa dostępu, wszystkie obecne widoki,
testy legacy i zmiany języka.

**Out of scope:** tłumaczenie maili, szkicu, komentarzy i uzasadnienia modelu;
przepisywanie snapshotów; automatyczne ponawianie zapisów; tłumaczenie
zapisanych technicznych błędów etapów w inspektorze.

## Architecture / Approach

Backend dodaje reason_code, parametry sygnałów oraz code/params błędów HTTP.
Frontend waliduje te dane i tłumaczy deskryptory przy renderowaniu.
Wspólne formatowanie obejmuje tabelę polityki, ryzyka i ocenę przełożonego.
Znane stare błędy detail są obsługiwane przejściowo w jednym miejscu klienta.

## Phases at a Glance

| Faza | Co dostarcza | Główne ryzyko |
| --- | --- | --- |
| 1. Kontrakty komunikatów i błędów | Kody i parametry z kompatybilnością | Ścisłe modele zagnieżdżonego JSONB |
| 2. Tłumaczenie komunikatów biznesowych | Szczegółowe nowe i ogólne stare opisy PL/EN | Niepełne dane historyczne |
| 3. Zrozumiałe błędy w interfejsie | Sytuacja, dalszy krok i bezpieczne zachowanie | Konflikty i niepewny wynik zapisu |

**Prerequisites:** istniejące i18n, widoki S-12/S-15; Docker do pełnych bramek backendu.
**Estimated effort:** orientacyjnie 3–5 sesji; rozszerzenie błędów dotyka wielu widoków.

## Open Risks & Assumptions

- Stare zapisy nie zawsze pozwalają odtworzyć szczegół; ogólny opis jest świadomym wyborem.
- Błędy muszą zachować działanie 401 i 409 oraz pusty stan braku analizy.
- Logi zachowują diagnostykę; komunikaty UI nie ujawniają surowych wyjątków.

## Success Criteria (Summary)

- Oba języki działają dla danych nowych i historycznych bez zmiany historii.
- Błędy wskazują bezpieczny dalszy krok i zmieniają język bez ponawiania operacji.
- Bramki backendu i frontendu oraz sprawdzenie ról, konfliktów i utraty połączenia przechodzą.