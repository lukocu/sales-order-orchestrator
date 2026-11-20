# Shareable URLs — plan implementacji

## Overview

S-17 realizuje FR-020. Użytkownik może udostępnić adres zapytania wraz z oglądanym krokiem albo otworzyć bezpośrednio inspektor, skrzynkę, kolejkę lub stronę systemową.

## Current State Analysis

Skrzynka, zapytanie, inspektor, kolejka i strona systemowa mają trasy. Krok oglądany przez użytkownika jest dziś stanem lokalnym panelu i po odświeżeniu wraca do kroku wynikającego ze stanu sprawy. Logowanie wyświetla się pod żądanym adresem, a serwer produkcyjny obsługuje wejścia bezpośrednie do SPA.

## Desired End State

Jeśli sprawa jest na etapie Odpowiedź, adres skopiowany po otwarciu ukończonych Wariantów otwiera Warianty. Gdy zapisany krok jest zablokowany albo nie dotyczy sprawy, aplikacja otwiera bieżący krok, zastępuje adres i wyświetla krótkie wyjaśnienie. Ręczna zmiana tworzy wpis historii. Otwarcie inspektora przenosi kontekst kroku także między sesjami.

### Key Discoveries:

- `frontend/src/router.tsx:17` i `frontend/src/components/InboxRoute.tsx:12` utrzymują wspólną skrzynkę dla listy i szczegółów.
- `frontend/src/components/inquirySteps.ts:34` wyprowadza dostępność kroków z analizy. `frontend/src/components/AnalysisPanel.tsx:299` przechowuje oglądany krok i śledzi zmiany przebiegu.
- `frontend/src/App.tsx:117` udostępnia trasę po uwierzytelnieniu. `frontend/src/components/SupervisorRoutes.tsx:9` ogranicza widoki akceptacji do przełożonego. `backend/app/main.py:33` udostępnia powłokę SPA pod bezpośrednimi adresami.

## What We're NOT Doing

Poza zakresem są dedykowana trasa logowania, zmiany uprawnień, nowe API, migracje danych i osobny przycisk kopiowania. Użytkownik kopiuje adres z przeglądarki.

## Implementation Approach

Parametr `step` przechowuje identyfikator oglądanego kroku: `inquiry`, `variants`, `approval` lub `reply`. Te same identyfikatory działają w obu językach. Analiza wyznacza bieżący krok i dostępność zapisanych kroków. Kanonizację wykonuj dopiero po pomyślnym odczycie analizy, także gdy odpowiedź potwierdza jej brak. Zachowaj pierwotny adres podczas logowania, ładowania i błędu odczytu.

## Phase 1: Krok zapytania w URL

### Overview

Zapis kroku w adresie i odtwarzanie ręcznych zmian w historii.

### Changes Required:

#### 1. Trasa i panel zapytania

**File** `frontend/src/router.tsx`, `frontend/src/components/InboxRoute.tsx`, `frontend/src/components/AnalysisPanel.tsx`, `frontend/src/components/inquirySteps.ts`

**Intent** Powiąż panel z adresem. Użyj istniejącego modelu kroków do oceny, czy krok z linku jest dostępny.

**Contract** `/inquiries/42?step=variants` otwiera Warianty w stanie `done` lub `active`. Brak parametru wybiera bieżący krok i uzupełnia adres. Nieznana wartość, `locked` i `not_needed` kierują do bieżącego kroku z komunikatem. Uzupełnienie i korekta zastępują wpis historii. Ręczna zmiana kroku dodaje wpis. Zmiany przebiegu po akcjach nadal wybierają nowy bieżący krok, zastępują wpis i zachowują istniejące komunikaty. Wstecz i Dalej odczytują URL zgodnie z aktualną dostępnością kroku. Zmiana samego kroku zachowuje instancję panelu, lokalne edycje i odczytaną analizę.

#### 2. Tekst awaryjny i przykłady widoków

**File** `frontend/src/i18n/locales/pl.json`, `frontend/src/i18n/locales/en.json`, `frontend/src/kitchen-sink.tsx`

**Intent** Wyjaśnij otwarcie bieżącego kroku językiem zrozumiałym dla użytkownika.

**Contract** Komunikat korzysta z `t()` oraz obszaru statusu dostępnego dla czytników ekranu. Kitchen sink obejmuje przypadek adresu wskazującego niedostępny krok.

#### 3. Testy kroku i historii

**File** `frontend/src/components/AnalysisPanel.test.tsx`, `frontend/src/App.test.tsx`

**Intent** Zweryfikuj adres i widoczny panel w tych samych scenariuszach.

**Contract** Użyj istniejącego routera pamięciowego i fixture analizy. Pokryj również pustą analizę, opóźniony odczyt, zablokowany krok oraz standardową sprawę, dla której późniejsze kroki nie mają zastosowania.

### Success Criteria:

#### Automated Verification:

- Testy frontendu potwierdzają odtworzenie oglądanych Wariantów, wybór bieżącego kroku dla starszego adresu oraz obsługę nieznanej wartości parametru.
- Testy frontendu potwierdzają zastąpienie adresu niedostępnego kroku, komunikat oraz zachowanie istniejących przejść po zmianie stanu sprawy.
- Testy nawigacji potwierdzają historię Wstecz i Dalej oraz zachowanie niezapisanych zmian bez ponownego pobrania analizy podczas ręcznego przełączania kroków tej samej sprawy.
- Przechodzą npm run lint, npm run typecheck i npm test w katalogu frontend.

#### Manual Verification:

- W sprawie na etapie Odpowiedź otwórz ukończone Warianty, odśwież adres i sprawdź panel Wariantów. W historii bez odświeżenia Wstecz przywraca Odpowiedź, a Dalej Warianty.
- Otwórz dawny link do Odpowiedzi po ponownej analizie. Sprawdź bieżący panel, skorygowany URL i krótkie wyjaśnienie po polsku i angielsku.

## Phase 2: Inspektor i wejścia z linków

### Overview

Zachowaj oglądany krok w inspektorze i potwierdź pełną ścieżkę od udostępnionego adresu do widoku.

### Changes Required:

#### 1. Inspektor i powrót do zapytania

**File** `frontend/src/router.tsx`, `frontend/src/components/AnalysisPanel.tsx`, `frontend/src/components/AnalysisPanel.test.tsx`

**Intent** Zachowaj widok zapytania pod inspektorem po otwarciu i zamknięciu, także po wejściu bezpośrednim.

**Contract** `/inquiries/42/run?step=variants` otwiera inspektor z kontekstem Wariantów. Przycisk zamknięcia i Escape prowadzą do `/inquiries/42?step=variants`, jeśli krok jest dostępny, z zachowaniem istniejącego przywracania fokusu. Starszy adres `/inquiries/42/run` wybiera bieżący krok po odczycie; korekta podczas otwartego inspektora zachowuje trasę `/run`. Trasy inspektora akceptacji zachowują kontekst kolejki i ograniczenia roli.

#### 2. Logowanie, sesja i uprawnienia

**File** `frontend/src/App.test.tsx`, `frontend/src/components/SupervisorQueue.test.tsx`

**Intent** Pokryj istniejący kontrakt logowania pod otwartym adresem i sprawdź dostęp do udostępnionych widoków zgodnie z rolą.

**Contract** Przed uwierzytelnieniem nie są montowane chronione widoki. Po zalogowaniu ta sama ścieżka i parametr sterują wyświetlanym widokiem. Po odpowiedzi 401 ponowne uwierzytelnienie przywraca widok według tego adresu i aktualnej dostępności kroku. Handlowiec otrzymuje istniejący komunikat odmowy pod adresem kolejki; przełożony widzi kolejkę.

### Success Criteria:

#### Automated Verification:

- Testy frontendu potwierdzają zachowanie kroku przy otwarciu inspektora, zamknięciu bezpośrednio otwartego inspektora oraz obsługę starszych adresów /run.
- Testy frontendu potwierdzają odtworzenie adresu po zalogowaniu i wygaśnięciu sesji oraz poprawną odmowę dostępu do kolejki dla handlowca.
- Przechodzą npm run lint, npm run typecheck, npm test i npm run build w katalogu frontend.

#### Manual Verification:

- W zbudowanej aplikacji otwórz i odśwież adresy skrzynki, zapytania, inspektora, kolejki i strony systemowej. W nowym oknie bez sesji sprawdź powrót do kroku po logowaniu oraz dostęp do kolejki dla obu ról.
- Zamknij inspektor otwarty z zapytania przyciskiem lub Escape i sprawdź panel oraz fokus. Powtórz z adresem inspektora wklejonym do nowej karty.

## Testing Strategy

### Unit Tests:

- Sprawdź dopuszczalne wartości `step` i rozstrzygnięcie kombinacji stanu sprawy oraz żądanego kroku.

### Integration Tests:

- Użyj routera pamięciowego i istniejącej infrastruktury testów aplikacji do zweryfikowania widoku, parametru, historii, sesji i ról.
- Przy bezpośrednim wejściu sprawdź, że adres pozostaje bez zmian do otrzymania danych i że nawigacja po krokach nie pobiera ponownie analizy.

### Manual Testing Steps:

1. Wykonaj scenariusze fazy 1 na sprawie na etapie Odpowiedź i po ponownej analizie.
2. Wykonaj scenariusze fazy 2 w zbudowanej aplikacji, używając osobnych sesji handlowca i przełożonego. Sprawdź widok, adres, stan dostępności i fokus.

## Performance Considerations

Parametr kroku jest stanem nawigacji. Odczyt analizy pozostaje powiązany z identyfikatorem sprawy i istniejącym mechanizmem ponawiania. Inspektor korzysta z już odczytanej analizy.

## Migration Notes

Dotychczasowe ścieżki pozostają poprawne. Link bez `step` rozwiązuje się do bieżącego kroku, gdy dostępne są dane. Parametr pozostaje wskazówką nawigacyjną, więc wycofanie zmiany nie wymaga przepisania zapisanych danych.

## References

- [FR-020 i role](../../foundation/prd.md#access-control)
- [S-17 w roadmapie](../../foundation/roadmap.md#s-17-adresy-url-do-zapytań-kroków-i-widoków)
- [Model kroków S-12](../../archive/2026-11-16-inquiry-steps/plan.md)
- `frontend/src/test/renderWithRouter.tsx`, `backend/tests/test_spa.py:21`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Krok zapytania w URL

#### Automated

- [x] 1.1 Testy frontendu potwierdzają odtworzenie oglądanych Wariantów, wybór bieżącego kroku dla starszego adresu oraz obsługę nieznanej wartości parametru. — 641a353
- [x] 1.2 Testy frontendu potwierdzają zastąpienie adresu niedostępnego kroku, komunikat oraz zachowanie istniejących przejść po zmianie stanu sprawy. — 641a353
- [x] 1.3 Testy nawigacji potwierdzają historię Wstecz i Dalej oraz zachowanie niezapisanych zmian bez ponownego pobrania analizy podczas ręcznego przełączania kroków tej samej sprawy. — 641a353
- [x] 1.4 Przechodzą npm run lint, npm run typecheck i npm test w katalogu frontend. — 641a353

#### Manual

- [x] 1.5 W sprawie na etapie Odpowiedź otwórz ukończone Warianty, odśwież adres i sprawdź panel Wariantów. W historii bez odświeżenia Wstecz przywraca Odpowiedź, a Dalej Warianty. — 641a353
- [x] 1.6 Otwórz dawny link do Odpowiedzi po ponownej analizie. Sprawdź bieżący panel, skorygowany URL i krótkie wyjaśnienie po polsku i angielsku. — 641a353

### Phase 2: Inspektor i wejścia z linków

#### Automated

- [ ] 2.1 Testy frontendu potwierdzają zachowanie kroku przy otwarciu inspektora, zamknięciu bezpośrednio otwartego inspektora oraz obsługę starszych adresów /run.
- [ ] 2.2 Testy frontendu potwierdzają odtworzenie adresu po zalogowaniu i wygaśnięciu sesji oraz poprawną odmowę dostępu do kolejki dla handlowca.
- [ ] 2.3 Przechodzą npm run lint, npm run typecheck, npm test i npm run build w katalogu frontend.

#### Manual

- [ ] 2.4 W zbudowanej aplikacji otwórz i odśwież adresy skrzynki, zapytania, inspektora, kolejki i strony systemowej. W nowym oknie bez sesji sprawdź powrót do kroku po logowaniu oraz dostęp do kolejki dla obu ról.
- [ ] 2.5 Zamknij inspektor otwarty z zapytania przyciskiem lub Escape i sprawdź panel oraz fokus. Powtórz z adresem inspektora wklejonym do nowej karty.
