# Kolejka przełożonego — plan implementacji

## Overview

S-15 z roadmapy: przełożony otwiera „Do akceptacji” z licznikiem w nawigacji i rozstrzyga przekazane sprawy bez przechodzenia przez cały proces handlowca. Widok zaczyna się od reguł wymagających decyzji, ocenianej oferty oraz akcji Zatwierdź / Odrzuć z obowiązkowym komentarzem. Zmiany danych i ponawianie przetwarzania są zablokowane dla obu ról do odrzucenia zgłoszenia.

Plan uzgodniony 2026-11-18. Złożoność: MEDIUM; trzy fazy zaakceptowane przez użytkownika. To dokument planistyczny; nie oznacza implementacji ani wykonania poniższych testów.

## Current State Analysis

- `frontend/src/router.tsx:20` ma wspólny layout skrzynki, adresy zapytań i inspektora oraz `/system`; brak trasy kolejki.
- `frontend/src/components/Inbox.tsx:181` filtruje surowy `draft_status === 'awaiting_supervisor'`. Filtr jest dostępny obu rolom; po decyzji status zmienia się lokalnie, bez ponownego pobrania listy.
- `frontend/src/components/AppNav.tsx:14` zna tylko skrzynkę i system. Nawigacja jest poza `SessionContext.Provider` (`frontend/src/App.tsx:94`, `:116`). Licznik potrzebuje wspólnego źródła danych dostępnego także dla nawigacji.
- `frontend/src/components/ReplyDraftSection.tsx:69` zawiera decyzje przełożonego, obowiązkowe uzasadnienia i zakaz zatwierdzenia własnego zgłoszenia. Układ pokazuje ofertę, politykę i mail przed przyciskami; nie spełnia wymagania decyzji na początku.
- `frontend/src/components/AnalysisPanel.tsx:552` i `:775` udostępnia poprawki oraz ponowienia etapów. Ukrycie edycji szkicu nie blokuje tych ścieżek.
- `backend/app/api/analysis.py:516` i `backend/app/draft/service.py:344` obsługują decyzję przełożonego. Istnieją blokada wiersza analizy, token `updated_at`, kontrola aktualności, cztery oczy i atomowy zapis historii.
- `backend/app/api/analysis.py:187`–`:388` pozwala zalogowanym użytkownikom zmieniać analizę i ponawiać etapy. To główna luka względem S-15.
- `backend/app/api/inquiries.py:24` zwraca surowy status szkicu, także nieaktualnego. Lista jest sortowana według otrzymania maila, a nie przekazania do przełożonego.
- `backend/app/draft/models.py:15` i `:49` przechowują bieżący szkic i historię decyzji. Nie potrzeba nowego statusu ani tabeli zadań kolejki.

Ustalenia S-08 zachowane: kolejka obejmuje tylko przekazane szkice; komentarz jest wymagany przy obu decyzjach; zatwierdzanie własnego zgłoszenia jest zabronione, jego odrzucenie dozwolone; obowiązuje polityka z chwili decyzji. S-15 zastępuje dawną zgodę na ponowne przetwarzanie w trakcie oczekiwania i dodaje osobny widok.

## Desired End State

1. Przełożony ma pozycję „Do akceptacji” z liczbą oczekujących spraw, także na innych stronach aplikacji. Handlowiec nie widzi tej pozycji.
2. `/approvals` pokazuje sprawy od najstarszego przekazania. Wiersz zawiera klienta lub nadawcę, temat, czas przekazania / oczekiwania i reguły wymagające decyzji.
3. `/approvals/$inquiryId` zachowuje kontekst kolejki. Na górze są reguły `fail` i `not_evaluated`, rzeczywista oceniana oferta oraz decyzje z komentarzem. Mail, szkic, pozostałe reguły i historia są niżej, rozwijane i tylko do odczytu.
4. Przekazana oferta może być edycją rekomendacji. Widok ocenia `draft.offer` i politykę tej oferty; nie przedstawia pierwotnego wariantu jako niezmienionej oferty do zatwierdzenia.
5. Obie role mają zablokowane zmiany i ponowienia na `awaiting_supervisor`, również przez bezpośrednie wywołanie API. Przełożony nadal może podjąć decyzję. Po odrzuceniu wracają dotychczasowe możliwości poprawek i generowania nowego szkicu.
6. Nieaktualnego zgłoszenia nie wolno zatwierdzić, ale przełożony może je odrzucić z komentarzem i zachowaniem historycznych danych zgłoszenia.
7. Po decyzji sprawa znika z kolejki i licznika, a wynik z autorem, czasem i komentarzem pozostaje otwarty. Nie następuje automatyczne przejście do następnej sprawy.
8. Dane kolejki odświeżają się przy wejściu, powrocie do widocznej karty, własnej decyzji i ręcznie. Brak pollingu. Domyślnym ekranem po logowaniu pozostaje skrzynka; wskazany URL zostaje zachowany.

### Uzgodnione decyzje

| Obszar | Wybór | Uzasadnienie |
| --- | --- | --- |
| Kolejność | Najstarsze przekazanie pierwsze | Najdłużej oczekujące sprawy nie giną pod nowymi mailami. |
| Odświeżanie | Wejście, powrót do karty, decyzja, ręcznie | Aktualizacja przy pracy użytkownika bez okresowych zapytań. |
| Po decyzji | Pozostaje wynik | Skutek decyzji i komentarz są widoczne przed kolejną sprawą. |
| Poprawki handlowca | Dopiero po odrzuceniu | Stabilny przedmiot oceny i rozdzielona odpowiedzialność. |
| Lista | Powód eskalacji i czas oczekiwania | Ułatwia wybór sprawy bez otwierania szczegółów. |
| Kontekst oceny | Rozwijany poniżej decyzji | Najpierw informacje i działania potrzebne przełożonemu. |
| Ekran startowy | Dotychczasowa skrzynka | Przełożony zachowuje też zwykłą pracę handlowca. |
| Nieaktualne zgłoszenie | Odrzucenie istniejącą akcją | Umożliwia poprawki bez nowego typu decyzji. |

## What We're NOT Doing

- Powiadomienia, WebSocket, polling, przypisywanie spraw i priorytety biznesowe.
- Masowe decyzje, automatyczne przechodzenie do kolejnej sprawy lub automatyczna wysyłka maila.
- Nowy mechanizm zamrożonej polityki: nadal obowiązuje dotychczasowa ocena polityki przy decyzji.
- Zmiana praw przełożonego poza oczekującymi sprawami ani zmiana zachowania `ready_to_send`.
- Wycofywanie zgłoszenia przez handlowca; poprawki wymagają odrzucenia przez przełożonego.
- Pełne adresowanie kroków i przebudowa logowania z S-17.
- Tłumaczenie wszystkich zapisanych komunikatów backendu z S-16. Nowe teksty UI mają klucze PL/EN.
- Wprowadzanie biblioteki cache zapytań, nowej infrastruktury kolejki albo migracji istniejących JSONB bez potrzeby.

## Implementation Approach

Najpierw domknąć niezmienność oczekującej sprawy w usługach backendu i bezpieczne odrzucenie nieaktualnego zgłoszenia. Następnie dodać lekki, dostępny tylko przełożonemu odczyt kolejki i szczegółu oceny, oparty na istniejących szkicach i historii. Frontend otrzymuje mały współdzielony provider kolejki oraz osobny widok oceny; zwykły adres zapytania również respektuje blokadę oczekiwania.

Dotychczasowy filtr oczekujących w skrzynce zostaje jako sposób śledzenia zgłoszeń przez handlowca. Dla przełożonego głównym wejściem jest nowa pozycja nawigacji. Nie powielamy osobnego stanu licznika i listy.

## Critical Implementation Details

### Zapis wyników rozpoczętych przed przekazaniem

Sprawdzenie statusu tylko na wejściu do endpointu nie wystarcza. Każdy zapis oraz usunięcie wyników zależnych musi pod blokadą analizy sprawdzić status i niezmienność historii decyzji od rozpoczęcia operacji. Jedna wersja historii, np. najwyższy identyfikator decyzji zapytania, przechodzi przez cały łańcuch etapów; nie jest pobierana ponownie jako nowa baza po każdym etapie. Chroni to również sekwencję rozpoczęcie analizy → przekazanie → odrzucenie / zatwierdzenie → spóźniony zapis.

Nie utrzymywać blokad ani połączeń bazodanowych podczas wywołań modeli. Wyjątek blokady musi przerwać łańcuch, także w miejscach z szerokim `except Exception`. Dane biznesowe pozostają bez zmian; ślad kosztu już rozpoczętego wywołania może zostać zapisany.

### Surowy status a możliwość decyzji

Członkostwo w kolejce wynika z surowego statusu, a nie z powodzenia walidacji treści szkicu. Nieaktualne i nieczytelne zgłoszenia nie mogą zniknąć z licznika. Odczyt szczegółu musi dać surowy status i token odrzucenia również wtedy, gdy zwykły widok analizy nie potrafi zbudować szkicu.

## Phase 1: Blokada zmian i bezpieczne decyzje

### Overview

Oczekująca sprawa pozostaje niezmieniona do decyzji przełożonego. Spóźnione wyniki nie nadpisują zgłoszenia ani późniejszej decyzji. Odrzucenie odblokowuje także nieaktualną sprawę.

### Changes Required:

#### 1. Wspólny kontrakt blokady

**File**: nowy `backend/app/inquiries/mutations.py`; `backend/app/checks/service.py`; `backend/app/parsing/service.py`.

**Intent**: Wprowadzić wspólną kontrolę stanu oraz wersji historii dla operacji zmieniających dane zapytania. Kontrola działa dla obu ról i przed kosztowną pracą, i bezpośrednio przed zapisem.

**Contract**: Surowe `awaiting_supervisor` blokuje zwykłe mutacje. Zmiana wersji historii od rozpoczęcia operacji unieważnia jej zapis. Kontrola zapisu działa w tej samej transakcji i pod tą samą blokadą wiersza analizy co decyzje. `lock_analysis` pozostaje ogólną blokadą — nie może sam odrzucać oczekujących spraw, bo korzysta z niego decyzja przełożonego. Brak wiersza analizy na początku nie zwalnia z kontroli: równoległa pierwsza analiza może utworzyć dane i doprowadzić do przekazania przed spóźnionym upsertem. Zapis analizy najpierw blokuje stabilny wiersz `Inquiry`, następnie ponownie odczytuje i blokuje istniejącą analizę lub tworzy ją, sprawdza status i pierwotną wersję historii, dopiero potem zapisuje. Wszystkie ścieżki upsertu analizy zachowują tę kolejność blokad; żadna nie pobiera blokady `Inquiry` po blokadzie analizy. Blokady są krótkie, po zakończeniu ekstrakcji.

#### 2. Wszystkie zapisy i czyszczenie etapów

**Files**: `backend/app/parsing/service.py`, `backend/app/checks/service.py`, `backend/app/orchestration/service.py`, `backend/app/recommendation/service.py`, `backend/app/policy/service.py`, `backend/app/draft/service.py`.

**Intent**: Zabezpieczyć analizę, poprawki, ponowienia oraz automatyczne etapy i usuwanie wyników zależnych przed zmianą oczekującej lub już rozstrzygniętej sprawy.

**Contract**: Kontekst operacji obejmuje wszystkie `_store`, `_drop_outdated`, `_drop_unless_exception` oraz zapis analizy / poprawek. Brak ścieżki publicznej pomijającej kontrolę; bezpośrednie wejścia usług tworzą kontekst, a kolejne etapy dziedziczą go. Wyjątki konfliktu przechodzą przez automatyczny łańcuch, nie uruchamiają kolejnych etapów i nie są zamieniane na ogólne błędy modeli. Zachować dotychczasowe sprawdzanie wersji danych wejściowych.

#### 3. API blokady i odrzucanie nieaktualnej sprawy

**Files**: `backend/app/api/analysis.py`, `backend/app/draft/service.py`.

**Intent**: Zwracać czytelny konflikt stanu zamiast ogólnego 500. Umożliwić powrót nieaktualnego zgłoszenia do poprawek bez osłabienia kontroli zatwierdzenia.

**Contract**: Mutacje `POST/PUT analysis`, `POST checks/orchestration/recommendation/policy/draft` i `PUT draft` oraz zwykła decyzja szkicu respektują blokadę; wyjątkiem jest autoryzowana decyzja przełożonego. Oczekiwanie i unieważnienie rozpoczętej pracy dają 409 ze stabilnymi, odróżnialnymi komunikatami (`Inquiry awaiting supervisor decision`, `Inquiry changed, reload`). Nadal 401 bez sesji i 403 dla handlowca na decyzji przełożonego. Nowe wyjątki mapować przed szerokimi handlerami.

Odrzucenie przełożonego wymaga surowego statusu oczekiwania, zgodnego `updated_at`, komentarza i atomowego zapisu historii; nie wymaga aktualnej rekomendacji ani polityki. Dla aktualnego zgłoszenia zachować dotychczasowy snapshot. Dla nieaktualnego skopiować historyczny snapshot ostatniego przekazania tego szkicu, bez udawania aktualnej oceny. Gdy brak czytelnych danych historycznych, zachować dostępny surowy snapshot (pusty obiekt tylko przy braku snapshotu); istniejący odczyt historii pokazuje dane oferty jako niedostępne, lecz zawsze zachowuje kto/kiedy/dlaczego. Nie dodawać nowej akcji ani nowych obowiązkowych pól JSONB. Zatwierdzenie nadal sprawdza aktualność, politykę i zakaz własnego zatwierdzenia. Ponowione żądanie ze starym tokenem nie dopisuje historii drugi raz. Odpowiedź po skutecznym odrzuceniu nie może zamienić udanej operacji w 500 z powodu nieczytelnego szkicu.

### Success Criteria:

#### Automated Verification:

- Testy backendu blokują każdą zwykłą mutację obu ról na oczekującej sprawie bez zmiany danych i bez uruchomienia dostawcy przy odmowie na wejściu.
- Testy współbieżności chronią zapis i usuwanie wyników po przekazaniu oraz po przekazaniu zakończonym decyzją; przerwany łańcuch nie uruchamia dalszych etapów.
- Testy decyzji obejmują komentarz, cztery oczy, konflikt tokenu, odrzucenie nieaktualnego / nieczytelnego zgłoszenia, historię oraz ponowne przetwarzanie po odrzuceniu.
- Bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`.

## Phase 2: API kolejki i danych oceny

### Overview

Przełożony otrzymuje spójny odczyt listy, licznika i przedmiotu decyzji, bez nowej tabeli kolejki i bez generowania treści przez model.

### Changes Required:

#### 1. Projekcja listy

**Files**: nowy `backend/app/api/supervisor.py`; nowy `backend/app/inquiries/supervisor_queue.py`; `backend/app/main.py`; `backend/app/draft/service.py` — współdzielony odczyt polityki.

**Intent**: Udostępnić wyłącznie przełożonemu lekką kolejkę z czasem przekazania i powodami eskalacji. Wykorzystać tę samą semantykę polityki co podczas decyzji, również dla edytowanej oferty.

**Contract**: `GET /api/supervisor/queue` zwraca `{items, total}`. Każdy element zawiera podstawowe pola zapytania (`id`, nadawca, temat, `received_at`), `submitted_at`, `submitted_by`, `draft_updated_at`, `attention_rules` (kod i werdykt `fail` / `not_evaluated`) oraz `review_state` (`actionable`, `stale`, `unavailable`). Brak dostępu dla handlowca: 403; brak sesji: 401.

Źródłem członkostwa jest wyłącznie zapisany `awaiting_supervisor`, w tym sprawy nieaktualne. `total` liczy wszystkie elementy tej listy. `submitted_at` pochodzi z ostatniej decyzji `approve` o `status_after=awaiting_supervisor` odpowiadającej bieżącemu szkicowi; przy historycznym braku wpisu użyć `draft.updated_at`. Sortowanie rosnąco po `(submitted_at, id)`.

Powody pochodzą z polityki rzeczywistej oferty, zgodnie z istniejącą logiką `_policy_in_force` / `_edited_offer_policy`; nie z samej rekomendacji. Dla spraw nieaktualnych nie przedstawiać starej polityki jako bieżącej — oznaczyć dane historyczne lub ich niedostępność. Błąd walidacji jednego JSONB nie wywraca całej kolejki. Nie zwracać pełnych maili, szkiców ani śladów uruchomień na liście. Pobierać dane zbiorczo, bez pełnego `get_analysis` / `get_draft_view` dla każdego wiersza.

#### 2. Odczyt szczegółu odporny na nieaktualność

**Files**: `backend/app/api/supervisor.py`, `backend/app/inquiries/supervisor_queue.py`, `backend/app/draft/service.py`.

**Intent**: Zapewnić ekranowi oceny dane potrzebne do decyzji oraz możliwość odrzucenia nawet wtedy, gdy pełny widok analizy nie może odtworzyć szkicu.

**Contract**: `GET /api/supervisor/reviews/{inquiry_id}` jest odczytem przełożonego istniejącego zapytania, także po decyzji. Zwraca metadane zapytania i surowy status / token szkicu, `submitted_at`, `submitted_by`, stan aktualności, dozwolone akcje, opcjonalną ocenianą ofertę i politykę, dostępny kontekst tylko do odczytu oraz historię. Brak czytelnej oferty daje `null` i marker niedostępności, a nie 500. Brak oczekującego szkicu daje widok wyniku lub komunikat „sprawa nie oczekuje”, bez akcji decyzji; nie przekierowuje automatycznie. Nieistniejące zapytanie daje 404, niepoprawny identyfikator 422. Żaden odczyt nie naprawia ani nie zmienia danych.

Decyzje nadal używają istniejącego `POST /api/inquiries/{id}/draft/supervisor-decision` z `updated_at`, `action`, `reason`. Weryfikacja w API decyzji pozostaje rozstrzygająca; `allowed_actions` z odczytu nie zastępuje kontroli przy zapisie.

### Success Criteria:

#### Automated Verification:

- Testy API kolejki potwierdzają 401/403, pustą listę, poprawny licznik, unikalność wierszy i kolejność według przekazania z deterministycznym remisem.
- Testy odczytu obejmują edytowaną ofertę, reguły `not_evaluated`, nieaktualne i nieczytelne szkice oraz fallback daty bez ukrywania zgłoszeń.
- Testy szczegółu obejmują wynik po decyzji, brak oczekiwania, brak danych oferty, 404/422 oraz brak skutków ubocznych odczytu.
- Bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`.

## Phase 3: Kolejka, licznik i ekran decyzji

### Overview

Udostępnić osobny przepływ przełożonego, wspólny stan kolejki i odświeżanie oraz blokady w dotychczasowym widoku zapytania. Zweryfikować zachowanie obu ról, dostępność i prezentację w PL/EN.

### Changes Required:

#### 1. Źródło danych i nawigacja

**Files**: nowy `frontend/src/api/supervisor.ts`; nowy `frontend/src/supervisorQueue.tsx`; `frontend/src/App.tsx`, `frontend/src/components/AppNav.tsx`, `frontend/src/router.tsx`.

**Intent**: Dzielić stan listy i licznika pomiędzy nawigację i kolejkę. Udostępnić trasy tylko przełożonemu, zachowując istniejący ekran startowy i adres podczas logowania.

**Contract**: Provider żyje w uwierzytelnionej części aplikacji i obejmuje nawigację oraz widoki routingu. Pobiera kolejkę tylko dla przełożonego. Stan rozróżnia ładowanie, wynik i błąd; nieznana liczba nie jest zerem. Po błędzie odświeżenia poprzednia liczba może zostać z oznaczeniem nieaktualności i akcją ponowienia. Wyniki starszych żądań nie nadpisują nowszej decyzji; wylogowanie i zmiana użytkownika czyszczą dane, anulują żądania i subskrypcje.

Trasy `/approvals`, `/approvals/$inquiryId` oraz `/approvals/$inquiryId/run` zachowują aktywną pozycję kolejki, także przy inspektorze. Handlowiec pod takim adresem widzi komunikat braku dostępu i link do skrzynki; nie uruchamia żądań kolejki. Anonimowy widzi logowanie pod zachowanym URL. Brak automatycznej zmiany `/` na kolejkę.

Odświeżanie: po wejściu na trasę kolejki, przejściu dokumentu z ukrytego do widocznego, własnej decyzji oraz ręcznie. Po powrocie do karty odświeża się także otwarta ocena. Współbieżne wyzwalacze współdzielą żądanie; brak timerów pollingu i nowych bibliotek cache. Ponowienie odczytu nie wysyła decyzji ponownie. Zachować komentarz przy błędzie sieciowym; jeśli token sprawy zmienił się w tle, wymagać ponownego przejrzenia danych przed wysłaniem.

#### 2. Lista i widok oceny

**Files**: nowe `frontend/src/components/SupervisorQueue.tsx`, `SupervisorReview.tsx`; `frontend/src/components/ReplyDraftSection.tsx`, `PolicySection.tsx`, `RunInspector.tsx`.

**Intent**: Pokazać powody oczekiwania i czas na liście, a po otwarciu umożliwić decyzję bez przewijania całego procesu handlowca. Wydzielić współdzielone elementy decyzji i prezentacji zamiast kopiować logikę formularza.

**Contract**: Lista pokazuje klienta, gdy jest dostępny w danych, w przeciwnym razie nadawcę, temat, datę przekazania i czas oczekiwania wyliczony przy renderze / odświeżeniu oraz przetłumaczone nazwy reguł wymagających uwagi. Nie pokazuje samego surowego identyfikatora wariantu. Pusta kolejka, ładowanie i błąd mają odrębne komunikaty.

Ocena: reguły `fail` / `not_evaluated` → zwięzła rzeczywista oferta (produkty, pokrycie, termin, wartość, marża, oznaczenie edycji) → Zatwierdź / Odrzuć i obowiązkowy komentarz. Pozostałe reguły, treść maila, szkic, uzasadnienie i historia znajdują się w rozwijanym kontekście poniżej. Podstawowy ekran i formularz decyzji mieszczą główną akcję na 1440×900; nie umieszczać przed nią pełnych tabel linii ani treści maila. Dla własnego zgłoszenia i nieaktualnej sprawy dostępne jest tylko odrzucenie z wyjaśnieniem; przy niedostępnych danych nie udawać kompletnej oferty.

Po decyzji natychmiast usunąć element ze współdzielonej kolejki, odświeżyć stan z API i pozostawić szczegół z wynikiem. Stały `role=status` ogłasza wynik; fokus trafia do nagłówka wyniku, nie do usuniętego wiersza ani body. Widoczny link „Wróć do kolejki”. Po 409 odświeżyć ocenę i kolejkę, wyjaśnić konflikt bez automatycznego ponawiania decyzji. Inspektor korzysta z istniejącego komponentu i pozostaje na żądanie; brak mutacji w jego kontekście oceny.

#### 3. Blokady na zwykłym adresie zapytania

**Files**: `frontend/src/components/Inbox.tsx`, `AnalysisPanel.tsx`, `InquiryStepper.tsx`, `ChecksSection.tsx`, `OrchestrationSection.tsx`, `RecommendationSection.tsx`, `PolicySection.tsx`, `ReplyDraftSection.tsx`.

**Intent**: Bezpośredni adres zapytania i powrót do wcześniejszego kroku nie mogą udostępniać niedozwolonych zmian. Handlowiec widzi, że sprawa czeka na decyzję, a przełożony może przejść do oceny.

**Contract**: Surowy `draft_status` z metadanych jest sygnałem blokady także przy `analysis.draft === null`. Dla obu ról na oczekującej sprawie nie ma aktywnych kontrolek edycji, ponawiania ani regenerowania; kontekst jest tylko do odczytu. Nie opierać blokady wyłącznie na aktywnym kroku. Przełożony ma jawny link do `/approvals/$inquiryId`; API nadal egzekwuje ograniczenie niezależnie od interfejsu. Po odrzuceniu powraca dotychczasowa ścieżka poprawek. Obecny filtr oczekujących i aktualizacje statusu w skrzynce pozostają dostępne.

#### 4. Tłumaczenia, komponenty i scenariusze weryfikacji

**Files**: `frontend/src/i18n/locales/pl.json`, `en.json`; `frontend/src/kitchen-sink.tsx`; `frontend/src/test/replyDraftFixtures.ts`; testy routingu, App, Inbox, AnalysisPanel oraz nowych komponentów; `AGENTS.md`; `README.md`.

**Intent**: Zapewnić czytelne komunikaty, dostępność i powtarzalne sprawdzenie stanów kolejki. Opisać nowy przepływ oraz zmianę praw poprawek.

**Contract**: Każdy nowy tekst UI przez `t()` w obu językach. Użyć istniejących komponentów z `components/ui`, semantycznych tokenów i solidnego fokusu; bez nowych reguł legacy CSS. Usunąć reguły legacy dopiero po usunięciu ostatniego użytkownika. Dodać nowe widoki do skanu kolorów w `AGENTS.md`. Kitchen sink obejmuje ładowanie, błąd licznika, pustą kolejkę, kilka spraw, ofertę edytowaną, własne zgłoszenie, nieaktualną / niedostępną sprawę i wynik obu decyzji; pozostaje tylko deweloperski.

### Success Criteria:

#### Automated Verification:

- Testy interfejsu obejmują dostęp ról i bezpośrednie URL, jeden stan listy i licznika, wszystkie wyzwalacze odświeżania, anulowanie po wylogowaniu i odporność na spóźnione odpowiedzi.
- Testy przepływu obejmują ofertę edytowaną, obowiązkowy komentarz, własne zgłoszenie, nieaktualność, konflikt 409, 401, błąd sieci, pozostawienie wyniku i odblokowanie poprawek po odrzuceniu.
- Testy zwykłego widoku zapytania nie znajdują aktywnych mutacji w żadnym kroku oczekującej sprawy obu ról, również przy nieczytelnym szkicu.
- Bramki frontendu przechodzą z `frontend/`: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`; bramki backendu przechodzą przez `docker compose run --rm backend sh check.sh`.
- Skan kolorów i wartości arbitralnych z `AGENTS.md`, rozszerzony o nowe widoki, nie wypisuje dopasowań; kitchen sink nie trafia do wejść builda.

#### Manual Verification:

- Dwie sesje sales/supervisor pokazują przekazanie, odświeżenie kolejki, decyzję z komentarzem, poprawny licznik i widoczny wynik dla handlowca; odrzucenie pozwala poprawić i ponownie przekazać sprawę.
- Na 1440×900 reguły, oceniana oferta i główna akcja oraz potwierdzenie formularza są dostępne bez przewijania; na 375 px strona nie przewija się poziomo, a kontekst jest czytelny.
- W PL/EN i obu motywach klawiatura zachowuje widoczny fokus, odczyt ekranu odpowiada kolejności decyzji, status jest ogłaszany, a po decyzji fokus pozostaje przy wyniku.
- Odświeżenie i otwarcie bez sesji URL kolejki / oceny zachowuje adres po logowaniu; ręczne wejście handlowca nie ujawnia danych oceny; inspektor otwiera się na żądanie.

## Testing Strategy

### Backend

Rozszerzyć `backend/tests/test_draft_api.py`, `test_draft_service.py`, `test_inquiries_api.py` i testy usług etapów; dodać testy API kolejki. Użyć prawdziwego PostgreSQL zgodnie z bramkami projektu. Wyścigi symulować kontrolowanymi barierami / punktami przechwycenia przed zapisem, bez losowych opóźnień. Weryfikować bazę, brak nadpisania historii, brak usunięcia szkicu i liczbę wywołań dostawców; samo 409 nie dowodzi ochrony danych. Uwzględnić kosztowną pracę rozpoczętą przed przekazaniem i zakończoną po odrzuceniu lub zatwierdzeniu. Osobno sprawdzić dwie równoległe pierwsze analizy: obie początkowo nie widzą analizy, pierwsza kończy się i trafia do akceptacji, a druga nie może nadpisać zgłoszenia swoim upsertem.

### Frontend

Vitest + Testing Library i memory history, z testami w języku angielskim zgodnie z konfiguracją. Mockowane API ma odwzorowywać stany oraz tokeny, nie tylko potwierdzać obecność tekstu. Szczególnie ważne: brak pobrań przełożonego dla sales, brak fałszywego zera, wylogowanie w trakcie pobierania, usunięcie elementu po decyzji, spóźnione odczyty, konflikt komentarza z nową wersją i bezpośredni URL starej sprawy.

### Manual

Najpierw ARIA, DOM, computed styles, konsola i asercje układu, zgodnie z `context/foundation/lessons.md`. Screenshoty dopiero jako końcowa kontrola wizualna lub przy problemie niewyjaśnionym w DOM. Sprawdzić także własne zgłoszenie przełożonego i nieaktualną sprawę zwracaną do poprawy.

## Performance Considerations

Zakładana skala projektu to kilka osób i demonstracyjny zestaw zapytań. Lista i licznik używają jednego lekkiego odczytu, bez maili i śladów uruchomień, bez N+1 i bez okresowych wywołań. Szczegół jest pobierany tylko dla wybranej sprawy. Nie dodawać paginacji, wirtualizacji ani nowych indeksów bez wykazanego problemu; istnieje indeks statusu szkicu.

## Migration Notes

Plan nie wymaga nowych tabel, statusów ani obowiązkowych pól w zapisanych modelach JSONB. Projekcje i wersja historii wynikają z istniejących danych. Nie przepisywać dawnych decyzji; fallback daty dotyczy odczytu. Jeśli implementacja jednak zmieni model zapisany w JSONB, obowiązuje migracja danych lub pole opcjonalne z domyślną wartością, zgodnie z lessons.

Backend i frontend trafiają do jednego obrazu zgodnie z istniejącym wdrożeniem. Plan nie upoważnia do samodzielnego publikowania ani merge. Cofnięcie kodu przywróci dawne prawa ponawiania, ale nie usunie historii decyzji; nowe odrzucenia używają istniejącej akcji `supervisor_reject` i nie wymagają odwracania migracji.

## Open Risks & Assumptions

- Ochrona obejmuje zapisy i czyszczenie wszystkich etapów; pominięcie pojedynczej ścieżki może unieważnić decyzję. Faza 1 ma odrębne testy wyścigów i skutków w bazie.
- Stara oczekująca sprawa może nie mieć czytelnego snapshotu. Odrzucenie ma zachować metadane decyzji i jawnie pokazać brak danych oferty, bez tworzenia fikcyjnych wartości.
- Polityka nadal może zmienić się między odczytem a decyzją wskutek zmiany konfiguracji poza UI; API decyzji pozostaje źródłem prawdy, a historia zapisuje ocenę z chwili decyzji.
- Licznik może być nieaktualny w bezczynnej widocznej karcie. To uzgodniony koszt braku pollingu; użytkownik ma ręczne odświeżenie.
- Dotychczasowe prawa przełożonego wracają poza oczekiwaniem. Nie rozszerzać tej zmiany na trwały rozdział ról sprzedaży i nadzoru.

## References

- `context/foundation/roadmap.md:144` — S-15, zależności S-11 i S-14.
- `context/foundation/prd.md:136` — FR-019; US-02, Access Control i NFR dostępności.
- `context/foundation/tech-stack.md` i `context/foundation/lessons.md` — stack, JSONB i weryfikacja UI.
- `context/archive/2026-11-12-supervisor-approval/plan-brief.md` — dotychczasowy kontrakt decyzji.
- `context/archive/2026-11-17-status-and-honest-actions/plan-brief.md` — statusy i stały komunikat wyniku.
- `backend/app/checks/service.py:68`, `backend/app/parsing/service.py:138`, `:230` — blokady i zapis analizy.
- `backend/app/orchestration/service.py:374`, `:409`; `backend/app/recommendation/service.py:383`, `:424`; `backend/app/policy/service.py:212`, `:253`; `backend/app/draft/service.py:697`, `:754` — zapisy i czyszczenie wyników.
- `backend/app/draft/service.py:344`, `:802`, `:890`, `:927` — decyzja, blokada, historia i autor przekazania.
- `frontend/src/components/AnalysisPanel.tsx:443` — istniejąca obsługa konfliktu decyzji.
- `frontend/src/components/ReplyDraftSection.tsx:366`, `:592` — formularz komentarza i historia.

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` - <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Blokada zmian i bezpieczne decyzje

#### Automated

- [x] 1.1 Testy backendu blokują każdą zwykłą mutację obu ról na oczekującej sprawie bez zmiany danych i bez uruchomienia dostawcy przy odmowie na wejściu.
- [x] 1.2 Testy współbieżności chronią zapis i usuwanie wyników po przekazaniu oraz po przekazaniu zakończonym decyzją; przerwany łańcuch nie uruchamia dalszych etapów.
- [x] 1.3 Testy decyzji obejmują komentarz, cztery oczy, konflikt tokenu, odrzucenie nieaktualnego / nieczytelnego zgłoszenia, historię oraz ponowne przetwarzanie po odrzuceniu.
- [x] 1.4 Bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`.

### Phase 2: API kolejki i danych oceny

#### Automated

- [x] 2.1 Testy API kolejki potwierdzają 401/403, pustą listę, poprawny licznik, unikalność wierszy i kolejność według przekazania z deterministycznym remisem.
- [x] 2.2 Testy odczytu obejmują edytowaną ofertę, reguły `not_evaluated`, nieaktualne i nieczytelne szkice oraz fallback daty bez ukrywania zgłoszeń.
- [x] 2.3 Testy szczegółu obejmują wynik po decyzji, brak oczekiwania, brak danych oferty, 404/422 oraz brak skutków ubocznych odczytu.
- [x] 2.4 Bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`.

### Phase 3: Kolejka, licznik i ekran decyzji

#### Automated

- [ ] 3.1 Testy interfejsu obejmują dostęp ról i bezpośrednie URL, jeden stan listy i licznika, wszystkie wyzwalacze odświeżania, anulowanie po wylogowaniu i odporność na spóźnione odpowiedzi.
- [ ] 3.2 Testy przepływu obejmują ofertę edytowaną, obowiązkowy komentarz, własne zgłoszenie, nieaktualność, konflikt 409, 401, błąd sieci, pozostawienie wyniku i odblokowanie poprawek po odrzuceniu.
- [ ] 3.3 Testy zwykłego widoku zapytania nie znajdują aktywnych mutacji w żadnym kroku oczekującej sprawy obu ról, również przy nieczytelnym szkicu.
- [ ] 3.4 Bramki frontendu przechodzą z `frontend/`: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`; bramki backendu przechodzą przez `docker compose run --rm backend sh check.sh`.
- [ ] 3.5 Skan kolorów i wartości arbitralnych z `AGENTS.md`, rozszerzony o nowe widoki, nie wypisuje dopasowań; kitchen sink nie trafia do wejść builda.

#### Manual

- [ ] 3.6 Dwie sesje sales/supervisor pokazują przekazanie, odświeżenie kolejki, decyzję z komentarzem, poprawny licznik i widoczny wynik dla handlowca; odrzucenie pozwala poprawić i ponownie przekazać sprawę.
- [ ] 3.7 Na 1440×900 reguły, oceniana oferta i główna akcja oraz potwierdzenie formularza są dostępne bez przewijania; na 375 px strona nie przewija się poziomo, a kontekst jest czytelny.
- [ ] 3.8 W PL/EN i obu motywach klawiatura zachowuje widoczny fokus, odczyt ekranu odpowiada kolejności decyzji, status jest ogłaszany, a po decyzji fokus pozostaje przy wyniku.
- [ ] 3.9 Odświeżenie i otwarcie bez sesji URL kolejki / oceny zachowuje adres po logowaniu; ręczne wejście handlowca nie ujawnia danych oceny; inspektor otwiera się na żądanie.
