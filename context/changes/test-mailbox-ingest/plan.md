# Odczyt testowej skrzynki e-mail (S-09) — plan implementacji

## Overview

Handlowiec klika „Fetch mail” w skrzynce. Backend łączy się z dedykowaną testową skrzynką IMAP w trybie tylko do odczytu, pobiera 20 najnowszych wiadomości i zapisuje jako `Inquiry` (źródło `mailbox`) te, których jeszcze nie ma. Lista się przeładowuje, a zapytania z poczty mają znaczek „E-mail”. Dalej obsługuje się je jak przykładowe: „Analyze request”, sprawdzenia, rekomendacja i szkic.

Zmiana realizuje FR-013 (`context/foundation/prd.md:71-72`) i wycinek S-09 (`context/foundation/roadmap.md:208-218`).

## Current State Analysis

Pełne ustalenia są w `context/changes/test-mailbox-ingest/research.md`. Najważniejsze dla planu:

- **Model bez pól pod pocztę.** `Inquiry` (`backend/app/inquiries/models.py:7-17`) ma kształt maila, ale nie ma `source` ani identyfikatora zewnętrznego. S-01 jawnie odłożył te pola do S-09 (`context/archive/2026-11-09-login-and-inbox/plan.md:39`). Limity kolumn: `sender_name` 200, `sender_email` 320, `subject` 300. `body` to `Text`. Head migracji: `0013_supervisor_decisions`.
- **Zapytania powstają tylko w dwóch miejscach:** z seedu migracji `0003` (4 przykładowe) i z runnera eval. Nie ma endpointu tworzącego zapytania. Sprzątanie eval kasuje każde zapytanie, którego temat zaczyna się od `[eval] ` (`backend/app/eval/runner.py:57,329-350`).
- **Brak pracy w tle.** Aplikacja działa jako jeden proces uvicorn (`backend/start.sh:8`). Render free usypia usługę po ~15 min (`README.md:599`). Endpointy są synchroniczne (`def`) i działają w threadpoolu.
- **Wzorzec integracji zewnętrznej.** `LLM_PROVIDER="fake"` (`backend/app/settings.py:11,50`) wybiera implementację. Protocol, `Fake*`, `Unconfigured*` i fabryka `get_*(settings)` jako `Depends` są w `backend/app/parsing/extractor.py:48-84`. Typowane błędy bez treści są w `backend/app/llm/client.py:33-124`. Sekrety mają typ `SecretStr | None` i walidator „pusty string = brak” (`backend/app/settings.py:60-63`). Testy podmieniają zależności przez `app.dependency_overrides` (`backend/tests/conftest.py:174-213`).
- **Blokada przebiegu.** Advisory lock na dedykowanym połączeniu: `backend/app/eval/runner.py:138-152`.
- **Konwencja logów.** Logi zawierają tylko klasę błędu i identyfikatory, nigdy treść zapytania. Przykłady: `backend/app/api/analysis.py:98-101`, `backend/app/llm/client.py:3-4`.
- **Frontend.** `frontend/src/components/Inbox.tsx` pobiera listę raz przy montowaniu (`:48-59`). Ponowne pobranie następuje tylko przez „Retry” po błędzie. Nagłówek sekcji listy to `<h2 id="inbox-heading">` (`:161`). Strażnik typu `isInquirySummary` jest w `frontend/src/api/inquiries.ts:19-36`.
- **Parser.** Ekstraktor regułowy bierze klienta z ostatniej niepustej linii treści (`backend/app/parsing/fake.py:83-91`). Cytat odpowiedzi albo stopka na końcu psują ten wynik.

## Desired End State

- **Przycisk w skrzynce.** Zalogowany użytkownik (sales albo supervisor) widzi w skrzynce przycisk „Fetch mail”. Po kliknięciu widzi wynik, np. „2 new, 3 already in inbox”, a lista pokazuje nowe zapytania ze znaczkiem „E-mail”.
- **Bez skutków ubocznych w skrzynce.** Ponowne kliknięcie niczego nie dubluje. Skrzynka IMAP nie zmienia się: żadna flaga, w tym `\Seen`, nie jest ustawiana, a wiadomości nie są przenoszone ani kasowane.
- **Bez konfiguracji (`MAILBOX_PROVIDER` = `fake`)** przycisk pobiera wiadomości z fake'owej skrzynki w pamięci. Testy i CI działają bez sieci.
- **Z `MAILBOX_PROVIDER=imap` bez danych logowania** endpoint zwraca 503 „Mailbox not configured”.
- **Lokalnie** `docker compose --profile mail up` stawia GreenMail. Polecenie `python -m app.mailbox.demo` wrzuca do niego przykładowe maile, które przycisk pobiera.
- **Na Gmailu** z hasłem aplikacji to samo działa przez `imap.gmail.com:993`.
- **Weryfikacja:** `check.sh` przechodzi, frontend lint/typecheck/test przechodzą, a ręczna próba na GreenMailu i na Gmailu kończy się powodzeniem.

### Key Discoveries:

- **Zapis bez duplikatów.** Unikalny indeks na `(source, external_id)` pozwala na `INSERT … ON CONFLICT DO NOTHING` bez wcześniejszego sprawdzania. Postgres dopuszcza wiele NULL-i w `external_id`, więc 4 seedy i wiersze eval nie kolidują.
- **Tylko odczyt po stronie IMAP:** `SELECT` z `readonly=True` (komenda IMAP `EXAMINE`) i `UID FETCH … (BODY.PEEK[])`. Oba wywołania nie zmieniają flag (RFC 3501).
- **Biblioteki:** stdlib `imaplib` oraz `email` z `policy.default` (`get_body(preferencelist=("plain", "html"))`, automatyczne dekodowanie nagłówków RFC 2047). Nie trzeba nowej zależności.
- **Session pooler.** Advisory lock sesyjny działa z session poolerem Supabase, którego używa deploy (`README.md`, sekcja Supabase).

## What We're NOT Doing

- Cykliczne lub automatyczne pobieranie (timer, cron, pobranie przy wejściu do skrzynki).
- Zapamiętywanie ostatniego UID lub UIDVALIDITY. Zamiast tego jest okno 20 najnowszych wiadomości i dedup.
- Jakakolwiek zmiana w skrzynce IMAP (flagi, przenoszenie, kasowanie) oraz wysyłka maili. Wysyłka zostaje symulowana.
- Załączniki, wątki, łączenie odpowiedzi z istniejącym zapytaniem.
- OAuth2 / XOAUTH2. Obsługiwane jest tylko logowanie hasłem (hasło aplikacji).
- Ograniczenie pobierania do przełożonego. Pobierać może każdy zalogowany.
- Śledzenie kosztu i czasu pobierania w `trace_runs`. To nie jest krok analizy zapytania.
- Paginacja skrzynki i usuwanie zapytań z poczty z UI.
- Automatyczne uruchamianie analizy po pobraniu. Handlowiec klika „Analyze request” jak dotąd.

## Implementation Approach

1. **Logika bez sieci najpierw.** Faza 1 to model i czysta konwersja „surowy mail → kandydat na zapytanie” z zapisem bez duplikatów, testowana na bajtach maili w testach.
2. **Klient według wzorca integracji LLM.** Faza 2 dodaje klienta skrzynki (`fake` domyślnie, `imap` prawdziwy) i cienki serwis spinający blokadę, klienta, konwersję i zapis. Do tego endpoint i pole `source` w API.
3. **Frontend.** Faza 3 dodaje przycisk, komunikat wyniku i znaczek.
4. **Środowisko do ręcznej próby.** Faza 4 dodaje GreenMail w compose, skrypt z przykładowymi mailami i dokumentację Gmaila oraz Render.

## Critical Implementation Details

- **Kolizja z prefiksem eval.** Temat maila zaczynający się od `[eval] ` zostałby skasowany przez sprzątanie eval (`backend/app/eval/runner.py:329-335`). Konwersja dopisuje wtedy przed nim `[mail] `, więc temat nie zaczyna się już od `SUBJECT_PREFIX`. Stałą importujemy z runnera, nie kopiujemy.
- **Prywatność w logach i błędach.** Nie logujemy tematu, nadawcy, treści, Message-ID ani surowych odpowiedzi IMAP. Wyjątki `imaplib` mogą cytować odpowiedź serwera, więc mapujemy je na własne błędy z komunikatem stałym i nie łańcuchujemy (`from None`), jak w `backend/app/parsing/openai_compatible.py:95`. Logujemy liczby i klasy błędów.
- **Kolejność w serwisie.** Najpierw blokada, potem połączenie IMAP, potem zapis. Gdy blokada jest zajęta, endpoint od razu zwraca 409 bez łączenia się ze skrzynką.

## Phase 1: Model i konwersja maila

### Overview

Zapytanie dostaje źródło i identyfikator zewnętrzny. Powstaje czysta funkcja, która z surowych bajtów maila robi kandydata na zapytanie albo powód pominięcia, oraz zapis, który dodaje tylko nowe wiersze.

### Changes Required:

#### 1. Migracja źródła zapytania

**File**: `backend/migrations/versions/0014_inquiry_source.py`

**Intent**: Dodać kolumny potrzebne do odróżnienia maili od przykładowych zapytań i do deduplikacji. Istniejące wiersze (4 seedy) dostają `sample`.

**Contract**: Rewizja `0014_inquiry_source`, `down_revision = "0013_supervisor_decisions"`. Kolumny:
- `inquiries.source` VARCHAR(20) NOT NULL `server_default 'sample'` z check `ck_inquiries_source`: `source IN ('sample', 'mailbox')`;
- `inquiries.external_id` VARCHAR(64) NULL.

Unikalny indeks `ux_inquiries_source_external_id` na `(source, external_id)`. `downgrade` usuwa indeks, check i kolumny.

#### 2. Model `Inquiry`

**File**: `backend/app/inquiries/models.py`

**Intent**: Odzwierciedlić nowe kolumny w modelu, tak żeby kod tworzący zapytania bez źródła (eval, testy) dalej dostawał `sample`.

**Contract**: `InquirySource = Literal["sample", "mailbox"]`. Pole `source: InquirySource` z domyślnym `"sample"` (`max_length=20`, server default jak w migracji). Pole `external_id: str | None = None` (`max_length=64`). W docstringu: `external_id` to sha256 (hex) identyfikatora wiadomości.

#### 3. Konwersja surowego maila

**File**: `backend/app/mailbox/__init__.py`, `backend/app/mailbox/message.py`

**Intent**: Zamienić bajty wiadomości RFC 5322 na dane zapytania, które przejdą przez limity bazy i parser. Zwraca kandydata albo powód pominięcia, bez rzucania i bez logowania treści.

**Contract**: `to_candidate(raw: bytes, *, fetched_at: datetime) -> MailCandidate | Skipped`.

`MailCandidate` (frozen dataclass) zawiera: `external_id`, `sender_name`, `sender_email`, `subject`, `body`, `received_at`. `Skipped` zawiera tylko `reason: Literal["no_sender", "unreadable"]`.

Reguły:
- **Identyfikator:** `external_id` = sha256 hex nagłówka `Message-ID` po `strip()`. Gdy go brak, sha256 surowych bajtów.
- **Nadawca:** z `From` przez `email.utils.parseaddr`. Brak adresu, brak `@` albo adres dłuższy niż 320 znaków daje `Skipped("no_sender")`. Puste imię zastępuje adres. `sender_name` jest przycinany do 200 znaków.
- **Temat:** zdekodowany, białe znaki zwinięte do pojedynczych spacji. Pusty temat daje `(no subject)`. Gdy zaczyna się od `SUBJECT_PREFIX` z `app.eval.runner`, dostaje prefiks `[mail] `. Przycięcie do 300 znaków z `…` na końcu.
- **Data:** `received_at` z `Date` przez `parsedate_to_datetime`. Data bez strefy jest traktowana jako UTC. Brak daty albo data niepoprawna daje `fetched_at`.
- **Treść:** wybierana przez `msg.get_body(preferencelist=("plain", "html"))`. HTML jest zamieniany na tekst przez `html.parser` (pomija `script` i `style`, zachowuje podziały na `br`, `p`, `div` i `li`). Potem:
  - odcięcie cytatu od pierwszej linii pasującej do `On … wrote:`, `W dniu … napisał(a):`, `-----Original Message-----` albo `-----Oryginalna wiadomość-----`;
  - usunięcie linii zaczynających się od `>`;
  - `\r\n` → `\n`, zwinięcie 3+ pustych linii do 2, `strip()`;
  - limit 20 000 znaków.

  Brak części tekstowej daje pustą treść.
- Wyjątek przy parsowaniu daje `Skipped("unreadable")`.

#### 4. Zapis bez duplikatów

**File**: `backend/app/mailbox/store.py`

**Intent**: Zapisać kandydatów jako zapytania ze źródłem `mailbox`, pomijając już istniejące, w jednej transakcji.

**Contract**: `insert_new(engine, candidates: Sequence[MailCandidate]) -> int`, gdzie wynik to liczba nowych wierszy. Funkcja wykonuje `INSERT … ON CONFLICT (source, external_id) DO NOTHING` (dialekt Postgres SQLAlchemy). Dwa kandydaty z tym samym `external_id` w jednej partii dają jeden wiersz.

#### 5. Testy

**File**: `backend/tests/test_mailbox_message.py`, `backend/tests/test_mailbox_store.py`, `backend/tests/test_inquiries_models.py` (albo rozszerzenie istniejącego testu modelu, jeśli taki jest)

**Intent**: Sprawdzić reguły konwersji na zbudowanych w testach bajtach maili (`email.message.EmailMessage`) oraz zapis z deduplikacją na prawdziwym Postgresie ze znacznikami procesu z `conftest.py`.

**Contract**: Przypadki konwersji:
- `text/plain` po polsku z podpisem;
- `multipart/alternative`, w którym wygrywa część plain;
- sam HTML;
- temat i nazwa zakodowane RFC 2047;
- odpowiedź z cytatem „W dniu … napisał:” i liniami `>`;
- brak `Message-ID`, czyli hash bajtów;
- brak `From`, czyli `no_sender`;
- data bez strefy i brak daty;
- temat `[eval] x`, czyli `[mail] [eval] x`;
- temat 400 znaków, przycięty do 300.

Zapis: drugi `insert_new` tych samych kandydatów zwraca 0. Seedy mają `source == "sample"`.

### Success Criteria:

#### Automated Verification:

- Migracja `0014` wchodzi i schodzi: `docker compose run --rm backend uv run alembic upgrade head && docker compose run --rm backend uv run alembic downgrade -1 && docker compose run --rm backend uv run alembic upgrade head`
- Testy konwersji i zapisu przechodzą: `docker compose run --rm backend uv run pytest tests/test_mailbox_message.py tests/test_mailbox_store.py`
- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`

#### Manual Verification:

- Po migracji 4 przykładowe zapytania mają `source = 'sample'` i `external_id IS NULL` (zapytanie SQL na lokalnej bazie)

---

## Phase 2: Klient skrzynki i endpoint

### Overview

Konfiguracja skrzynki według wzorca LLM. Klient `fake` / `imap` / `unconfigured`, serwis z blokadą i endpoint `POST /api/mailbox/fetch`. API skrzynki zwraca `source`.

### Changes Required:

#### 1. Ustawienia

**File**: `backend/app/settings.py`

**Intent**: Dodać konfigurację skrzynki z bezpiecznymi domyślnymi wartościami: `fake` bez sieci, a dla `imap` port 993 z TLS.

**Contract**:

| Pole | Typ | Domyślnie |
|---|---|---|
| `mailbox_provider` | `MailboxProvider = Literal["fake", "imap"]` | `"fake"` |
| `imap_host` | `str \| None` | — |
| `imap_port` | `int`, `Field(gt=0, lt=65536)` | `993` |
| `imap_ssl` | `bool` | `True` |
| `imap_username` | `str \| None` | — |
| `imap_password` | `SecretStr \| None` | — |
| `imap_folder` | `str` | `"INBOX"` |
| `imap_timeout_seconds` | `float`, `Field(gt=0)` | `15` |

`imap_host`, `imap_username` i `imap_password` trafiają do listy walidatora `_empty_string_is_unset`. Komentarz nad polami mówi: tylko dedykowana testowa skrzynka, tylko odczyt.

#### 2. Klient skrzynki

**File**: `backend/app/mailbox/client.py`, `backend/app/mailbox/imap.py`

**Intent**: Dać serwisowi jeden interfejs, który zwraca surowe bajty najnowszych wiadomości, z wersją bez sieci do testów i demo oraz z jasnym błędem, gdy konfiguracji brakuje.

**Contract**:
- `class Mailbox(Protocol)`: `name: str` oraz `def latest(self, limit: int) -> list[bytes]`. Wynik zawiera co najwyżej `limit` wiadomości w kolejności od najnowszej (najwyższe UID).
- Błędy (komunikaty stałe, bez danych serwera):
  - `MailboxError` jako baza;
  - `MailboxNotConfigured`;
  - `MailboxAuthFailed`;
  - `MailboxUnavailable` dla sieci, timeoutu i TLS;
  - `MailboxProtocolError` dla nieoczekiwanej odpowiedzi.
- `FakeMailbox(messages: Sequence[bytes] = DEMO_MESSAGES)` zwraca ostatnie `limit` wiadomości. `DEMO_MESSAGES` to 2 polskie maile w stylu seedów z adresami `.example`, zbudowane przez `EmailMessage`.
- `UnconfiguredMailbox` rzuca `MailboxNotConfigured`.
- `get_mailbox(settings: Annotated[Settings, Depends(get_settings)]) -> Mailbox`:
  - dla `fake` zwraca `FakeMailbox()`;
  - dla `imap` przy braku host, username albo password zwraca `UnconfiguredMailbox`;
  - w pozostałych przypadkach zwraca `ImapMailbox` (import leniwy).
- `ImapMailbox.latest`:
  - łączy się przez `IMAP4_SSL` (gdy `imap_ssl`) albo `IMAP4`, z `timeout`, i wywołuje `login`;
  - wybiera folder z `select(folder, readonly=True)`;
  - pobiera `uid("SEARCH", None, "ALL")` i bierze ostatnie `limit` UID-ów;
  - dla nich wykonuje `uid("FETCH", …, "(BODY.PEEK[])")`;
  - na końcu wywołuje `logout` w `finally`.

  Mapowanie wyjątków:
  - `imaplib.IMAP4.error` przy `login` → `MailboxAuthFailed`;
  - `OSError` i `TimeoutError` (w tym `ssl.SSLError`) → `MailboxUnavailable`;
  - pozostałe `IMAP4.error` i odpowiedzi różne od `OK` → `MailboxProtocolError`.

  Wszystkie mapowania przez `from None`.

#### 3. Serwis pobierania

**File**: `backend/app/mailbox/service.py`

**Intent**: Spiąć blokadę, klienta, konwersję i zapis w jedną operację z wynikiem do pokazania w UI. Loguje tylko liczby.

**Contract**:
- `FETCH_LIMIT = 20`.
- Wynik `FetchResult` (pydantic, `extra="forbid"`): `fetched: int`, `created: int`, `duplicates: int`, `skipped: int`.
- `fetch_mailbox(engine, mailbox: Mailbox, *, now: datetime | None = None) -> FetchResult`.
- Blokada advisory `MAILBOX_LOCK_KEY` (osobna stała, wzorzec z `backend/app/eval/runner.py:138-152`). Zajęta blokada rzuca `MailboxBusy`.
- Liczby: `duplicates = len(candidates) - created`, `skipped` = liczba `Skipped`.
- Log `INFO`: `mailbox fetch: fetched=%d created=%d duplicates=%d skipped=%d`.

#### 4. Endpoint

**File**: `backend/app/api/mailbox.py`, `backend/app/main.py`

**Intent**: Udostępnić pobranie każdemu zalogowanemu i zamienić błędy na zrozumiałe statusy HTTP bez treści serwera.

**Contract**: `POST /api/mailbox/fetch` na `protected_router` zwraca `200 FetchResult`. Mapowanie błędów:

| Błąd | Status | Komunikat |
|---|---|---|
| `MailboxNotConfigured` | 503 | „Mailbox not configured” |
| `MailboxAuthFailed` | 502 | „Mailbox login failed” |
| `MailboxUnavailable` | 502 | „Mailbox unavailable” |
| `MailboxProtocolError` | 502 | „Mailbox error” |
| `MailboxBusy` | 409 | „Mailbox fetch already in progress” |
| `SQLAlchemyError` | 503 | `database_unavailable()` |

Każdy błąd jest logowany tylko z klasą. Endpoint jest synchroniczny (`def`).

#### 5. Źródło w API skrzynki

**File**: `backend/app/api/inquiries.py`

**Intent**: Frontend musi wiedzieć, które zapytania przyszły z poczty.

**Contract**: `InquirySummary.source: InquirySource`. `InquiryDetail` dziedziczy pole. `external_id` nie jest wystawiany.

#### 6. Konfiguracja środowisk

**File**: `.env.example`, `docker-compose.yml` (usługi `app` i `backend`), `render.yaml`

**Intent**: Przepuścić nowe zmienne tak jak `LLM_*`. Na Render skrzynka zostaje `fake`, dopóki autor nie ustawi danych.

**Contract**:
- `.env.example`: blok komentarza o dedykowanej skrzynce, haśle aplikacji Gmail i trybie tylko do odczytu; `MAILBOX_PROVIDER=`, `IMAP_HOST=`, `IMAP_PORT=`, `IMAP_SSL=`, `IMAP_USERNAME=`, `IMAP_PASSWORD=`, `IMAP_FOLDER=`.
- compose: `MAILBOX_PROVIDER: ${MAILBOX_PROVIDER:-fake}`, a pozostałe przez `${X:-}`, przy czym `IMAP_PORT` przez `${IMAP_PORT:-993}`, `IMAP_SSL` przez `${IMAP_SSL:-true}`, `IMAP_FOLDER` przez `${IMAP_FOLDER:-INBOX}`.
- `render.yaml`: `MAILBOX_PROVIDER`, `IMAP_HOST`, `IMAP_USERNAME`, `IMAP_PASSWORD` jako `sync: false`, z komentarzem jak przy `LLM_API_KEY`.

#### 7. Testy

**File**: `backend/tests/test_mailbox_client.py`, `backend/tests/test_mailbox_service.py`, `backend/tests/test_mailbox_api.py`, `backend/tests/test_inquiries_api.py`, `backend/tests/test_settings.py`

**Intent**: Sprawdzić fabrykę, mapowanie błędów IMAP, serwis z fake'iem, endpoint (auth, statusy) i pole `source`, bez sieci.

**Contract**:
- `ImapMailbox` jest testowany przez podmianę `imaplib.IMAP4_SSL` lub `IMAP4` (monkeypatch) na atrapę. Testy sprawdzają, że `select` dostaje `readonly=True`, że `FETCH` używa `BODY.PEEK[]` i że brane jest tylko ostatnie `limit` UID-ów, oraz mapowanie błędów logowania, sieci i protokołu.
- Serwis i API:
  - pierwsze pobranie z `FakeMailbox` tworzy wiersze, a drugie daje `created=0` i `duplicates>0`;
  - 401 bez sesji, sales i supervisor dostają 200;
  - `UnconfiguredMailbox` daje 503;
  - zajęta blokada daje 409 (blokada wzięta w teście na osobnym połączeniu).
- Testy sprzątają wiersze `source='mailbox'` ze swoim znacznikiem domeny. Fake w testach używa adresów `@<marker>.test`.
- Ustawienia: pusty `IMAP_PASSWORD` daje `None`.

### Success Criteria:

#### Automated Verification:

- Testy skrzynki przechodzą: `docker compose run --rm backend uv run pytest tests/test_mailbox_client.py tests/test_mailbox_service.py tests/test_mailbox_api.py`
- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`

#### Manual Verification:

- `curl` z cookie sesji na `POST /api/mailbox/fetch` przy domyślnym `fake` zwraca `created: 2`, a drugi raz `created: 0, duplicates: 2`
- Logi backendu po pobraniu zawierają tylko liczby, bez tematów i adresów

---

## Phase 3: Frontend — przycisk i znaczek

### Overview

Przycisk „Fetch mail” w skrzynce, komunikat wyniku albo błędu, przeładowanie listy i znaczek „E-mail” przy zapytaniach z poczty.

### Changes Required:

#### 1. Klient API

**File**: `frontend/src/api/mailbox.ts`, `frontend/src/api/inquiries.ts`

**Intent**: Wywołać endpoint pobierania z walidacją odpowiedzi jak w pozostałych modułach API i rozszerzyć typ zapytania o źródło.

**Contract**:
- `fetchMail(): Promise<FetchResult>` przez `requestJson` (POST), ze strażnikiem typu dla czterech liczb.
- `InquirySummary.source: "sample" | "mailbox"`, a `isInquirySummary` sprawdza to pole.

#### 2. Skrzynka

**File**: `frontend/src/components/Inbox.tsx` (+ style obok istniejących klas `inbox__*`)

**Intent**: Dać handlowcowi akcję pobrania obok nagłówka listy i pokazać, co się stało, bez gubienia wybranego zapytania.

**Contract**:
- Przycisk „Fetch mail” przy `<h2 id="inbox-heading">`, wyłączony w trakcie (etykieta „Fetching…”).
- Po sukcesie:
  - komunikat `aria-live="polite"`, np. „2 new, 3 already in inbox” albo „No new mail”;
  - gdy `skipped > 0`, dopisek „1 skipped”;
  - przeładowanie listy przy zachowaniu wybranego zapytania.
- Po błędzie: komunikat ze statusu, np. „Mailbox not configured” albo „Mailbox unavailable, try again”.
- Przy zapytaniach z `source === "mailbox"` na liście znaczek „E-mail”.

#### 3. Testy

**File**: `frontend/src/components/Inbox.test.tsx`

**Intent**: Pokryć przycisk, komunikaty i znaczek na zamockowanym `fetch`, jak w istniejących testach.

**Contract**: Przypadki:
- kliknięcie wywołuje POST i drugi GET listy, nowe zapytanie ma znaczek;
- `created=0` daje „No new mail”;
- 503 daje komunikat konfiguracji;
- przycisk jest wyłączony w trakcie.

### Success Criteria:

#### Automated Verification:

- Lint przechodzi: `cd frontend && npm run lint`
- Typy przechodzą: `cd frontend && npm run typecheck`
- Testy frontendu przechodzą: `cd frontend && npm test`

#### Manual Verification:

- W `docker compose up -d --build` (domyślne `fake`) kliknięcie „Fetch mail” pokazuje 2 nowe zapytania ze znaczkiem „E-mail”, a drugie kliknięcie pokazuje „No new mail”
- Nowe zapytanie da się otworzyć i przeanalizować („Analyze request”) jak przykładowe

---

## Phase 4: GreenMail, przykładowe maile i dokumentacja

### Overview

Lokalny serwer IMAP do ręcznej próby bez konta, polecenie wrzucające do niego przykładowe maile oraz instrukcja dla Gmaila i Render.

### Changes Required:

#### 1. GreenMail w compose

**File**: `docker-compose.yml`

**Intent**: Opcjonalny lokalny serwer IMAP, który nie startuje domyślnie.

**Contract**:
- Usługa `mail` z profilem `mail`, obraz `greenmail/standalone` w konkretnej wersji 2.x, IMAP bez TLS na porcie 3143.
- Użytkownik testowy przez `GREENMAIL_OPTS`, np. `-Dgreenmail.setup.test.all -Dgreenmail.hostname=0.0.0.0 -Dgreenmail.users=sales:demo@mail.local`.
- Port hosta konfigurowalny (`MAIL_IMAP_HOST_PORT`, domyślnie 3143).
- Komentarz z ustawieniami `.env` do lokalnej próby: `MAILBOX_PROVIDER=imap`, `IMAP_HOST=mail`, `IMAP_PORT=3143`, `IMAP_SSL=false`, `IMAP_USERNAME=sales`, `IMAP_PASSWORD=demo`.

#### 2. Przykładowe maile do GreenMail

**File**: `backend/app/mailbox/demo.py`

**Intent**: Jednym poleceniem wrzucić do lokalnej skrzynki maile pokazujące konwersję: zwykły tekst z podpisem, HTML i odpowiedź z cytatem. Narzędzie dotyka tylko lokalnej skrzynki deweloperskiej.

**Contract**: `python -m app.mailbox.demo` ma `def main() -> int`.
- Odmawia (kod 2) poza wszystkimi naraz spełnionymi warunkami: `mailbox_provider == "imap"`, `imap_ssl` wyłączone i host w `{"mail", "localhost", "127.0.0.1"}`. Zapobiega to zapisowi do prawdziwej skrzynki.
- Wrzuca 3 maile z adresami `.example` przez `IMAP APPEND`. Każde uruchomienie dokłada kopie, a dedup po `Message-ID` sprawia, że w aplikacji pojawią się raz.
- Wzorzec CLI jak `app/auth/demo_accounts.py`.

#### 3. Dokumentacja

**File**: `README.md`

**Intent**: Opisać, jak włączyć odczyt skrzynki lokalnie, na Gmailu i na Render, oraz co jest gwarantowane: tylko odczyt, brak treści w logach, okno 20 najnowszych.

**Contract**: Nowa sekcja „Test mailbox (read-only)”:
- tryb `fake` jako domyślny;
- GreenMail: `docker compose --profile mail up -d mail`, wpisy do `.env`, `python -m app.mailbox.demo`;
- Gmail: dedykowane konto, 2FA, hasło aplikacji, `imap.gmail.com:993`;
- Render: zmienne w Dashboardzie i restart;
- ograniczenia z „What We're NOT Doing” w skrócie.

#### 4. Test CLI demo

**File**: `backend/tests/test_mailbox_demo.py`

**Intent**: Strażnik hosta jest jedyną barierą przed zapisem do prawdziwej skrzynki, więc musi być przetestowany.

**Contract**: `main()` zwraca 2 dla `fake`, dla `imap_ssl=True` i dla hosta `imap.gmail.com`, nie łącząc się z siecią (atrapa `imaplib` nie jest wywołana).

### Success Criteria:

#### Automated Verification:

- Test strażnika demo przechodzi: `docker compose run --rm backend uv run pytest tests/test_mailbox_demo.py`
- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Konfiguracja compose jest poprawna: `docker compose --profile mail config --quiet`

#### Manual Verification:

- Z GreenMailem i `MAILBOX_PROVIDER=imap` „Fetch mail” pokazuje 3 nowe zapytania. Odpowiedź z cytatem ma treść bez cytatu i z podpisem na końcu. Mail HTML ma czysty tekst. Drugie kliknięcie pokazuje „No new mail”.
- Na dedykowanym Gmailu z hasłem aplikacji „Fetch mail” pobiera wysłane testowe maile, a w Gmailu pozostają one nieprzeczytane
- Złe hasło daje w UI „Mailbox login failed”, a w logach tylko klasę błędu

---

## Testing Strategy

### Unit Tests:

- Konwersja maila: kodowania, multipart, HTML, cytaty, limity, daty, brak nagłówków, prefiks `[eval] `.
- Klient IMAP na atrapie `imaplib`: tryb tylko do odczytu, `BODY.PEEK[]`, okno UID-ów, mapowanie błędów bez łańcuchowania.
- Fabryka `get_mailbox` dla `fake`, `imap` bez danych i `imap` z danymi.

### Integration Tests:

- Zapis z dedupem na prawdziwym Postgresie (`ON CONFLICT`).
- Endpoint: auth, 200, 409, 503, oraz `source` w `GET /api/inquiries`.

### Manual Testing Steps:

1. `docker compose up -d --build`, logowanie jako `sales`, „Fetch mail” w trybie `fake`: 2 nowe zapytania, potem „No new mail”.
2. `docker compose --profile mail up -d mail`, `.env` jak w komentarzu compose, restart `app`, `docker compose run --rm backend uv run python -m app.mailbox.demo`, „Fetch mail”: 3 nowe zapytania. Otworzyć odpowiedź z cytatem i HTML, potem „Analyze request” na jednym z nich.
3. Dedykowany Gmail: wysłać 2 maile, ustawić `.env` (hasło aplikacji), „Fetch mail”, sprawdzić, że w Gmailu są nadal nieprzeczytane.
4. Złe hasło: komunikat w UI, w logach tylko klasa błędu.

## Performance Considerations

Jedno pobranie to jedno połączenie IMAP, jedno `SEARCH` i jedno `FETCH` co najwyżej 20 wiadomości, synchronicznie w żądaniu. Przy testowej skrzynce i timeoucie 15 s na operację mieści się to w żądaniu HTTP. Lista skrzynki nadal nie ma paginacji, co przy testowej skali jest akceptowalne.

## Migration Notes

`0014` dodaje kolumny z wartością domyślną, więc istniejące wiersze dostają `sample` bez przepisywania danych. `downgrade` usuwa kolumny razem z informacją o źródle: zapytania z poczty zostają jako zwykłe. Lekcja o JSONB (`context/foundation/lessons.md`) nie dotyczy tej zmiany, bo pola nie są w JSONB.

## References

- Research: `context/changes/test-mailbox-ingest/research.md`
- Wzorzec integracji zewnętrznej: `backend/app/parsing/extractor.py:48-84`, `backend/app/llm/client.py:33-124`
- Wzorzec blokady: `backend/app/eval/runner.py:138-152`
- Wzorzec CLI: `backend/app/auth/demo_accounts.py`
- Odłożone pola: `context/archive/2026-11-09-login-and-inbox/plan.md:39`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Model i konwersja maila

#### Automated

- [x] 1.1 Migracja 0014 wchodzi i schodzi — 40504d7
- [x] 1.2 Testy konwersji i zapisu przechodzą — 40504d7
- [x] 1.3 Wszystkie bramki backendu przechodzą — 40504d7

#### Manual

- [x] 1.4 Przykładowe zapytania mają source = sample i external_id NULL — 40504d7

### Phase 2: Klient skrzynki i endpoint

#### Automated

- [x] 2.1 Testy skrzynki przechodzą — 1c6b3e0
- [x] 2.2 Wszystkie bramki backendu przechodzą — 1c6b3e0

#### Manual

- [x] 2.3 curl na POST /api/mailbox/fetch w trybie fake: 2 nowe, potem 0 nowych — 1c6b3e0
- [x] 2.4 Logi po pobraniu zawierają tylko liczby — 1c6b3e0

### Phase 3: Frontend — przycisk i znaczek

#### Automated

- [x] 3.1 Lint przechodzi — 861a8e3
- [x] 3.2 Typy przechodzą — 861a8e3
- [x] 3.3 Testy frontendu przechodzą — 861a8e3

#### Manual

- [x] 3.4 Fetch mail w trybie fake pokazuje 2 zapytania ze znaczkiem, potem No new mail — 861a8e3
- [x] 3.5 Zapytanie z poczty da się przeanalizować — 861a8e3

### Phase 4: GreenMail, przykładowe maile i dokumentacja

#### Automated

- [x] 4.1 Test strażnika demo przechodzi
- [x] 4.2 Wszystkie bramki backendu przechodzą
- [x] 4.3 Konfiguracja compose jest poprawna

#### Manual

- [x] 4.4 GreenMail: 3 nowe zapytania, cytat odcięty, HTML jako tekst, potem No new mail
- [ ] 4.5 Gmail: maile pobrane i nadal nieprzeczytane
- [x] 4.6 Złe hasło: komunikat w UI, w logach tylko klasa błędu
