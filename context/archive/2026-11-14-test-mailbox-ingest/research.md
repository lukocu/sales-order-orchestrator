---
date: 2026-11-14T17:35:44+01:00
researcher: Claude (Opus 5.5) for lukocu
git_commit: e39e980
branch: claude/recursing-solomon-072a8c
repository: agent-orchestrator
topic: "S-09 test-mailbox-ingest: co trzeba podłączyć, żeby zapytania z testowej skrzynki IMAP trafiały do skrzynki handlowca"
tags: [research, inquiries, inbox, imap, settings, deploy, s-09]
status: complete
last_updated: 2026-11-14
last_updated_by: Claude (Opus 5.5)
---

# Research: odczyt testowej skrzynki e-mail (S-09, FR-013)

**Date**: 2026-11-14T17:35:44+01:00
**Git Commit**: e39e980
**Branch**: claude/recursing-solomon-072a8c
**Repository**: agent-orchestrator

## Research Question

Jak zapytania trafiają dziś do systemu i do czego musi się podłączyć funkcja, która czyta dedykowaną testową skrzynkę e-mail (tylko odczyt) i pokazuje te maile w skrzynce handlowca (FR-013, roadmapa S-09)? Jakie ograniczenia (prywatność, deploy, parser, długości pól) wpływają na projekt?

## Summary

- **Dziś zapytania powstają w dwóch miejscach:** seed w migracji `0003` (4 przykładowe) oraz runner ewaluacji (`[eval] `, tymczasowe). Nie istnieje żaden endpoint tworzący zapytania (`backend/app/api/inquiries.py` ma tylko dwa GET-y).
- **Tabela `inquiries` jest celowo „w kształcie maila”** (`backend/app/inquiries/models.py:8`). Odłożono w niej do S-09 pola `source` / `message_id` (`context/archive/2026-11-09-login-and-inbox/plan.md:39`). Dziś brak kolumny na identyfikator zewnętrzny, więc deduplikacja wymaga migracji `0014` (head: `0013_supervisor_decisions`).
- **Nie ma żadnej pracy w tle.** Wszystko jest synchroniczne w żądaniu: jeden proces uvicorn (`backend/start.sh:8`), Render free usypia usługę po ~15 min bez ruchu (`README.md:599`). Cykliczne pobieranie w procesie nie odpali się podczas uśpienia, więc naturalnym wyzwalaczem jest **ręczne „Pobierz pocztę”** (POST) i/lub pobranie przy wejściu do skrzynki.
- **Brak biblioteki pocztowej w zależnościach.** Wystarczą stdlib `imaplib` + `email` (Python 3.14, `backend/pyproject.toml:5`).
- **Wzorzec klienta zewnętrznego jest gotowy do skopiowania:** Protocol + `Fake*` + `Unconfigured*` + fabryka `get_*(settings)` jako zależność FastAPI (`backend/app/parsing/extractor.py:48-84`). Do tego sekrety jako `SecretStr | None` z walidatorem „pusty string = brak” (`backend/app/settings.py:60-63`).
- **Twarde ograniczenia:**
  - **prywatność:** tylko dedykowana skrzynka, tylko odczyt, wysyłka symulowana (`context/foundation/prd.md:71-72,135`);
  - **logi:** nigdy treści zapytania, tylko klasa błędu i id (konwencja w ~20 miejscach, np. `backend/app/api/analysis.py:99`);
  - **długości pól:** w bazie `sender_name` 200, `subject` 300, `sender_email` 320 (`backend/app/inquiries/models.py:13-15`);
  - **czysty tekst:** parser regułowy zakłada polski tekst z podpisem w ostatniej linii (`backend/app/parsing/fake.py:83-91`), więc HTML, cytaty odpowiedzi i stopki trzeba sprowadzić do czystego tekstu.
- **Otwarte decyzje produktowe** (do `/10x-plan`): wyzwalacz (przycisk / przy wejściu / zewnętrzny cron), kto może pobierać (każdy zalogowany czy tylko przełożony), filtr wiadomości (wszystkie / UNSEEN / od daty), czy pokazywać źródło w UI, dostawca testowej skrzynki.

## Detailed Findings

### Model danych i wejście zapytań

- **Kolumny `Inquiry`** (`backend/app/inquiries/models.py:12-17`): `id` PK, `sender_name` max 200, `sender_email` max 320, `subject` max 300, `body` Text, `received_at` timestamptz z nieunikalnym indeksem. Poza PK nie ma unikalnych ograniczeń. Brak `source`, `message_id`, `created_at`.
- **Seed:** 4 przykładowe zapytania w `op.bulk_insert` w `backend/migrations/versions/0003_users_inquiries.py:146` (lista :41-103). Adresy `.example` (RFC 2606), treść po polsku, `received_at` od 2026-11-02 do 2026-11-05. Brak znacznika źródła.
- **Runner ewaluacji** (`backend/app/eval/runner.py:57,313-350`) wstawia zapytania z prefiksem tematu `[eval] ` i kasuje wszystko z tym prefiksem (wraz z `TraceRun`). Ingest **nie może** produkować tematów zaczynających się od `[eval] `, bo sprzątanie eval by je usunęło. To ryzyko teoretyczne, ale realne dla maila zatytułowanego „[eval] …”.
- **Zależności z kaskadą:** analizy, checks, orchestration, recommendation, policy, drafts i decisions mają FK `inquiry_id` z `ON DELETE CASCADE`. Trace runs nie mają FK (subject_id jako string). Ingest tylko dodaje wiersze, więc kaskady go nie dotyczą. Nowe zapytanie pojawia się z `outcome=None` i `draft_status=None`, a analizę uruchamia handlowiec jak dla seedów.
- **Deduplikacja:** naturalny klucz to nagłówek `Message-ID` (lub IMAP UID + UIDVALIDITY). Nullable `source` + `external_id` z unikalnym indeksem na parze nie koliduje z 4 seedami, bo Postgres dopuszcza wiele NULL-i w unikalnym indeksie. Zgodnie z lekcją z `context/foundation/lessons.md` (JSONB) nowe pola dodane jako opcjonalne nie wymagają migracji danych. Tu nie ma JSONB, więc lekcja dotyczy pośrednio.

### API skrzynki i frontend

- **API:** `GET /api/inquiries` (`backend/app/api/inquiries.py:54-67`) zwraca pełną listę bez paginacji, sortowaną `received_at DESC, id DESC`. `GET /api/inquiries/{id}` (:70-86). Router jest pod `protected_router` z `Depends(get_current_user)` (`backend/app/main.py:13-16`), więc każdy zalogowany widzi wszystko.
- **Schematy:** `InquirySummary` (:24-32) zawiera id, sender_name, sender_email, subject, received_at, outcome, draft_status. `InquiryDetail` (:35-36) dodaje body. Ewentualne pole `source` trzeba dodać tu oraz w strażniku typu `isInquirySummary` (`frontend/src/api/inquiries.ts:19-36`).
- **Frontend:** `frontend/src/components/Inbox.tsx` pobiera listę raz przy montowaniu (:48-59). Ponowne pobranie następuje tylko przez „Retry” po błędzie (:112-115). Nie ma przycisku odświeżania ani pollingu, więc nowe maile nie pojawią się bez przeładowania strony. Do dodania: przycisk „Pobierz pocztę”, który wywołuje POST i przeładowuje listę.
- **Ochrona POST:** cookie sesyjne `samesite="lax"` (`backend/app/api/auth.py:47,97`), brak tokenu CSRF. Role: `require_supervisor` (`backend/app/auth/deps.py:59-65`), użyty np. w `backend/app/api/analysis.py:515-535`.

### Ustawienia, sekrety i wzorzec klienta

- **Ustawienia:** pydantic-settings `BaseSettings` (`backend/app/settings.py:22-29`) czyta `.env` z katalogu repo i `backend/`. Nazwy zmiennych to wielkie litery bez prefiksu. Sekrety są typu `SecretStr | None` (:40, :51). Walidator `_empty_string_is_unset` (:60-63) obejmuje tylko wymienione pola, więc nowe sekrety IMAP trzeba do niego dopisać, bo compose przekazuje `${X:-}` jako `""`.
- **Wzorzec dostawcy:** `LLM_PROVIDER: Literal["fake","groq","openrouter"] = "fake"` (`backend/app/settings.py:11,50`). Fabryka `get_extractor` (`backend/app/parsing/extractor.py:67-84`) zwraca:
  - fake, gdy provider to `fake`;
  - `Unconfigured*`, gdy brakuje klucza (API mapuje to na 503);
  - w pozostałych przypadkach prawdziwego klienta, importowanego leniwie.

  Ten sam kształt mają `get_drafter`, `get_planner` i `get_recommender`.
- **Klient HTTP LLM** (`backend/app/llm/client.py:33-124`):
  - typowana hierarchia błędów (timeout, sieć, zła odpowiedź);
  - komunikaty bez treści żądania i odpowiedzi;
  - wstrzykiwany `transport` jako szew testowy.

  Analogicznie dla IMAP przydadzą się:
  - `imaplib.IMAP4_SSL(host, timeout=...)`;
  - mapowanie `imaplib.IMAP4.error`, `OSError` i `TimeoutError` na własne błędy bez treści;
  - fake skrzynka w pamięci w testach.
- **Testy:** zależności podmieniane przez `app.dependency_overrides[get_x]` (`backend/tests/conftest.py:174-213`). Testy używają prawdziwego Postgresa i znaczników procesu (`TEST_EMAIL_DOMAIN` = `<marker>.test`, :30-40), sprzątając tylko swoje wiersze. CI nie ma sekretów (`.github/workflows/ci.yml`), więc testy muszą działać na fake'u.

### Praca w tle i deploy

- **Brak pracy w tle:** w `backend/app` nie ma BackgroundTasks, lifespan, schedulera, cronu ani tabeli zadań. Równoległość istnieje tylko wewnątrz żądania (`backend/app/orchestration/executor.py:15,126`, ThreadPoolExecutor).
- **Proces:** `backend/start.sh:6-8` uruchamia migracje, potem synchronizację haseł demo, potem `exec uvicorn` jako jeden proces bez `--workers`.
- **Render:** `render.yaml` definiuje jedną usługę web na planie free, bez workera i cron joba. Sekrety mają `sync: false`, a w istniejących usługach trzeba je ustawić ręcznie w Dashboardzie (README ~:590-597). Render free usypia usługę po ~15 min (`README.md:599`). Supabase free pauzuje po tygodniu bez aktywności (`README.md:601`).
- **Blokada przed równoległym pobieraniem:** wzorzec `_run_lock` z advisory lockiem sesyjnym (`backend/app/eval/runner.py:138-152`) można powtórzyć z innym kluczem, żeby dwa kliknięcia nie pobrały tego samego naraz. Unikalny indeks na `(source, external_id)` i tak chroni przed duplikatem. Blokada sesyjna wymaga session poolera, a ten jest używany na Supabase.
- **Lokalny serwer testowy:** w `docker-compose.yml` nie ma serwisu pocztowego. Do testów manualnych bez prawdziwego konta można dodać np. GreenMail (IMAP) jako opcjonalny profil. Automatyczne testy zostają na fake'u.

### Parser a format maila

- **Ekstraktor LLM** (`backend/app/parsing/openai_compatible.py:14-15,108`): przycina temat do 500 znaków, a treść do `MAX_BODY_CHARS = 8000`. System prompt opisuje „e-mail po polsku” i każe traktować temat i treść jako dane, nie instrukcje.
- **Ekstraktor regułowy** (`backend/app/parsing/fake.py:83-91`): klienta bierze z ostatniej niepustej linii treści (podpisu). Cytowana odpowiedź („> …”), stopka lub HTML w ostatnich liniach dadzą złego klienta albo pusty wynik.
- **Wniosek:** ingest powinien wybrać część `text/plain`. Gdy jej brak, konwertuje HTML do tekstu (np. `html.parser` ze stdlib, bez nowej zależności). Wynik normalizuje: dekoduje nagłówki RFC 2047 (`email.header` / `email.policy.default`) i przycina pola do limitów bazy. Odcinanie cytatów jest opcjonalne. Załączniki są poza zakresem, bo nic ich nie konsumuje.
- **Dopasowanie klienta:** `backend/app/checks/rules.py:101-112` wraca do domeny adresu nadawcy. Prawdziwe maile z domen spoza symulowanych danych firmowych dadzą więc „nieznany klient”. To zgodne z założeniem MVP, ale warto dać autorowi wskazówkę, by testowe maile wysyłał z treścią i podpisem pasującymi do danych przykładowych (np. „ACME”).

## Code References

- `backend/app/inquiries/models.py:7-17`: model `Inquiry` w kształcie maila, bez `source` i `message_id`.
- `backend/migrations/versions/0003_users_inquiries.py:41-103,146`: seed 4 zapytań; następna migracja to `0014`.
- `backend/app/api/inquiries.py:24-86`: schematy i dwa endpointy GET.
- `backend/app/main.py:13-21`: `protected_router` (uwierzytelnienie cookie).
- `backend/app/auth/deps.py:40-65`: `get_current_user`, `require_supervisor`.
- `backend/app/settings.py:11,22-63`: ustawienia, `SecretStr`, walidator pustych stringów.
- `backend/app/parsing/extractor.py:48-84`: wzorzec Protocol + Fake + Unconfigured + fabryka.
- `backend/app/llm/client.py:33-124`: hierarchia błędów klienta zewnętrznego, bez treści w komunikatach.
- `backend/app/eval/runner.py:57,138-152,313-350`: prefiks `[eval] `, advisory lock, wstawianie i usuwanie zapytań.
- `backend/start.sh:6-8`: jeden proces uvicorn.
- `README.md:599-601`: usypianie Render free i pauza Supabase.
- `frontend/src/components/Inbox.tsx:48-59,112-115`: lista pobierana raz, bez odświeżania.
- `frontend/src/api/inquiries.ts:19-36`: strażnik typu `isInquirySummary`.
- `backend/app/parsing/fake.py:83-91`: klient z ostatniej linii podpisu.
- `backend/app/parsing/openai_compatible.py:14-15`: limity 8000 i 500 znaków dla LLM.

## Architecture Insights

- Nowa integracja zewnętrzna wchodzi w repo zawsze tym samym kształtem: `*_PROVIDER` z domyślnym `fake`, Protocol, `Fake*`, `Unconfigured*`, `get_*(settings)` jako `Depends`, typowane błędy bez treści, test przez `dependency_overrides`. Skrzynka powinna to powtórzyć, np. `MAILBOX_PROVIDER=fake|imap`, `IMAP_HOST`, `IMAP_PORT`, `IMAP_USERNAME`, `IMAP_PASSWORD: SecretStr | None`, `IMAP_FOLDER=INBOX` i `IMAP_TIMEOUT_SECONDS`.
- „Tylko odczyt” po stronie IMAP: `SELECT` z `readonly=True` (IMAP `EXAMINE`) oraz `FETCH` z `BODY.PEEK[]`, dzięki czemu flaga `\Seen` się nie zmienia. Dedykowane konto i hasło aplikacji (np. Gmail wymaga 2FA i hasła aplikacji) to warunek po stronie autora. To fakty z RFC 3501 i dokumentacji dostawców, nie z repo.
- Domena logowania: tylko liczby (pobrane, nowe, pominięte), UID-y i klasy błędów. Nigdy temat, nadawca, treść ani surowe odpowiedzi IMAP, bo mogą cytować dane (konwencja, np. `backend/app/api/analysis.py:99`, `backend/app/llm/client.py:3-4`).
- Synchroniczny POST mieści się w istniejącym modelu (endpointy `def` w threadpoolu). Przy małej testowej skrzynce i limicie liczby wiadomości na jedno pobranie czas odpowiedzi jest ograniczony.

## Historical Context (from prior changes)

- `context/archive/2026-11-09-login-and-inbox/plan.md:39`: pola `source` / `message_id` jawnie odłożone do S-09. Twierdzenie nadal aktualne, bo model ich nie ma.
- `context/archive/2026-11-09-login-and-inbox/research.md:109`: „pola message-id czy źródło nie są nigdzie wymagane; to wnioskowanie”. Nadal prawdziwe: żaden dokument nie narzuca ich kształtu.
- `context/archive/2026-11-09-step-cost-tracing/research.md:171`, `context/archive/2026-11-10-parse-inquiry/plan.md:36-45`: prompty i odpowiedzi modelu nie są zapisywane, z uwagą na prawdziwą pocztę (FR-013). Wciąż obowiązuje; ingest nic tu nie zmienia.
- `context/archive/2026-11-11-orchestrator-plan-and-delegation/plan.md:54`: planner widzi tylko ustrukturyzowane fakty, nie tekst maila. Ingest tego nie narusza.
- `context/archive/2026-11-13-workflow-vs-orchestrator-eval/plan.md:474,529`: skrzynka ma zostać czysta po eval, stąd ryzyko kolizji z prefiksem `[eval] ` (wyżej).
- `context/foundation/roadmap.md:208-218`: S-09 `blocked` przez Open Question 1. Wszystkie pozostałe slice'y M-1 są `done`, więc zasada „najpierw pionowy wycinek” jest spełniona. Formalne odblokowanie (zamknięcie Question 1) należy do autora.
- `context/team/opportunity-map.md:19,39`: prawdziwa poczta to dane osobowe, więc dostęp trzeba uzgodnić. Spełnia to dedykowana skrzynka testowa.

## Related Research

- `context/archive/2026-11-09-login-and-inbox/research.md`: kształt tabeli `inquiries` i skrzynki.
- `context/archive/2026-11-10-parse-inquiry/research.md`: parser i limity tekstu.

## Open Questions

Decyzje dla autora przed lub w trakcie `/10x-plan`:

1. **Wyzwalacz pobierania:** przycisk „Pobierz pocztę” (polecane, działa mimo usypiania Render), pobranie przy wejściu do skrzynki, czy zewnętrzny cron pingujący endpoint.
2. **Uprawnienia:** każdy zalogowany (sales i supervisor) czy tylko przełożony.
3. **Zakres wiadomości:** wszystkie w folderze, tylko nowsze od ostatniego UID, czy od daty. Do tego limit liczby wiadomości na jedno pobranie.
4. **Widoczność źródła w UI:** znacznik „e-mail” vs „przykładowe” na liście.
5. **Dostawca testowej skrzynki:** Gmail z hasłem aplikacji, inne konto IMAP, czy lokalny GreenMail tylko do demo.
6. **Obróbka treści:** czy odcinać cytowane odpowiedzi i stopki, czy przekazywać pełny tekst.
7. **Formalne zamknięcie Open Roadmap Question 1:** FR-013 jako ostatni krok MVP, zapis w roadmapie i PRD.

Luki dowodowe: zachowanie konkretnego dostawcy IMAP (limity, wymóg OAuth zamiast hasła aplikacji) nie zostało sprawdzone, bo dostawca nie jest jeszcze wybrany.
