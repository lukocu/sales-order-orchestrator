---
date: 2026-11-12T23:00:00+01:00
researcher: Claude (Opus 5.5) dla lukocu
git_commit: 08ad2b5
branch: main
repository: lukocu/sales-order-orchestrator
topic: "S-08 supervisor-approval — na czym budować akceptację przełożonego"
tags: [research, auth, roles, draft, policy, decisions, frontend, s-08]
status: complete
last_updated: 2026-11-12
last_updated_by: Claude (Opus 5.5)
---

# Research: S-08 supervisor-approval

**Date**: 2026-11-12
**Researcher**: Claude (Opus 5.5) dla lukocu
**Git Commit**: 08ad2b5
**Branch**: main
**Repository**: lukocu/sales-order-orchestrator

## Research Question

Co w obecnym kodzie (po S-07 `draft-and-human-decision`) jest gotowe do zbudowania S-08: przełożony
widzi rekomendacje odrzucone przez politykę wraz z regułą, która nie przeszła, zatwierdza je lub
odrzuca; handlowiec widzi wynik, a decyzja zapisuje kto, kiedy i dlaczego (FR-009, US-02,
roadmap S-08). Gdzie są luki i jakie decyzje zostają dla `/10x-plan`.

## Summary

- **Stan „czeka na przełożonego” już istnieje, ale jest ślepym zaułkiem.** Approve handlowca przy
  werdykcie w mocy innym niż `no_approval_needed` ustawia szkic na `awaiting_supervisor` i dopisuje
  decyzję `approve` (`backend/app/draft/service.py:324-330`). Żadna ścieżka nie wychodzi z tego
  statusu: `_locked_draft` wymaga `status == "draft"` (`service.py:757-758`, `DraftNotEditable` → 409),
  a regenerate jest blokowany przez `DECIDED` (`service.py:89`, 409 `DraftDecided`). S-07 jawnie
  oddał przejścia AWAITING SUPERVISOR → READY TO SEND / REJECTED do S-08
  (`context/archive/2026-11-12-draft-and-human-decision/plan.md:73-74`).
- **Role są w danych, ale nikt ich nie sprawdza.** `Role = Literal["salesperson", "supervisor"]`
  (`backend/app/auth/models.py:7`), kolumna `users.role` z CHECK (`auth/models.py:21,27`), konto
  demo `supervisor` / „Piotr Wiśniewski” (`backend/migrations/versions/0003_users_inquiries.py:24-39`).
  `AuthUser.role` jest kopiowane w `auth/deps.py:32`; w `backend/app` nie ma żadnego innego użycia
  `.role` ani zależności typu `require_role` — wszystkie endpointy chronione przyjmują dowolnego
  zalogowanego (`backend/app/main.py:13-21`). S-01 i S-02 odłożyły egzekwowanie ról i 403 do S-08
  (`context/archive/2026-11-09-login-and-inbox/plan.md:37-38`, `.../plan-brief.md:30,44`).
- **„Kto” jest zapisywany jako user id, bez roli.** `inquiry_draft_decisions.decided_by` to FK do
  `users.id` z `ON DELETE SET NULL` (`backend/app/draft/models.py:66`); widok zwraca tylko
  `decided_by_name` (`service.py:148-155`, `_user_name` `:859-862`). Akcje to wyłącznie
  `edit|approve|reject` (`draft/schema.py:90`, CHECK `draft/models.py:50-53`, migracja
  `0012_drafts_decisions.py:61`).
- **Kolejka przełożonego da się wyprowadzić z istniejących danych** (`inquiry_drafts.status =
  'awaiting_supervisor'`), ale nie ma do niej endpointu ani UI. `GET /inquiries`
  (`backend/app/api/inquiries.py:40-52`) zwraca tylko outcome sprawdzeń
  (`standard|exception|needs_input`), bez statusu szkicu i bez filtrów; tabela `inquiries` nie ma
  pola cyklu życia (`backend/app/inquiries/models.py:7-17`).
- **Frontend nie zna roli poza nagłówkiem.** `user` trafia tylko do `Inbox`
  (`frontend/src/App.tsx:57-58`), rola jest wyświetlana w `Inbox.tsx:118-120`; `AnalysisPanel` i
  `ReplyDraftSection` jej nie dostają. Po Approve z `requires_supervisor` UI pokazuje „Status:
  Awaiting supervisor approval” i chowa przyciski (`ReplyDraftSection.tsx:53,150,231-235`).
- **„Która reguła nie przeszła” jest częściowo w danych.** `DecisionSnapshot.failing_rules` zawiera
  tylko kody reguł z werdyktem `fail` (`service.py:838`); reguły `not_evaluated` też dają
  `requires_supervisor` (`backend/app/policy/rules.py:229-233`), ale nie trafiają do snapshotu. Pełna
  tabela reguł (actual, threshold, reason) jest w `DraftView.policy` — werdykcie w mocy, liczonym na
  odczycie (`service.py:364-367`).

## Detailed Findings

### Uwierzytelnianie i role

- Model `User` (`users`): `id`, `username` (unique), `display_name`, `role` VARCHAR(20) z CHECK
  `ck_users_role`, `password_hash` (NULL = brak logowania), `created_at`
  (`backend/app/auth/models.py:17-30`). Sesje `user_sessions` z hashem SHA-256 tokenu
  (`auth/models.py:33-42`, `auth/sessions.py:12-13`, TTL 7 dni).
- Konta demo `sales` (salesperson) i `supervisor` (supervisor) seedowane w migracji 0003
  (`0003_users_inquiries.py:24-39`); hasła ustawia `sync_demo_passwords` z env `DEMO_PASSWORD` przy
  każdym starcie (`backend/app/auth/demo_accounts.py:27,30-53`, `backend/start.sh`).
- Endpointy: `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`
  (`backend/app/api/auth.py:51-128`). Zależność `get_current_user` → 401 bez sesji
  (`auth/deps.py:40-56`); `protected_router` owija runs, inquiries i analysis (`main.py:13-21`).
- Testy: fabryka użytkownika przyjmuje `role=` z domyślnym `salesperson`
  (`backend/tests/conftest.py:47,137-141`); żaden test nie loguje się jako supervisor ani nie
  sprawdza 403.
- PRD Access Control: każdy użytkownik ma jedną rolę; przełożony może wszystko, co handlowiec, plus
  zatwierdzać i odrzucać wyjątki skierowane przez politykę (`context/foundation/prd.md:125-130`).

### Polityka

- `PolicyOutcome = no_approval_needed|requires_supervisor` (`backend/app/policy/schema.py:76`);
  `no_approval_needed` tylko gdy wszystkie reguły mają `pass`, każdy `fail` lub `not_evaluated` daje
  `requires_supervisor` (`policy/rules.py:229-233`).
- `RuleResult(code, verdict, actual, threshold, unit, reason)` i `PolicyResult` z `extra="forbid"`
  (`policy/schema.py:82-107`) — objęte regułą lessons o migracji JSONB.
- Werdykt etapu: `inquiry_policy_verdicts`, jeden wiersz na zapytanie, przypięty do
  `recommended_at` (`policy/models.py:35-61`); progi w `policy_rules` (`policy/models.py:15-32`,
  `load_thresholds` `policy/service.py:195-209`).

### Szkic i decyzje (S-07)

- `DraftStatus = draft|ready_to_send|awaiting_supervisor|rejected`, `DecisionAction =
  edit|approve|reject` (`draft/schema.py:89-90`), CHECK-i w `draft/models.py:12,26,50-53` i migracji
  `0012_drafts_decisions.py:20,38,61`. Najnowsza migracja to 0012.
- `decide` (`service.py:298-330`): powód wymagany dla reject, opcjonalny dla approve (`:316`);
  `_locked_draft` (`:742-778`) bierze `lock_analysis`, sprawdza `updated_at` (`DraftChanged`), status
  `draft` (`DraftNotEditable`) i aktualność rekomendacji (`DraftStale`); `_policy_in_force`
  (`:796-819`) — dla edytowanej oferty ponowna ocena aktualnymi progami (`_edited_offer_policy`
  `:781-793`), dla nieedytowanej werdykt etapu z tym samym `recommended_at`.
- `_decide` (`:822-855`) w jednym commicie ustawia status i `updated_at` oraz dopisuje wiersz
  decyzji ze snapshotem (`offer`, `policy_outcome`, `failing_rules` = kody `fail`).
- Endpointy: `POST /inquiries/{id}/draft` (regenerate), `PUT /inquiries/{id}/draft` (edit),
  `POST /inquiries/{id}/draft/decision` z `{updated_at, action: approve|reject, reason}`
  (`backend/app/api/analysis.py:358-497`); wszystkie zwracają pełny `AnalysisView`. Mapowanie błędów
  409/422/500 w `analysis.py:405-432`.
- Cykl życia szkicu w stanie `awaiting_supervisor`:
  - ponowne uruchomienie polityki nie zmienia statusu szkicu tej samej rekomendacji
    (`draft_after_policy`, `service.py:195-211`), nawet jeśli nowy werdykt to `no_approval_needed`;
  - nowa rekomendacja usuwa szkic niezależnie od statusu (`_drop_outdated` `service.py:694-720`,
    `_store` blokuje tylko ten sam `recommended_at` `:684-689`) — oczekująca pozycja może zniknąć,
    decyzje zostają w historii z `current=false` (`get_decision_views` `:396-439`);
  - werdykt edytowanej oferty jest liczony na odczycie, więc zmiana progów może zmienić to, co
    zobaczy przełożony, względem tego, co zatwierdzał handlowiec.

### Skrzynka i frontend

- `GET /inquiries` → `InquirySummary` z `outcome` sprawdzeń (`api/inquiries.py:40-52`,
  `checks/service.py:188-206`); frontend `frontend/src/api/inquiries.ts:5-12`, badge w
  `Inbox.tsx:29-33,163-165`. Brak indeksu na `inquiry_drafts.status`.
- `ReplyDraftSection.tsx`: etykiety statusów `:50-55`, etykiety werdyktu `:63-66`, `VerdictInForce`
  z tabelą reguł `:289-330`, przyciski decyzji `:186-198`, `DecisionForm` `:362-403`,
  `DecisionHistory` `:574-630` (By, When, Reason, Offer, Policy „(failing: …)”).
- `decideDraft` w `frontend/src/api/analysis.ts:1188-1203`; `App.tsx` trzyma stan auth bez
  kontekstu ani routera (`App.tsx:7-11,18-37`).

## Code References

- `backend/app/draft/service.py:89` — `DECIDED` (`ready_to_send`, `awaiting_supervisor`) blokuje regenerate
- `backend/app/draft/service.py:298-330` — `decide`, jedyne wejście w `awaiting_supervisor`
- `backend/app/draft/service.py:742-778` — `_locked_draft`, wymaga statusu `draft`
- `backend/app/draft/service.py:796-819` — `_policy_in_force`
- `backend/app/draft/service.py:822-855` — `_decide`, zapis decyzji i snapshotu
- `backend/app/draft/models.py:42-68` — `inquiry_draft_decisions`, `decided_by` FK users
- `backend/app/draft/schema.py:89-90,154-161` — statusy, akcje, `DecisionSnapshot`
- `backend/app/auth/models.py:7,17-30` — `Role`, `User`
- `backend/app/auth/deps.py:22-56` — `AuthUser`, `get_current_user`
- `backend/app/main.py:13-21` — `protected_router`
- `backend/app/api/analysis.py:397-497` — endpointy edit/decision i mapowanie błędów
- `backend/app/api/inquiries.py:40-52` — lista zapytań
- `backend/app/policy/rules.py:229-233` — `outcome`
- `backend/migrations/versions/0012_drafts_decisions.py:20,38,61` — CHECK-i statusów i akcji
- `frontend/src/components/ReplyDraftSection.tsx:50-66,150,186-198,574-630` — statusy, przyciski, historia
- `frontend/src/components/Inbox.tsx:118-120,163-165` — rola i badge w skrzynce
- `frontend/src/App.tsx:57-58` — `user` przekazywany tylko do `Inbox`

## Architecture Insights

- Zapis decyzji to wzorzec „lock → walidacja tokenu i statusu → werdykt w mocy → jeden commit z
  dopisaniem historii” (`_locked_draft` + `_decide`). Decyzja przełożonego może go powtórzyć z innym
  warunkiem statusu (`awaiting_supervisor` zamiast `draft`).
- Historia decyzji jest append-only i przeżywa szkic; `current` odróżnia decyzje aktualnej wersji.
- Endpointy decyzji zwracają pełny `AnalysisView`, a frontend podmienia stan panelu odpowiedzią.
- Każda zmiana modelu pydantic czytanego z JSONB (`DecisionSnapshot`, `PolicyResult`, literały)
  wymaga migracji danych albo pola opcjonalnego z domyślną wartością
  (`context/foundation/lessons.md:5-10`); nowe wartości `DecisionAction`/`DraftStatus` wymagają
  migracji CHECK-ów.

## Historical Context (from prior changes)

- `context/archive/2026-11-09-login-and-inbox/plan-brief.md:30,44`, `plan.md:37-38` — role
  zapisane i wyświetlane, egzekwowanie i 403 odłożone do S-08 (wspierane przez kod: brak użycia roli).
- `context/archive/2026-11-10-parse-inquiry/plan.md:40` — każdy zalogowany może uruchomić analizę;
  role w S-08. `reviews/impl-review.md:56-67` (F3) — brak limitu płatnych wywołań LLM i wspólne
  hasło kont demo, rekomendowane jako follow-up dla S-08 lub hardeningu; ostateczna decyzja w tym
  pliku nie jest jednoznaczna.
- `context/archive/2026-11-11-policy-verdict/plan.md:66`, `plan-brief.md:47` — kolejka przełożonego,
  approve/reject i zapis kto/kiedy/dlaczego poza zakresem S-06, do S-08.
- `context/archive/2026-11-12-draft-and-human-decision/plan.md:73-74,98-101` — Approve bez osobnej
  akcji „poproś o akceptację”; `awaiting_supervisor` przejmie S-08; każdy zalogowany może podjąć
  decyzję handlowca (wspierane: `decide` nie sprawdza roli). `research.md:285-286` — otwarte pytanie
  8 (czy decyzję handlowca może podjąć przełożony) pozostawione dla S-08.
- `context/archive/2026-11-12-draft-and-human-decision/reviews/plan-review.md:27-44` — reguła rabatu
  przy edycji zawodzi, gdy za wysoki jest rabat żądany lub oferowany, więc Delta zawsze idzie do
  przełożonego; ślepy punkt: nie potwierdzono, że biznes tego chce.

## Related Research

- `context/archive/2026-11-12-draft-and-human-decision/research.md`
- `context/archive/2026-11-11-policy-verdict/research.md`
- `context/archive/2026-11-09-login-and-inbox/research.md`

## Open Questions

Decyzje produktowe i projektowe dla `/10x-plan` (żadna nie jest rozstrzygnięta w dokumentach):

1. **Przedmiot kolejki.** Czy przełożony pracuje tylko na szkicach w `awaiting_supervisor` (po
   Approve handlowca, zgodnie z S-07 i US-02 „When handlowiec chce ją zatwierdzić”), czy widzi też
   werdykty `requires_supervisor`, których nikt jeszcze nie przekazał (dosłowne brzmienie roadmapy:
   „rekomendacje odrzucone przez politykę”)?
2. **Widok kolejki.** Osobna lista/filtr dla przełożonego (nowe pole statusu szkicu w
   `InquirySummary` albo osobny endpoint) czy praca w istniejącym panelu analizy z badge'em w skrzynce.
3. **Zapis decyzji przełożonego.** Nowe akcje (np. `supervisor_approve`/`supervisor_reject`) z
   migracją CHECK, czy istniejące `approve`/`reject` z rolą wywnioskowaną z `decided_by` (rola nie
   jest dziś zapisywana w decyzji; zmiana roli użytkownika zmieniłaby interpretację historii).
4. **Powód.** Czy „dlaczego” przełożonego jest wymagane przy approve i reject (S-07: wymagane tylko
   przy reject i edit).
5. **Egzekwowanie ról.** Zakres 403: tylko nowy endpoint przełożonego, czy też ograniczenie ścieżki
   handlowca (PRD: przełożony może wszystko, co handlowiec). Czy przełożony może zatwierdzić wyjątek,
   który sam przekazał jako handlowiec?
6. **Zmiana danych w trakcie oczekiwania.** Co z `awaiting_supervisor`, gdy werdykt etapu się zmieni
   (dziś status zostaje) albo gdy przyjdzie nowa rekomendacja (dziś szkic znika). Czy decyzja
   przełożonego ma używać werdyktu w mocy w chwili decyzji (jak `decide`) i blokować przy braku/stale?
7. **Wyjście po odrzuceniu przez przełożonego.** Czy `rejected` od przełożonego jest końcowe, czy
   handlowiec może Regenerate/edytować jak po własnym Reject.
8. **Snapshot reguł.** Czy `failing_rules` ma obejmować `not_evaluated` (też kierują do przełożonego);
   zmiana znaczenia pola JSONB podlega regule lessons.
9. **Zakres poboczny.** Czy follow-up z S-02 (limit płatnych wywołań LLM, wspólne hasło demo) wchodzi
   w S-08 — dokumenty sugerują, ale nie przesądzają.
