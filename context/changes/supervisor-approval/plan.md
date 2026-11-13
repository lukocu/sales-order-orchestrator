# Supervisor approval (S-08) Implementation Plan

## Overview

Zamykamy ślepy zaułek `awaiting_supervisor` z S-07. Przełożony (i tylko on) zatwierdza albo
odrzuca szkic, który handlowiec przekazał po werdykcie `requires_supervisor`, z obowiązkowym
powodem i zasadą czterech oczu. Handlowiec widzi wynik w statusie i historii decyzji, a skrzynka
pokazuje i filtruje pozycje czekające na przełożonego (FR-009, US-02, roadmap S-08).

## Current State Analysis

- Approve handlowca przy werdykcie w mocy innym niż `no_approval_needed` ustawia
  `awaiting_supervisor` (`backend/app/draft/service.py:298-330`), ale nic z tego statusu nie
  wychodzi: `_locked_draft` wymaga `status == "draft"` (`service.py:757-758`), a regenerate
  odmawia dla `DECIDED` (`service.py:89,232-237`).
- Role są w danych (`Role` w `backend/app/auth/models.py:7`, konta demo `sales` i `supervisor` z
  migracji 0003), `AuthUser.role` jest dostępne w `backend/app/auth/deps.py:22-33`, ale żaden
  endpoint go nie sprawdza.
- Historia decyzji (`inquiry_draft_decisions`) jest append-only: `action` z CHECK
  `ck_inquiry_draft_decisions_action` (`edit|approve|reject`,
  `backend/migrations/versions/0012_drafts_decisions.py:56-59`), `decided_by` FK do `users`,
  snapshot JSONB `DecisionSnapshot(offer, policy_outcome, failing_rules)`
  (`backend/app/draft/schema.py:86-93`), gdzie `failing_rules` ma tylko kody `fail`
  (`service.py:838`).
- `GET /inquiries` zwraca `InquirySummary` z `outcome` sprawdzeń, bez statusu szkicu
  (`backend/app/api/inquiries.py:22-52`); brak indeksu na `inquiry_drafts.status`.
- Frontend: `App.tsx:57-58` przekazuje `user` tylko do `Inbox`; `AnalysisPanel` dostaje
  `inquiryId`, `onUnauthorized`, `onOutcome` (`AnalysisPanel.tsx:33,222`); `ReplyDraftSection`
  pokazuje „Awaiting supervisor approval” i chowa przyciski, bo `canDecide` wymaga `draft`
  (`ReplyDraftSection.tsx:50-55,135-142`).

## Desired End State

- Przełożony zalogowany jako `supervisor` filtruje skrzynkę do „Awaiting supervisor”, otwiera
  zapytanie, widzi werdykt w mocy z tabelą reguł i przyciski decyzji przełożonego; zatwierdza
  (→ `ready_to_send`) albo odrzuca (→ `rejected`), zawsze z powodem.
- Handlowiec (lub przełożony działający jako handlowiec) widzi nowy status i wpis historii
  „Approved by supervisor” / „Rejected by supervisor” z nazwiskiem, czasem, powodem i regułami,
  które nie przeszły (w tym nieocenione); po odrzuceniu może Regenerate jak po własnym Reject.
- `POST /api/inquiries/{id}/draft/supervisor-decision` zwraca 403 dla roli `salesperson`, 409 dla
  szkicu nie w `awaiting_supervisor`, dla zmienionego `updated_at`, dla nieaktualnej rekomendacji
  i dla zatwierdzenia przez osobę, która szkic przekazała (odrzucenie własnego przekazania jest
  dozwolone — działa jak wycofanie, po którym można Regenerate).
- Weryfikacja: bramki backendu i frontendu zielone; demo na Render na dwóch kontach (sales
  przekazuje Deltę, supervisor decyduje).

### Key Discoveries:

- Wzorzec zapisu decyzji: `_locked_draft` (lock analizy, token `updated_at`, status, aktualność
  rekomendacji) → `_policy_in_force` → `_decide` w jednym commicie (`service.py:742-855`). Decyzja
  przełożonego powtarza go z innym wymaganym statusem.
- `rejected` nie jest w `DECIDED`, więc Regenerate po odrzuceniu przełożonego działa bez zmian
  (`service.py:224-237`).
- `DecisionAction` żyje w kolumnie z CHECK, nie w JSONB — nowe akcje wymagają migracji CHECK, nie
  migracji danych. `DecisionSnapshot` ma `extra="forbid"`, więc nowe pole snapshotu musi mieć
  wartość domyślną (`context/foundation/lessons.md:5-10`).
- Endpointy decyzji zwracają pełny `AnalysisView` przez wrappery w
  `backend/app/parsing/service.py:384-400`, mapowanie błędów w `backend/app/api/analysis.py:405-432`.
- Fabryka użytkowników w testach przyjmuje `role=` (`backend/tests/conftest.py:137-141`).

## What We're NOT Doing

- Kolejka nie obejmuje werdyktów `requires_supervisor`, których handlowiec nie przekazał
  (Approve); przełożony decyduje wyłącznie o `awaiting_supervisor`.
- Brak osobnego widoku/endpointu kolejki — filtr w istniejącej skrzynce i decyzja w panelu.
- Brak blokady ponownej analizy/rekomendacji w trakcie oczekiwania: nowa rekomendacja nadal usuwa
  szkic (`_drop_outdated`), historia zostaje z `current=false`; brak powiadomień.
- Brak zamrożonego werdyktu z chwili przekazania — przełożony decyduje na werdykcie w mocy.
- Odrzucenie przez przełożonego nie jest ostateczne (bez nowej blokady Regenerate).
- Brak rozdziału ról w ścieżce handlowca — przełożony nadal może Edit/Approve/Reject jako
  handlowiec (PRD Access Control).
- Brak zmiany znaczenia `failing_rules` (nadal tylko `fail`); nieocenione reguły idą do nowego pola.
- Poza zakresem: limit płatnych wywołań LLM i osobne hasła kont demo (follow-up S-02) — osobna
  zmiana hardeningu.
- Brak wycofania (withdraw) przekazania przez handlowca.
- Brak odświeżania skrzynki na żywo: badge i licznik dla szkicu przekazanego w innej sesji
  pojawiają się po przeładowaniu listy (`Inbox` ładuje ją raz); `onDraftStatus` aktualizuje tylko
  własne decyzje.

## Implementation Approach

Backend najpierw: migracja i serwis decyzji przełożonego (faza 1) to rdzeń reguł — status,
cztery oczy, powód, werdykt w mocy — testowany bez HTTP. Faza 2 dokłada granicę ról (403),
endpoint i status szkicu na liście. Faza 3 przeprowadza użytkownika do panelu szkicu, dodaje
akcje przełożonego, etykiety historii i filtr skrzynki, po czym wdrożenie na Render.

Zasada czterech oczu: „przekazujący” to `decided_by` ostatniej decyzji szkicu (ta sama
`inquiry_id` i `recommended_at`); dopóki szkic jest w `awaiting_supervisor`, ostatnią decyzją jest
z konstrukcji Approve, który go tam przeniósł. `decided_by = NULL` (usunięty użytkownik) nie
blokuje decyzji. Cztery oczy dotyczą tylko approve: obejście polityki jest wyłącznie w
zatwierdzeniu, a reject własnego przekazania to wyjście z `awaiting_supervisor`, gdy w systemie
nie ma drugiego przełożonego (demo ma jedno konto `supervisor`; regenerate odmawia dla `DECIDED`).

## Critical Implementation Details

**State sequencing** — Sprawdzenie ról (403) dzieje się w zależności FastAPI przed jakimkolwiek
odczytem; w serwisie kolejność jest: powód → lock + token + status + aktualność rekomendacji →
cztery oczy → werdykt w mocy. Cztery oczy po locku, żeby ostatnia decyzja była czytana pod tą samą
blokadą co status.

## Phase 1: Model i serwis decyzji przełożonego

### Overview

Nowe akcje w danych i schemacie, rozszerzony snapshot, `supervisor_decide` i `submitted_by` w
widoku szkicu — wszystko testowane na poziomie serwisu.

### Changes Required:

#### 1. Migracja 0013

**File**: `backend/migrations/versions/0013_supervisor_decisions.py`

**Intent**: Dopuścić akcje przełożonego w historii i przyspieszyć filtr skrzynki po statusie
szkicu.

**Contract**: `revision = "0013_supervisor_decisions"`, `down_revision = "0012_drafts_decisions"`.
Upgrade: drop + create `ck_inquiry_draft_decisions_action` z
`action IN ('edit', 'approve', 'reject', 'supervisor_approve', 'supervisor_reject')`; indeks
`ix_inquiry_drafts_status` na `inquiry_drafts.status`. Downgrade: drop indeksu i przywrócenie
starego CHECK — świadomie nie powiedzie się, gdy istnieją decyzje przełożonego (historia jest
audytem, nie kasujemy jej).

#### 2. Modele i schematy

**File**: `backend/app/draft/schema.py`, `backend/app/draft/models.py`

**Intent**: Odzwierciedlić migrację w modelach i dodać nieocenione reguły do snapshotu decyzji.

**Contract**: `DecisionAction = Literal["edit", "approve", "reject", "supervisor_approve",
"supervisor_reject"]`; CHECK w `InquiryDraftDecision.__table_args__` zgodny z migracją; indeks
`status` w `InquiryDraft` (żeby `alembic check` był zielony). `DecisionSnapshot` dostaje
`not_evaluated_rules: list[RuleCode] = Field(default_factory=list)` — stare wiersze walidują się
bez migracji danych.

#### 3. Serwis decyzji

**File**: `backend/app/draft/service.py`

**Intent**: Wyjście z `awaiting_supervisor` decyzją przełożonego według wzorca `decide`, z
zasadą czterech oczu i obowiązkowym powodem.

**Contract**:
- `_locked_draft(session, inquiry_id, updated_at, *, status: DraftStatus = "draft")` — oczekiwany
  status parametrem; przy innym statusie rzuca `NotAwaitingSupervisor`, gdy oczekiwany jest
  `awaiting_supervisor`, a w przeciwnym razie `DraftNotEditable` (ścieżka handlowca bez zmian).
  Kolejność kontroli bez zmian: `DraftChanged` (token) przed błędem statusu, `DraftStale` po nim.
- Nowe wyjątki: `NotAwaitingSupervisor` (szkic nie czeka na przełożonego), `OwnSubmission`
  (zatwierdzający przekazał ten szkic).
- `supervisor_decide(engine, inquiry_id, user, *, updated_at, action: Literal["approve",
  "reject"], reason) -> None`: `_required(reason)` dla obu akcji; lock ze statusem
  `awaiting_supervisor`; `OwnSubmission`, gdy `action == "approve"` i `decided_by` ostatniej
  decyzji szkicu == `user.id` (reject przekazującego przechodzi);
  werdykt w mocy (`_policy_in_force`) — `None` → `PolicyMissing` dla approve, `DraftStale` dla
  reject (jak `decide`); approve → `ready_to_send` (niezależnie od outcome werdyktu w mocy),
  reject → `rejected`; zapis przez `_decide` z akcją `supervisor_approve`/`supervisor_reject`.
  Rola nie jest sprawdzana w serwisie (granica jest w API).
- `_decide` wypełnia `not_evaluated_rules` kodami reguł z werdyktem `not_evaluated` (dla
  wszystkich akcji).
- Helper `_submitted_by(session, row) -> int | None` — `decided_by` ostatniej decyzji (po
  `decided_at`, `id`) z tą samą `inquiry_id` i `recommended_at`; używany przez
  `supervisor_decide` i widok.
- `DraftView.submitted_by: int | None` — id przekazującego, gdy `status ==
  "awaiting_supervisor"`, inaczej `None`.
- Docstring `DECIDED` i `regenerate_draft` bez zmian zachowania.

#### 4. Wrapper widoku analizy

**File**: `backend/app/parsing/service.py`

**Intent**: Zwrócić pełny `AnalysisView` po decyzji przełożonego, jak `decide_draft_inquiry`.

**Contract**: `supervisor_decide_inquiry(engine, inquiry_id, user, *, updated_at, action,
reason) -> AnalysisView` — `_require_analysis`, `supervisor_decide`, `_current_view`.

#### 5. Testy serwisu

**File**: `backend/tests/test_draft_service.py`, `backend/tests/test_draft_models.py`

**Intent**: Przypiąć reguły przejść i audytu.

**Contract**: przypadki — approve i reject przełożonego z `awaiting_supervisor` (status, akcja,
`decided_by`, powód, snapshot z `failing_rules` i `not_evaluated_rules`); brak/pusty powód przy
obu → `ReasonRequired`; szkic w `draft`/`ready_to_send`/`rejected` → `NotAwaitingSupervisor`;
zmieniony `updated_at` → `DraftChanged`; nowa rekomendacja → `DraftStale`; approve przez tego samego
użytkownika co przekazujący → `OwnSubmission`; reject przez przekazującego → `rejected`; przekazujący usunięty (`decided_by` NULL) → decyzja przechodzi;
approve przełożonego, gdy werdykt w mocy jest już `no_approval_needed` → `ready_to_send`;
Regenerate po odrzuceniu przełożonego działa; `DraftView.submitted_by`; stary snapshot bez
`not_evaluated_rules` czyta się; CHECK odrzuca nieznaną akcję.

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Modele zgadzają się z migracją: `docker compose run --rm backend uv run alembic check`
- Testy serwisu i modeli szkicu przechodzą: `docker compose run --rm backend uv run pytest tests/test_draft_service.py tests/test_draft_models.py`

#### Manual Verification:

- Downgrade do 0012_drafts_decisions (bez decyzji przełożonego w bazie) i ponowny upgrade do head przechodzą lokalnie

**Implementation Note**: Po zielonych bramkach zatrzymaj się na ręczne potwierdzenie.

---

## Phase 2: API, role i lista zapytań

### Overview

Granica ról (403), endpoint decyzji przełożonego z mapowaniem błędów oraz status szkicu na liście
i w szczególe zapytania.

### Changes Required:

#### 1. Zależność roli

**File**: `backend/app/auth/deps.py`

**Intent**: Jedno miejsce egzekwowania roli przełożonego.

**Contract**: `require_supervisor(user: Annotated[AuthUser, Depends(get_current_user)]) ->
AuthUser` — 403 `"Supervisor role required"` dla roli innej niż `supervisor`; 401 jak
`get_current_user`.

#### 2. Endpoint decyzji przełożonego

**File**: `backend/app/api/analysis.py`

**Intent**: Wystawić `supervisor_decide` z tymi samymi kodami błędów co decyzja handlowca plus
nowe 409.

**Contract**: `SUPERVISOR_DECISION_PATH = "/inquiries/{inquiry_id}/draft/supervisor-decision"`;
`POST` z `SupervisorDecisionRequest {updated_at: AwareDatetime, action: "approve"|"reject",
reason: str}` (`extra="forbid"`; pusty powód → 422 `"Reason is required"` z serwisu), zależność
`require_supervisor`, odpowiedź `AnalysisView`. `_decision_error` mapuje
`NotAwaitingSupervisor` → 409 `"Draft is not awaiting supervisor"`, `OwnSubmission` → 409
`"Cannot approve your own submission"`; oba dodane do `_DECISION_ERRORS`. Pozostała obsługa
wyjątków jak w `decide_draft`.

#### 3. Status szkicu na liście

**File**: `backend/app/api/inquiries.py`

**Intent**: Skrzynka może pokazać badge i filtr „Awaiting supervisor” bez dodatkowych zapytań.

**Contract**: `InquirySummary.draft_status: DraftStatus | None = None` (dziedziczy
`InquiryDetail`); outer join `InquiryDraft` po `inquiry_id` w `list_inquiries` i `read_inquiry`
(jeden wiersz na zapytanie dzięki `uq_inquiry_drafts_inquiry_id`): `select(Inquiry,
current_outcome(), InquiryDraft.status)` z outer joinem `InquiryDraft` dołożonym po
`with_current_outcome`; `_with_outcome` przyjmuje trzeci argument `draft_status`, a oba endpointy
rozpakowują trzy kolumny. Status raw z tabeli —
nieaktualny szkic w `awaiting_supervisor` też się pokaże, decyzja zwróci wtedy 409 `Draft is
stale`.

#### 4. Testy API

**File**: `backend/tests/test_draft_api.py`, `backend/tests/test_inquiries_api.py`,
`backend/tests/test_auth_api.py`

**Intent**: Przypiąć kontrakt HTTP i granicę ról.

**Contract**: supervisor approve/reject → 200 z nowym statusem i decyzją w `AnalysisView`;
salesperson → 403 (bez zmiany w bazie); bez sesji → 401; brak powodu → 422; szkic nie w
`awaiting_supervisor` → 409; approve własnego przekazania → 409, reject własnego → 200; zmieniony token → 409; nieznane pole →
422; ścieżka handlowca nadal dostępna dla supervisora; `GET /inquiries` i `GET /inquiries/{id}`
zwracają `draft_status` (`null` bez szkicu).

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Testy API szkicu, zapytań i auth przechodzą: `docker compose run --rm backend uv run pytest tests/test_draft_api.py tests/test_inquiries_api.py tests/test_auth_api.py tests/test_analysis_api.py`

#### Manual Verification:

- Lokalnie w /docs: jako `sales` Approve Delty → `awaiting_supervisor`; supervisor-decision jako `sales` → 403; jako `supervisor` bez powodu → 422, z powodem → 200 i `ready_to_send`

**Implementation Note**: Po zielonych bramkach zatrzymaj się na ręczne potwierdzenie.

---

## Phase 3: Frontend i wdrożenie

### Overview

Użytkownik trafia do panelu szkicu, przełożony dostaje swoje akcje, historia i skrzynka pokazują
wynik; wdrożenie na Render i demo na dwóch kontach.

### Changes Required:

#### 1. API i typy

**File**: `frontend/src/api/analysis.ts`, `frontend/src/api/inquiries.ts`,
`frontend/src/api/analysis.test.ts`

**Intent**: Odzwierciedlić nowe pola i endpoint.

**Contract**: `ReplyDraftAction` z `supervisor_approve` i `supervisor_reject`;
`ReplyDraftView.submitted_by: number | null`; `ReplyDraftSnapshot.not_evaluated_rules` opcjonalne
w guardzie (brak → `[]`); `decideAsSupervisor(inquiryId, updatedAt, action, reason)` →
`POST /api/inquiries/{id}/draft/supervisor-decision`; `InquirySummary.draft_status:
ReplyDraftStatus | null` w guardzie.

#### 2. Panel szkicu

**File**: `frontend/src/App.tsx`, `frontend/src/components/Inbox.tsx`,
`frontend/src/components/AnalysisPanel.tsx`, `frontend/src/components/ReplyDraftSection.tsx`

**Intent**: Przełożony decyduje w istniejącym panelu; obie strony widzą wynik i reguły.

**Contract**:
- `Inbox` przekazuje `user` do `AnalysisPanel`, ten do `ReplyDraftSection` (prop `user: User`) i
  dostaje `onSupervisorDecide(updatedAt, action, reason)` obsłużone jak `onDecide` (przeładowanie
  przy `DraftChanged`, 401 → wylogowanie).
- `ReplyDraftSection`: gdy `draft.status === 'awaiting_supervisor'`, `!draft.stale`,
  `user.role === 'supervisor'` i `draft.submitted_by !== user.id` — grupa „Supervisor decision”
  z przyciskami Approve / Reject i `DecisionForm` z wymaganym powodem dla obu; gdy
  `submitted_by === user.id` — tylko Reject przełożonego i tekst „You submitted this draft; another
  supervisor must approve it. You can reject it to start over.”;
  dla handlowca — „Waiting for a supervisor decision.”
- `ACTION`: `supervisor_approve: 'Approved by supervisor'`, `supervisor_reject: 'Rejected by
  supervisor'`; `DecisionHistory` dopisuje „not evaluated: …” obok „failing: …”.
- `AnalysisPanel` raportuje status szkicu po każdej nowej wersji widoku przez opcjonalne
  `onDraftStatus(inquiryId, status | null)`, wzorem `onOutcome`.

#### 3. Skrzynka

**File**: `frontend/src/components/Inbox.tsx`

**Intent**: Przełożony znajduje oczekujące pozycje bez otwierania każdej.

**Contract**: badge „Awaiting supervisor” na pozycji z `draft_status === 'awaiting_supervisor'`
(tekst + kolor); przełącznik „Awaiting supervisor only (N)” (`aria-pressed`) nad listą, dla obu
ról, domyślnie wyłączony; `handleDraftStatus` aktualizuje pozycję listy w miejscu.

#### 4. Testy frontendu

**File**: `frontend/src/components/ReplyDraftSection.test.tsx`,
`frontend/src/components/AnalysisPanel.test.tsx`, `frontend/src/components/Inbox.test.tsx` (nowy)

**Intent**: Przypiąć widoczność akcji per rola i cztery oczy oraz filtr.

**Contract**: supervisor widzi akcje przełożonego tylko dla cudzego, aktualnego szkicu w
`awaiting_supervisor`; salesperson ich nie widzi; własne przekazanie pokazuje komunikat i tylko Reject; reject i
approve przełożonego wymagają powodu; historia pokazuje nowe etykiety i nieocenione reguły;
filtr skrzynki zawęża listę i liczy pozycje; badge po decyzji znika (`onDraftStatus`).

### Success Criteria:

#### Automated Verification:

- Testy przechodzą: `cd frontend && npm test`
- Typy przechodzą: `cd frontend && npm run typecheck`
- Lint przechodzi: `cd frontend && npm run lint`
- Build przechodzi: `cd frontend && npm run build`
- Obraz się buduje: `docker build -t sales-order-orchestrator .`

#### Manual Verification:

- Lokalnie w trybie fake: `sales` Approve Delty → „Awaiting supervisor approval” i badge w skrzynce; `supervisor` filtruje, widzi tabelę reguł, odrzuca z powodem; `sales` widzi „Rejected by supervisor” z powodem i może Regenerate
- Lokalnie: `supervisor` Approve Delty jako handlowiec, potem widzi tylko Reject przełożonego i po nim może Regenerate
- Na Render health pokazuje migrację `0013_supervisor_decisions`, a demo `sales` → `supervisor` kończy Deltę w „Ready to send (sending is simulated)”

**Implementation Note**: Po zielonych bramkach zatrzymaj się na ręczne potwierdzenie.

---

## Testing Strategy

### Unit Tests:

- Serwis: przejścia `awaiting_supervisor → ready_to_send|rejected`, powód przy obu akcjach,
  cztery oczy (w tym `decided_by` NULL), status inny niż oczekiwany, token, nieaktualna
  rekomendacja, brak werdyktu w mocy, snapshot z `not_evaluated_rules`, odczyt starego snapshotu.
- Frontend: widoczność akcji per rola i przekazujący, wymagany powód, etykiety historii, filtr.

### Integration Tests:

- API: 401/403/409/422/200 dla `supervisor-decision`; `draft_status` w liście i szczególe;
  ścieżka handlowca dostępna dla supervisora.

### Manual Testing Steps:

1. `sales`: analiza Delty → Approve → „Awaiting supervisor approval”, badge w skrzynce.
2. `supervisor`: filtr „Awaiting supervisor only”, otwarcie Delty, tabela reguł, Reject bez
   powodu zablokowany, z powodem → „Rejected”.
3. `sales`: historia „Rejected by supervisor” z powodem i regułami; Regenerate → nowy szkic.
4. Ponownie Approve (`sales`) → `supervisor` Approve z powodem → „Ready to send”.
5. `supervisor` sam przekazuje szkic, widzi komunikat o własnym przekazaniu i tylko Reject;
   odrzuca z powodem i robi Regenerate.

## Performance Considerations

Outer join `inquiry_drafts` na liście zapytań (jeden wiersz na zapytanie, unikalny klucz) i indeks
na `inquiry_drafts.status`; skala demo jest pomijalna.

## Migration Notes

Migracja 0013 jest addytywna (CHECK rozszerzony, indeks). Snapshot bez migracji danych — nowe
pole ma wartość domyślną (lessons). Downgrade nie powiedzie się przy istniejących decyzjach
przełożonego — celowo, bez kasowania audytu.

## References

- Related research: `context/changes/supervisor-approval/research.md`
- Wzorzec decyzji: `backend/app/draft/service.py:298-330,742-855`
- Endpoint i mapowanie błędów: `backend/app/api/analysis.py:397-497`
- Poprzednia zmiana: `context/archive/2026-11-12-draft-and-human-decision/plan.md`
- Lessons: `context/foundation/lessons.md`

## Addendum (impl-review)

- `ix_inquiry_drafts_status` (migracja 0013) na razie nie jest używany przez żadne zapytanie —
  filtr „Awaiting supervisor only” działa w przeglądarce na liście z `GET /inquiries`. Indeks
  zostaje jako przygotowanie pod filtr po stronie serwera (bez migracji 0014).
- Faza 3 zmieniła też `frontend/src/components/ChecksSection.tsx`: `ReplyDraftSection` jest
  renderowany w `ChecksSection`, więc `user` i `onSupervisorDecideDraft` przechodzą przez nią.
  `frontend/src/App.tsx` nie wymagał zmian — `Inbox` już dostawał `user`.
- Po przeglądzie: `_submitted_by` sortuje po `id` (kolejność commitów pod blokadą analizy), nie
  po `decided_at` z zegara aplikacji; nieaktualny szkic w `awaiting_supervisor` pokazuje obu rolom
  podpowiedź, że trzeba ponownie uruchomić rekomendację.

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Model i serwis decyzji przełożonego

#### Automated

- [x] 1.1 Wszystkie bramki backendu przechodzą — d562e38
- [x] 1.2 Modele zgadzają się z migracją — d562e38
- [x] 1.3 Testy serwisu i modeli szkicu przechodzą — d562e38

#### Manual

- [x] 1.4 Downgrade do 0012_drafts_decisions (bez decyzji przełożonego w bazie) i ponowny upgrade do head przechodzą lokalnie — d562e38

### Phase 2: API, role i lista zapytań

#### Automated

- [x] 2.1 Wszystkie bramki backendu przechodzą — 02614d0
- [x] 2.2 Testy API szkicu, zapytań i auth przechodzą — 02614d0

#### Manual

- [x] 2.3 Lokalnie w /docs: jako sales Approve Delty → awaiting_supervisor; supervisor-decision jako sales → 403; jako supervisor bez powodu → 422, z powodem → 200 i ready_to_send — 02614d0

### Phase 3: Frontend i wdrożenie

#### Automated

- [x] 3.1 Testy przechodzą — 245f9e0
- [x] 3.2 Typy przechodzą — 245f9e0
- [x] 3.3 Lint przechodzi — 245f9e0
- [x] 3.4 Build przechodzi — 245f9e0
- [x] 3.5 Obraz się buduje — 245f9e0

#### Manual

- [x] 3.6 Lokalnie w trybie fake: sales Approve Delty → Awaiting supervisor i badge; supervisor filtruje, widzi reguły, odrzuca z powodem; sales widzi Rejected by supervisor i może Regenerate — 245f9e0
- [x] 3.7 Lokalnie: supervisor Approve Delty jako handlowiec, potem widzi tylko Reject przełożonego i po nim może Regenerate — 245f9e0
- [x] 3.8 Na Render health pokazuje migrację 0013_supervisor_decisions, a demo sales → supervisor kończy Deltę w Ready to send — 245f9e0
