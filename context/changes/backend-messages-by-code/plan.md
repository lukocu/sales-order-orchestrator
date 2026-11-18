# Komunikaty biznesowe i błędy API w PL/EN — plan implementacji

## Overview

S-16: użytkownik czyta wyniki sprawdzeń, powody polityki, sygnały pewności oraz błędy API w wybranym języku. Błędy wyjaśniają sytuację i możliwy następny krok osobie nietechnicznej. Plan uzgodniony 2026-11-18: MEDIUM, cztery pytania i trzy zatwierdzone fazy.

## Current State Analysis

- Sprawdzenia mają statusy, kody powodów i dane liczbowe: `backend/app/checks/schema.py:15`; `frontend/src/components/ChecksSection.tsx:47` już tłumaczy powody. Potrzebne potwierdzenie pokrycia, nie nowy model komunikatów sprawdzeń.
- `backend/app/policy/schema.py:29` przechowuje kod reguły i angielski reason. Kod reguły z werdyktem nie odróżnia przyczyn: `backend/app/policy/rules.py:116` ma wiele powodów braku oceny rabatu; kredyt zablokowany i przekroczony limit dają fail.
- `backend/app/recommendation/schema.py:47` ma kod sygnału i polski label. `confidence.py:67,133,147` wpisuje produkt, ilości i daty do tekstu bez kompletnych parametrów strukturalnych.
- Surowe teksty renderują `PolicySection.tsx:148`, `SupervisorReview.tsx:194,247` i `VariantComparison.tsx:72,202`.
- `frontend/src/api/client.ts:23` odczytuje tekst detail i techniczne msg walidacji. `components/format.ts:52` zwraca Error.message; kilka widoków omija ten helper.
- `AnalysisPanel.tsx:115` rozpoznaje konflikt przez tekst DRAFT_CHANGED; `Inbox.tsx:77` podobnie rozpoznaje niedostępność skrzynki. Kody muszą zachować skutki tych rozróżnień.
- `api/health.ts` ma oddzielny klient; `SystemPage.tsx:53` pokazuje jego błędy. Logowanie odróżnia błędne dane od wygaśnięcia sesji.
- Modele JSONB mają extra=forbid. Reguła `context/foundation/lessons.md` wymaga migracji albo opcjonalnych pól z wartościami domyślnymi również w szkicach i historii decyzji.

## Desired End State

1. Nowe powody polityki mają jednoznaczne kody; nowe sygnały zachowują wszystkie szczegóły przez parametry. Frontend tłumaczy po kodzie, nie analizuje reason/label.
2. Wszystkie obecne miejsca prezentacji tych danych korzystają ze wspólnego formatowania, także edytowana oferta i przegląd przełożonego.
3. Stare rozpoznane kody otrzymują ogólne tłumaczenie z dostępnych danych. Brak danych nie prowadzi do zgadywania przyczyny, produktu ani historycznego terminu.
4. Zupełnie nieznany kod opisu biznesowego pokazuje oryginalny reason/label. Nieznany błąd API pokazuje lokalny komunikat ogólny z bezpiecznym następnym krokiem.
5. Błędy API są rozróżniane kodami i kontekstem operacji. Tekst dla użytkownika nie zawiera nazw infrastruktury, wyjątków, statusów HTTP, szczegółów walidatora ani sekretów.
6. Zmiana PL/EN aktualizuje również już widoczne komunikaty i błędy bez ponowienia operacji i bez zapisu danych biznesowych.
7. Mail, szkic, uzasadnienie modelu, komentarz człowieka, werdykty, uprawnienia i progi zachowują swoje znaczenie.

### Key Discoveries

- S-16 i FR-021 określają tłumaczenie przy wyświetlaniu, bez przepisywania JSONB.
- `backend/app/policy/rules.py:95` zachowuje powód rabatu decydującego o wyniku; kod musi podążać za tym samym wyborem.
- Sygnały `compat_full` mogą wystąpić dla różnych produktów; ich parametrów nie wolno przypisywać wyłącznie według kodu.
- `api/analysis.ts:1123` traktuje brak analizy jako stan pusty; nie jest to brak zapytania.
- `backend/app/api/auth.py:113` zwraca własny JSONResponse przy błędzie wylogowania; wspólny kontrakt musi objąć również tę ścieżkę.

## What We're NOT Doing

- Tłumaczenie maili, szkicu odpowiedzi, tekstu modelu i komentarzy człowieka.
- Przepisywanie zapisanych tekstów, historii i snapshotów ani ponowna ocena historycznej polityki.
- Tłumaczenie zapisanych błędów etapów w inspektorze diagnostycznym; obejmujemy błędy jego żądań HTTP.
- Automatyczne ponawianie zapisów, nowy system powiadomień, nowe języki, zmiana procesu akceptacji.
- Rozszerzanie ukrytej listy `draft.why.signals` tylko na potrzeby tłumaczenia.

## Implementation Approach

Najpierw dodać kompatybilne dane identyfikujące komunikaty i błędy. Następnie podłączyć wspólne formatowanie biznesowe. Na końcu przenieść prezentację błędów na tłumaczenie przy renderowaniu i zachować obsługę konfliktów, sesji oraz stanów pustych.

### Uzgodnione decyzje

| Obszar | Decyzja |
| --- | --- |
| Stare zapisy | Ogólne tłumaczenie po dostępnych kodach; bez rozpoznawania dawnych zdań biznesowych |
| Nieznany kod biznesowy | Oryginalny reason/label |
| Nowe komunikaty | Pełne szczegóły przez opcjonalne pola kodów i parametrów |
| Zakres | Sprawdzenia, powody polityki, sygnały pewności oraz błędy API wszystkich obecnych widoków |
| Błędy dla nietechnicznej osoby | Sytuacja i następny krok; nieznane błędy bez surowych szczegółów |
| Stary kontrakt API | Zachować detail i status; przejściowe rozpoznanie znanych dawnych detail tylko w kliencie błędów |

## Critical Implementation Details

### Zgodność i dane historyczne

Nowe pola modeli JSONB mają wartości domyślne; reason i label pozostają wymagane tak jak obecnie. Nie uzupełniać snapshotów z bieżących danych analizy. Dla starego powodu polityki bez identyfikatora pokazać ogólny opis reguły i werdyktu, bez przypisania konkretnej brakującej wartości.

### Wynik zapisu przy błędzie połączenia

Utrata odpowiedzi nie dowodzi nieudanego zapisu. Przy decyzji, korekcie i przekazaniu komunikat zaleca sprawdzenie aktualnego stanu przed ponowieniem. Nie dodawać automatycznego retry ani akcji, która może powtórzyć decyzję.

## Phase 1: Kontrakty komunikatów i błędów

### Overview

Backend dostarcza identyfikatory i pełne dane potrzebne do tłumaczenia, zachowując dotychczasowych odbiorców.

### Changes Required:

#### 1. Powody polityki

**Files**: `backend/app/policy/schema.py`, `backend/app/policy/rules.py`, testy reguł i decyzji.

**Intent**: Odróżnić każdą rzeczywistą przyczynę wyniku, również dla edytowanej oferty.

**Contract**: RuleResult otrzymuje opcjonalne `reason_code` domyślnie null. Stabilne kody obejmują wszystkie gałęzie reguł: brak danych/progu, typ rabatu i przekroczenie lub spełnienie warunku, kredyt zablokowany i limit. Zachować reason, wartości, werdykt i wybór decydującej reguły. Dokumentować katalog kodów razem z testami pokrycia wszystkich gałęzi.

#### 2. Parametry sygnałów pewności

**Files**: `backend/app/recommendation/schema.py`, `backend/app/recommendation/confidence.py`, testy pewności i serializacji.

**Intent**: Umożliwić pełne tłumaczenie ilości, dat i produktów bez parsowania etykiet.

**Contract**: Signal otrzymuje `params` z domyślnym pustym obiektem; dozwolone wartości to proste liczby i ciągi. Znane kody określają wymagane nazwy i typy parametrów. Pokrycie niesie covered/requested; opóźnienie fulfilled_on/deadline w ISO; zgodność product_code. Zachować obecne code, polarity, label i obliczenia band. Kody z sufiksem pola lub kompetencji pozostają kompatybilne.

#### 3. Kody błędów HTTP

**Files**: `backend/app/api/errors.py`, `backend/app/main.py`, `backend/app/api/{analysis,auth,inquiries,mailbox,runs,supervisor}.py`, `backend/app/auth/deps.py`, testy API.

**Intent**: Pozwolić klientowi rozpoznać błąd niezależnie od angielskiego zdania.

**Contract**: Odpowiedzi błędów zachowują status i dotychczasowe detail, dodają top-level `code` i opcjonalne `params`. Identyfikować błędy przy źródle; nie mapować dowolnych wyjątków przez str(exception). Pokryć brak sesji, błędne dane logowania, odmowę roli, brak zasobu, wymagany komentarz/niepoprawne dane, konflikty wersji i blokady akceptacji, ograniczenia decyzji, brak wymaganego etapu, zajętą skrzynkę, niedostępność usług i nieudany etap. Obsłużyć błędy walidacji żądania, nieznane trasy API oraz JSONResponse wylogowania. Parametry mają być jawnie dozwolone i pozbawione treści haseł, maili i wyjątków. Zachować nagłówki i cookie odpowiedzi; nie osłabiać obecnego logowania błędów. Nieoczekiwany 500 otrzymuje ogólny kod, a oryginalny błąd pozostaje widoczny w logach.

### Success Criteria:

#### Automated Verification:

- Wszystkie gałęzie polityki i dynamiczne sygnały mają poprawne kody/parametry bez zmiany wyników liczbowych i werdyktów.
- Stare i nowe JSONB rekomendacji, polityki, szkiców i historii decyzji są odczytywane; odczyt nie zmienia zapisanych danych.
- Błędy API zachowują status/detail, dodają poprawne kody i nie ujawniają w params poufnych danych; walidacja, auth i wylogowanie mają pokrycie.
- Pełne bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`.

## Phase 2: Tłumaczenie komunikatów biznesowych

### Overview

Wspólne formatowanie PL/EN obsługuje nowe szczegółowe komunikaty i stare zapisy.

### Changes Required:

#### 1. Kontrakty klienta i formatowanie

**Files**: `frontend/src/api/analysis.ts`, `frontend/src/components/policyLabels.ts`, nowy `frontend/src/components/businessMessages.ts`, `frontend/src/i18n/locales/{pl,en}.json`.

**Intent**: Tłumaczyć rozpoznane komunikaty po kodach z zachowaniem ich szczegółów i kompatybilności.

**Contract**: Walidatory akceptują brak nowych pól w starym payloadzie; sprawdzają typy nowych pól. Formatter przyjmuje t i dane, nie zapisuje przetłumaczonych zdań. Znany kod z niepełnymi parametrami daje ogólne tłumaczenie bez undefined/null i bez zgadywania. Nieznany kod biznesowy daje oryginalny tekst. Rozpoznane sufiksy kompetencji/pól mają tłumaczone nazwy. Daty i liczby używają języka interfejsu. Interpolacja pozostaje tekstem React.

#### 2. Wszystkie widoki biznesowe

**Files**: `PolicySection.tsx`, `SupervisorReview.tsx`, `VariantComparison.tsx`, testy tych widoków, `ChecksSection.test.tsx`, `frontend/src/kitchen-sink.tsx`.

**Intent**: Zachować spójne opisy w tabelach, podsumowaniu ryzyk i rozwijanych szczegółach.

**Contract**: Wszystkie obecne bezpośrednie renderowania rule.reason i signal.label przechodzą przez wspólny formatter. Historia i edytowane oferty używają swoich zapisanych danych. Sprawdzenia zachowują istniejące tłumaczenia; testy potwierdzają kompletność. Uzasadnienie modelu i treści użytkowników pozostają oryginalne.

### Success Criteria:

#### Automated Verification:

- Testy PL/EN obejmują wszystkie kody powodów i sygnałów, dynamiczne parametry, niepełne stare zapisy i fallback nieznanych kodów.
- Zmiana języka aktualizuje tabelę polityki, uwagę przełożonego oraz obie prezentacje ryzyk bez zapisu lub ponownego pobrania danych.
- Bramki frontendu przechodzą: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`; zgodność kluczy PL/EN jest zachowana.

#### Manual Verification:

- W obu językach sprawdzenia, rekomendacja i ocena edytowanej oferty pokazują właściwe ilości, daty i produkty; mail, szkic, komentarz i uzasadnienie modelu zachowują treść.

## Phase 3: Zrozumiałe błędy w interfejsie

### Overview

Każda obecna ścieżka błędu żądania API pokazuje zrozumiały komunikat i bezpieczny następny krok.

### Changes Required:

#### 1. Wspólne deskryptory i tłumaczenia błędów

**Files**: `frontend/src/api/client.ts`, `frontend/src/api/health.ts`, `frontend/src/components/format.ts`, nowy `frontend/src/api/errorMessages.ts`, zasoby PL/EN, testy klienta.

**Intent**: Oddzielić identyfikację błędu od jego prezentacji i zachować odświeżanie języka.

**Contract**: ApiError i UnauthorizedError zachowują status oraz diagnostyczny message, dodają code/params. Klient ma kody dla braku połączenia, niepoprawnej odpowiedzi i nieznanej odpowiedzi HTTP. Znane dawne detail można przejściowo mapować tylko w tej warstwie; nie tłumaczyć dowolnego tekstu. UI przechowuje deskryptor błędu i tłumaczy przy renderowaniu. Health korzysta z tego samego kontraktu. AbortError nie staje się błędem dla użytkownika. Nieznany błąd API lub zwykły Error daje bezpieczny komunikat ogólny, bez raw message. Zachować null analizy jako poprawny stan pusty.

#### 2. Widoki i dalsze kroki

**Files**: `App.tsx`, `LoginForm.tsx`, `Inbox.tsx`, `AnalysisPanel.tsx`, `ChecksSection.tsx`, `OrchestrationSection.tsx`, `RecommendationSection.tsx`, `PolicySection.tsx`, `ReplyDraftSection.tsx`, `SupervisorReview.tsx`, `SupervisorQueue.tsx`, `supervisorQueue.tsx`, `RunInspector.tsx`, `SystemPage.tsx`, powiązane testy.

**Intent**: Usunąć surowe techniczne błędy żądań i zapewnić dalszy krok właściwy dla operacji.

**Contract**: Komunikaty rozróżniają: popraw dane logowania; zaloguj ponownie; brak uprawnień; wróć do listy, gdy brak sprawy; uzupełnij wymagane dane; odśwież zmienioną sprawę; poczekaj na decyzję przełożonego; spróbuj odczytu ponownie; skontaktuj się z administratorem, gdy wymagana jest konfiguracja. Dla niepewnego wyniku zapisu sprawdź stan przed powtórzeniem. Własne zatwierdzenie i brak aktualności mają odrębne objaśnienia. Zastąpić porównania error.message kodami, zachowując obecne odświeżenie po konflikcie i ochronę edycji. SupervisorReview nie opisuje 403/422/5xx jako problemu sieci. Zachować treść wprowadzonych formularzy, o ile stan i uprawnienia nadal pozwalają na ich użycie. Komunikaty korzystają z istniejących alertów/statusów i fokusów. Techniczne zapisane błędy etapów pozostają w inspektorze.

#### 3. Dokumentacja i scenariusze weryfikacji

**Files**: `README.md`, `frontend/src/kitchen-sink.tsx`, testy API/komponentów i `context/changes/backend-messages-by-code/change.md`.

**Intent**: Opisać kontrakty i udokumentować rzeczywiście wykonaną weryfikację.

**Contract**: README opisuje fallbacki, kody i kompatybilność. Kitchen sink pokazuje istotne stany błędów i nie trafia do builda produkcyjnego. Używać tokenów i obu locale zgodnie z AGENTS.md. Bez commita ani wdrożenia w ramach samego planowania.

### Success Criteria:

#### Automated Verification:

- Testy klienta pokrywają kody i stare detail, błędne JSON, sieć, anulowanie, 401 logowania/sesji, 403, 404, 409, 422, 429 i 5xx oraz nieznany kod bez ujawnienia raw message.
- Testy widoków zachowują stany puste, konflikty i bezpieczne odświeżanie oraz aktualizują widoczny błąd po PL/EN bez ponowienia żądania.
- Testy decyzji, korekty i przekazania nie powtarzają zapisów po utracie odpowiedzi; nie mylą błędów walidacji, roli i serwera z siecią.
- Pełne bramki backendu i frontendu przechodzą; skan tokenów z AGENTS.md nie wykazuje naruszeń, a kitchen sink jest poza buildem.

#### Manual Verification:

- Osoba nietechniczna otrzymuje opis i następny krok dla błędnego logowania, utraty sesji, braku uprawnień, zmienionej sprawy, oczekiwania na przełożonego i problemu połączenia; treść nie zawiera HTTP, SQL, JSON ani nazw wyjątków.
- W PL/EN i obu motywach alerty są czytelne przy 1440×900 i 375 px; klawiatura i ogłaszanie błędów działają, przełącznik aktualizuje istniejący błąd, a ponowienie odczytu pozwala kontynuować pracę.

## Testing Strategy

### Unit Tests

Katalog powodów i sygnałów ma pokrycie każdej gałęzi producenta. Formatter ma przypadki pełne, legacy, częściowe i nieznane. Klient błędów sprawdza kontrakt oraz kontekst operacji, bez testów zależnych od przypadkowych technicznych zdań.

### Integration Tests

Backend sprawdza błędy tras i zgodność odczytu zagnieżdżonego JSONB, także snapshotów. Frontend sprawdza rzeczywiste renderowanie w widokach handlowca i przełożonego oraz zmianę języka przy widocznym błędzie. Ścieżki 401/409 i utrata odpowiedzi zapisu są obowiązkowe.

### Manual Testing Steps

1. Otwórz standardowe i wyjątkowe zapytanie; przełącz PL/EN przy widocznych wynikach.
2. Porównaj rekomendację, edytowaną ofertę i ocenę przełożonego, w tym historyczne dane.
3. Wywołaj kontrolowane odmowy i konflikty; sprawdź opis oraz dalszy krok.
4. Przerwij połączenie podczas odczytu i po wysłaniu zapisu; sprawdź, że UI nie zakłada niepowodzenia zapisu i nie powtarza go automatycznie.
5. Sprawdź login, skrzynkę, kolejkę, inspektor i stronę systemową; wykorzystaj ARIA/DOM przed screenshotami zgodnie z lessons.md.

## Performance Considerations

Tłumaczenie odbywa się lokalnie z zasobów bundlowanych. Brak nowych żądań, pollingu i wywołań modeli. Parametry zwiększają payload tylko o dane konkretnego komunikatu.

## Migration Notes

Brak migracji danych: nowe pola są opcjonalne z domyślnymi wartościami. Zachować reason/label i detail dla poprzednich klientów. Frontend toleruje stary backend w ramach jawnego fallbacku. Wycofanie frontendu nie wymaga cofania danych; walidację starych zagnieżdżonych JSONB należy wykonać przed wdrożeniem backendu.

## References

- `context/foundation/prd.md:139` — FR-021 i ograniczenia tłumaczeń.
- `context/foundation/roadmap.md` — S-16; zakres błędów API rozszerzony przez użytkownika.
- `context/foundation/lessons.md` — JSONB i weryfikacja UI.
- `backend/app/policy/rules.py`, `backend/app/recommendation/confidence.py` — źródła kodów i parametrów.
- `frontend/src/api/client.ts`, `frontend/src/components/format.ts` — obecna prezentacja błędów.
- Decyzje użytkownika z 2026-11-18: cztery odpowiedzi i zatwierdzenie trzech faz.

## Progress

> Jedyna kanoniczna lista wykonania. Dopisz SHA po commicie; plan nie oznacza wykonania weryfikacji.

### Phase 1: Kontrakty komunikatów i błędów

#### Automated

- [x] 1.1 Wszystkie gałęzie polityki i dynamiczne sygnały mają poprawne kody/parametry bez zmiany wyników liczbowych i werdyktów. — 87dee2b
- [x] 1.2 Stare i nowe JSONB rekomendacji, polityki, szkiców i historii decyzji są odczytywane; odczyt nie zmienia zapisanych danych. — 87dee2b
- [x] 1.3 Błędy API zachowują status/detail, dodają poprawne kody i nie ujawniają w params poufnych danych; walidacja, auth i wylogowanie mają pokrycie. — 87dee2b
- [x] 1.4 Pełne bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`. — 87dee2b

### Phase 2: Tłumaczenie komunikatów biznesowych

#### Automated

- [x] 2.1 Testy PL/EN obejmują wszystkie kody powodów i sygnałów, dynamiczne parametry, niepełne stare zapisy i fallback nieznanych kodów. — 5c17a39
- [x] 2.2 Zmiana języka aktualizuje tabelę polityki, uwagę przełożonego oraz obie prezentacje ryzyk bez zapisu lub ponownego pobrania danych. — 5c17a39
- [x] 2.3 Bramki frontendu przechodzą: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`; zgodność kluczy PL/EN jest zachowana. — 5c17a39

#### Manual

- [x] 2.4 W obu językach sprawdzenia, rekomendacja i ocena edytowanej oferty pokazują właściwe ilości, daty i produkty; mail, szkic, komentarz i uzasadnienie modelu zachowują treść. — 5c17a39

### Phase 3: Zrozumiałe błędy w interfejsie

#### Automated

- [x] 3.1 Testy klienta pokrywają kody i stare detail, błędne JSON, sieć, anulowanie, 401 logowania/sesji, 403, 404, 409, 422, 429 i 5xx oraz nieznany kod bez ujawnienia raw message. — 5c17a39
- [x] 3.2 Testy widoków zachowują stany puste, konflikty i bezpieczne odświeżanie oraz aktualizują widoczny błąd po PL/EN bez ponowienia żądania. — 5c17a39
- [x] 3.3 Testy decyzji, korekty i przekazania nie powtarzają zapisów po utracie odpowiedzi; nie mylą błędów walidacji, roli i serwera z siecią. — 5c17a39
- [x] 3.4 Pełne bramki backendu i frontendu przechodzą; skan tokenów z AGENTS.md nie wykazuje naruszeń, a kitchen sink jest poza buildem. — 5c17a39

#### Manual

- [x] 3.5 Osoba nietechniczna otrzymuje opis i następny krok dla błędnego logowania, utraty sesji, braku uprawnień, zmienionej sprawy, oczekiwania na przełożonego i problemu połączenia; treść nie zawiera HTTP, SQL, JSON ani nazw wyjątków. — 5c17a39
- [x] 3.6 W PL/EN i obu motywach alerty są czytelne przy 1440×900 i 375 px; klawiatura i ogłaszanie błędów działają, przełącznik aktualizuje istniejący błąd, a ponowienie odczytu pozwala kontynuować pracę. — 5c17a39
