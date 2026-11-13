# Supervisor approval (S-08) — Plan Brief

> Full plan: `context/changes/supervisor-approval/plan.md`
> Research: `context/changes/supervisor-approval/research.md`

## What & Why

Przełożony zatwierdza albo odrzuca rekomendację, której polityka nie przepuściła, a obie strony
widzą, która reguła nie przeszła; każda decyzja zapisuje kto, kiedy i dlaczego (FR-009, US-02).
Dziś szkic przekazany przez handlowca utyka w `awaiting_supervisor` bez wyjścia.

## Starting Point

S-07 ustawia `awaiting_supervisor` po Approve handlowca przy werdykcie `requires_supervisor`, ale
żadna ścieżka z niego nie wychodzi. Role (`salesperson`, `supervisor`) i konta demo istnieją, lecz
żaden endpoint ich nie sprawdza; lista zapytań nie zna statusu szkicu.

## Desired End State

Przełożony filtruje skrzynkę do „Awaiting supervisor”, otwiera zapytanie, widzi tabelę reguł i
zatwierdza (→ Ready to send) lub odrzuca (→ Rejected) z obowiązkowym powodem. Handlowiec widzi
„Approved/Rejected by supervisor” w historii z powodem i regułami, a po odrzuceniu może
Regenerate. Handlowiec dostaje 403 na endpoincie przełożonego; nikt nie zatwierdza własnego
przekazania (może je odrzucić, żeby zacząć od nowa).

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Przedmiot kolejki | Tylko `awaiting_supervisor` | Zgodne z US-02 („When handlowiec chce ją zatwierdzić”) i S-07, bez nowego wejścia w stan. | Plan |
| Widok kolejki | Filtr i badge w skrzynce, decyzja w panelu szkicu | Reużywa panel z tabelą reguł i historią; jedna lista dla obu ról. | Plan |
| Zapis decyzji | Nowe akcje `supervisor_approve` / `supervisor_reject` + migracja CHECK | Historia jednoznaczna i niezależna od późniejszej zmiany roli. | Plan |
| Powód | Wymagany przy approve i reject przełożonego | Zatwierdzenie to obejście polityki — „dlaczego” ma tu największą wartość audytową. | Plan |
| Role | 403 tylko na decyzji przełożonego; ścieżka handlowca dla obu ról | PRD: przełożony może wszystko, co handlowiec. | Research / Plan |
| Cztery oczy | 409 na approve, gdy zatwierdzający przekazał szkic; reject własnego dozwolony | Obejście polityki jest tylko w approve; reject własnego to wyjście z oczekiwania przy jednym koncie przełożonego. | Plan / review F1 |
| Zmiana danych w trakcie | Werdykt w mocy w chwili decyzji; nowa rekomendacja jak dziś usuwa szkic | Reużywa `_policy_in_force` i `_drop_outdated`, zero nowych blokad. | Plan |
| Odrzucenie | Jak Reject handlowca — Regenerate dozwolone | Nowy szkic i tak wraca do przełożonego, więc nie da się obejść polityki. | Plan |
| Snapshot reguł | Nowe pole `not_evaluated_rules` z wartością domyślną; `failing_rules` bez zmian | Reguły `not_evaluated` też kierują do przełożonego; pole domyślne nie wymaga migracji danych (lessons). | Research / Plan |
| Follow-up S-02 | Poza zakresem | Wycinek zostaje pionowy, hardening osobno. | Plan |

## Scope

**In scope:**
- Migracja 0013 (CHECK akcji, indeks statusu szkicu), `supervisor_decide`, `submitted_by` w widoku
- `require_supervisor` (403) i `POST /inquiries/{id}/draft/supervisor-decision`
- `draft_status` w `GET /inquiries` i szczególe; badge i filtr w skrzynce
- Akcje przełożonego, komunikaty i etykiety historii w panelu szkicu; wdrożenie na Render

**Out of scope:**
- Nieprzekazane werdykty `requires_supervisor` w kolejce, osobny widok kolejki, powiadomienia
- Blokada ponownej analizy w trakcie oczekiwania, zamrożony werdykt, ostateczne odrzucenie
- Wycofanie przekazania przez handlowca
- Limit wywołań LLM i osobne hasła kont demo

## Architecture / Approach

Decyzja przełożonego powtarza wzorzec S-07: lock analizy → token `updated_at` + wymagany status
(`awaiting_supervisor`) + aktualna rekomendacja → cztery oczy (`decided_by` ostatniej decyzji
szkicu) → werdykt w mocy → jeden commit ze statusem i wpisem historii. Granica ról jest w
zależności FastAPI przed serwisem. Frontend przekazuje `user` z `Inbox` przez `AnalysisPanel` do
`ReplyDraftSection`, a panel raportuje status szkicu do listy, wzorem `onOutcome`.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Model i serwis decyzji przełożonego | Migracja 0013, nowe akcje, `supervisor_decide`, `submitted_by`, testy serwisu | Parametryzacja `_locked_draft` nie może zmienić zachowania ścieżki handlowca |
| 2. API, role i lista zapytań | 403, endpoint z mapowaniem 409/422, `draft_status` na liście | Join na liście zapytań nie może zduplikować wierszy |
| 3. Frontend i wdrożenie | Akcje przełożonego, historia, badge i filtr, demo na Render | Przeprowadzenie `user` przez trzy komponenty bez regresji testów panelu |

**Prerequisites:** S-07 zarchiwizowane (08ad2b5); konta demo `sales` i `supervisor` z hasłem na Render.
**Estimated effort:** ~3 sesje, po jednej na fazę.

## Open Risks & Assumptions

- Nowa rekomendacja nadal usuwa oczekujący szkic bez powiadomienia — świadomie zaakceptowane.
- Przełożony może zobaczyć inny werdykt niż handlowiec przy przekazaniu (zmiana progów dla
  edytowanej oferty); snapshot decyzji zapisuje werdykt z chwili decyzji przełożonego.
- Downgrade 0013 nie przejdzie przy istniejących decyzjach przełożonego — celowo.
- Skrzynka bez odświeżania na żywo — szkic przekazany w innej sesji widać po przeładowaniu.

## Success Criteria (Summary)

- Delta przechodzi sales Approve → supervisor Approve/Reject z powodem na Render.
- Handlowiec dostaje 403 na decyzji przełożonego; zatwierdzenie własnego przekazania jest zablokowane (409), odrzucenie dozwolone.
- Historia pokazuje przełożonego, czas, powód i reguły, które nie przeszły lub nie zostały ocenione.
