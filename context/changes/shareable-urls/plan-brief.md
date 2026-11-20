# Shareable URLs — brief planu

> [Pełny plan](plan.md)

## What & Why

S-17 pozwala wysłać współpracownikowi adres konkretnego widoku sprawy. Udostępniony link odtwarza krok, który handlowiec oglądał podczas kopiowania adresu.

## Starting Point

Skrzynka, zapytanie, kolejka, strona systemowa i inspektor już mają adresy. Link do zapytania gubi oglądany krok po odświeżeniu. Istniejące logowanie zachowuje otwarty adres.

## Desired End State

Gdy sprawa jest na etapie Odpowiedź, link do oglądanych Wariantów otwiera Warianty. Gdy krok stał się niedostępny, aplikacja otwiera bieżący krok, poprawia adres i informuje o zmianie. Link do inspektora zachowuje kontekst po zamknięciu.

## Key Decisions Made

| Decyzja | Wybór | Powód |
| --- | --- | --- |
| Krok w adresie | Oglądany krok, w tym ukończony | Link odtwarza widok nadawcy. |
| Krok niedostępny | Bieżący krok, korekta adresu i krótki komunikat PL/EN | Odbiorca wie, dlaczego widzi inny panel. |
| Wstecz i Dalej | Ręczna zmiana dodaje wpis. Zmiana automatyczna zastępuje wpis. | Historia odtwarza kroki wybrane przez użytkownika. |
| Powrót po zalogowaniu | Logowanie pod żądanym adresem | Istniejący mechanizm zachowuje ścieżkę i parametr. |

## Scope

- Adres kroku, historia przeglądarki i powrót z inspektora.
- Weryfikacja odświeżenia, wejścia bez sesji i dostępu zależnego od roli.
- Poza zakresem pozostają dedykowana trasa logowania, zmiany uprawnień, nowe API, migracje danych i przycisk kopiowania.

## Architecture / Approach

Routing przechowuje `step`, a model analizy wyznacza dostępne kroki. Na przykład `/inquiries/42?step=variants` wskazuje Warianty, a `/inquiries/42/run?step=variants` otwiera inspektor w tym samym kontekście. Aplikacja koryguje adres po pomyślnym odczycie analizy.

## Phases at a Glance

| Faza | Rezultat | Ryzyko do sprawdzenia |
| --- | --- | --- |
| 1. Krok zapytania w URL | Udostępnianie, odświeżanie i historia panelu. | Zmiana adresu podczas ładowania albo utrata lokalnych edycji. |
| 2. Inspektor i wejścia z linków | Zachowanie kroku przy zamknięciu inspektora i powrót po logowaniu. | Utrata kontekstu w nowej sesji albo błędna obsługa roli. |

**Prerequisites** S-12 i S-15. Do kontroli ręcznej potrzebna jest zbudowana aplikacja z przykładową sprawą i kontami obu ról.

**Estimated effort** Dwie sesje implementacji z weryfikacją po każdej fazie.

## Open Risks & Assumptions

- Stan sprawy może się zmienić między skopiowaniem i otwarciem adresu. Kryteria obejmują link do kroku, który stał się niedostępny.
- Weryfikacja logowania i odświeżenia obejmuje zbudowaną aplikację, gdzie adresy obsługuje serwer SPA.

## Success Criteria (Summary)

- Link do ukończonych Wariantów otwiera Warianty. Wstecz wraca do Odpowiedzi po ręcznym przełączeniu.
- Niedostępny krok prowadzi do bieżącego panelu z wyjaśnieniem i zaktualizowanym adresem.
- Logowanie przywraca widok zgodnie z adresem i rolą. Zamknięcie inspektora przywraca kontekst zapytania.

## References

- [FR-020](../../foundation/prd.md)
- [S-17 w roadmapie](../../foundation/roadmap.md)
