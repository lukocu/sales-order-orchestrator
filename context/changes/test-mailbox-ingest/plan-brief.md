# Odczyt testowej skrzynki e-mail (S-09) — Plan Brief

> Full plan: `context/changes/test-mailbox-ingest/plan.md`
> Research: `context/changes/test-mailbox-ingest/research.md`

## What & Why

Handlowiec ma widzieć w skrzynce zapytania odczytane z dedykowanej testowej skrzynki e-mail, tylko do odczytu (FR-013, S-09). To ostatni otwarty wycinek M-1. Wszystkie pozostałe są `done`, więc zasada „najpierw pionowy wycinek, potem prawdziwa poczta” jest spełniona.

## Starting Point

Zapytania pochodzą dziś tylko z seedu migracji `0003` (4 przykładowe) i z runnera eval. Tabela `inquiries` ma kształt maila, ale nie ma pól `source` ani identyfikatora wiadomości, bo S-01 odłożył je do S-09. Aplikacja nie ma pracy w tle (jeden proces uvicorn, Render free usypia usługę), a skrzynka we froncie ładuje listę raz.

## Desired End State

W skrzynce jest przycisk „Fetch mail”. Pobiera 20 najnowszych wiadomości z testowej skrzynki IMAP w trybie tylko do odczytu i dodaje te, których jeszcze nie ma. Nowe zapytania mają znaczek „E-mail” i przechodzą tę samą analizę co przykładowe. Bez konfiguracji działa skrzynka `fake`. Lokalnie można użyć GreenMaila, a na demo dedykowanego Gmaila z hasłem aplikacji.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
|---|---|---|---|
| Wyzwalacz | Przycisk „Fetch mail”, synchroniczny POST | Działa mimo usypiania Render free i nie wymaga pracy w tle | Plan |
| Uprawnienia | Każdy zalogowany (sales, supervisor) | FR-013 mówi o skrzynce handlowca; handlowiec sam ściąga nowe zapytania | Plan |
| Zakres | 20 najnowszych (UID), dedup po Message-ID | Idempotentne, niezależne od flagi `\Seen` i od zapamiętanego UID | Plan |
| Tylko odczyt | `EXAMINE` + `BODY.PEEK[]`, brak zmian w skrzynce | Wymóg PRD (dane osobowe, dedykowana skrzynka) | Research |
| Treść | `text/plain` (lub HTML → tekst), cytat odcięty | Podpis zostaje w ostatniej linii, więc parser regułowy znajduje klienta | Plan |
| Model | `source` (`sample`/`mailbox`) + `external_id` = sha256 Message-ID, unikalny indeks | Odłożone przez S-01; `ON CONFLICT DO NOTHING` bez wyścigów | Research + Plan |
| Integracja | `MAILBOX_PROVIDER=fake\|imap`, Protocol, Fake, Unconfigured, Imap | Ten sam wzorzec co LLM; testy i CI bez sieci | Research |
| UI źródła | Znaczek „E-mail” na liście | Na demo widać, że FR-013 działa | Plan |
| Test ręczny | GreenMail w compose + jedna próba na Gmailu | Lokalna pętla bez sekretów i sprawdzenie prawdziwego dostawcy | Plan |
| Logi | Tylko liczby i klasy błędów, wyjątki IMAP bez łańcucha | Konwencja repo: nigdy treść zapytania | Research |

## Scope

**In scope:**
- migracja `0014` i model;
- konwersja maila (nagłówki, treść, cytaty, limity, kolizja z `[eval] `);
- zapis bez duplikatów;
- klient skrzynki, serwis z blokadą advisory i `POST /api/mailbox/fetch`;
- `source` w API;
- przycisk, komunikat i znaczek;
- GreenMail i `python -m app.mailbox.demo`;
- README, `.env.example`, compose, `render.yaml`.

**Out of scope:**
- automatyczne pobieranie (timer, cron, przy wejściu) i stan UID;
- jakakolwiek zmiana w skrzynce IMAP oraz wysyłka;
- załączniki i wątki;
- OAuth2;
- tracing kosztu pobrania;
- auto-analiza po pobraniu;
- paginacja.

## Architecture / Approach

Przepływ: `Inbox` (przycisk) → `POST /api/mailbox/fetch` → `fetch_mailbox`. Serwis bierze blokadę advisory, pobiera `Mailbox.latest(20)` (fake albo IMAP), zamienia każdy mail przez `to_candidate` na kandydata albo pominięcie, zapisuje przez `insert_new` (`ON CONFLICT DO NOTHING`) i zwraca `{fetched, created, duplicates, skipped}`. Frontend pokazuje wynik i przeładowuje listę. Zapytania z poczty dalej idą istniejącą ścieżką analizy.

## Phases at a Glance

| Phase | What it delivers | Key risk |
|---|---|---|
| 1. Model i konwersja maila | `source`/`external_id`, `to_candidate`, `insert_new` z testami | Heurystyka cięcia cytatów zbyt agresywna lub zbyt słaba |
| 2. Klient skrzynki i endpoint | Ustawienia, Fake/Unconfigured/Imap, serwis z blokadą, POST, `source` w API | Wyjątki `imaplib` cytujące dane serwera, jeśli mapowanie coś pominie |
| 3. Frontend | Przycisk, komunikaty, przeładowanie, znaczek | Zachowanie wybranego zapytania przy przeładowaniu listy |
| 4. GreenMail i dokumentacja | Lokalny IMAP, skrypt demo ze strażnikiem hosta, README | Różnice GreenMail a Gmail (TLS, hasło aplikacji) |

**Prerequisites:**
- Do faz 1–3 nic poza repo.
- Do ręcznej próby 4.5 potrzebne jest dedykowane konto Gmail z 2FA i hasłem aplikacji, które autor wpisuje sam do `.env`.

**Estimated effort:** ~3–4 sesje, po jednej na fazę (faza 4 krótsza).

## Open Risks & Assumptions

- Testowa skrzynka jest mała, więc synchroniczne pobranie 20 wiadomości mieści się w żądaniu HTTP (timeout 15 s na operację IMAP).
- Gmail nadal pozwala na IMAP z hasłem aplikacji dla kont z 2FA. Jeśli nie, potrzebny będzie OAuth2, który jest poza zakresem.
- Maile spoza symulowanych danych firmowych dadzą „nieznany klient” w sprawdzeniach. Tak ma być w MVP. W README będzie wskazówka, jak pisać testowe maile.
- Open Roadmap Question 1 rozstrzygamy wykonaniem: FR-013 jako ostatni krok MVP. Zapis w roadmapie zrobi `/10x-roadmap` przy zamykaniu M-1.

## Success Criteria (Summary)

- Handlowiec klika „Fetch mail” i widzi nowe zapytania z testowej skrzynki ze znaczkiem „E-mail”. Ponowne kliknięcie niczego nie dubluje.
- W skrzynce nic się nie zmienia: maile zostają nieprzeczytane. Logi nie zawierają treści, tematów ani adresów.
- `check.sh` i bramki frontendu przechodzą bez sieci i sekretów.
