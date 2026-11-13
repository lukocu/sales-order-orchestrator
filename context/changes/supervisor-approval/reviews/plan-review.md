<!-- PLAN-REVIEW-REPORT -->

# Plan Review: Supervisor approval (S-08)

- **Plan**: context/changes/supervisor-approval/plan.md
- **Mode**: Deep
- **Date**: 2026-11-13
- **Verdict**: SOUND
- **Findings**: 0 critical, 2 warnings, 2 observations

## Verdicts

| Dimension             | Verdict |
| --------------------- | ------- |
| End-State Alignment   | PASS    |
| Lean Execution        | PASS    |
| Architectural Fitness | PASS    |
| Blind Spots           | WARNING |
| Plan Completeness     | WARNING |

## Grounding

Grounding: 18/18 paths ✓, 12/12 symbols ✓, brief↔plan ✓

## Findings

### F1 — Własne przekazanie jedynego przełożonego to nowy ślepy zaułek

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 1 — supervisor_decide (OwnSubmission); Phase 3 — 3.7
- **Detail**: Demo ma jedno konto `supervisor`. Gdy zatwierdzi ono jako handlowiec, szkic utyka w `awaiting_supervisor`: OwnSubmission blokuje approve i reject, Regenerate odmawia dla DECIDED (`service.py:89,232-237`), withdraw jest poza zakresem. Jedyne wyjście to nowa rekomendacja (płatne wywołanie LLM).
- **Fix A ⭐ Recommended**: Cztery oczy tylko dla approve; reject własnego przekazania dozwolony
  - Strength: Obejście polityki dotyczy tylko approve; reject = wycofanie + Regenerate, bez nowego pojęcia.
  - Tradeoff: Historia pokaże „Rejected by supervisor” od osoby, która przekazała.
  - Confidence: HIGH — `rejected` nie jest w DECIDED.
  - Blind spot: None significant.
- **Fix B**: 409 dla obu; komunikat wskazuje wyjście (ponowna rekomendacja)
  - Strength: Symetryczne cztery oczy.
  - Tradeoff: Wyjście kosztuje wywołanie LLM.
  - Confidence: MED — zależy od dostępności ponownej analizy z panelu.
  - Blind spot: Nie sprawdzono ponownej rekomendacji bez pełnej analizy.
- **Decision**: FIXED (Fix A)

### F2 — Wybór wyjątku statusu w `_locked_draft` niedookreślony

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 1 — #3 Serwis decyzji
- **Detail**: Kontrakt parametryzuje `status`, ale nie mówi, jak funkcja wybiera DraftNotEditable vs NotAwaitingSupervisor; DraftChanged jest sprawdzany przed statusem (`service.py:755-758`).
- **Fix**: `status="awaiting_supervisor"` → NotAwaitingSupervisor, inaczej DraftNotEditable; DraftChanged ma pierwszeństwo.
- **Decision**: FIXED

### F3 — Zmiana kształtu wierszy w list_inquiries/read_inquiry

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 2 — #3 Status szkicu na liście
- **Detail**: Oba endpointy rozpakowują `(inquiry, outcome)` do `_with_outcome` (`inquiries.py:34-49`); trzecia kolumna zmienia krotkę i helper.
- **Fix**: `select(Inquiry, current_outcome(), InquiryDraft.status)` + outerjoin po `with_current_outcome`; `_with_outcome` przyjmuje `draft_status`.
- **Decision**: FIXED

### F4 — Skrzynka nie odświeża się po przekazaniu przez innego użytkownika

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 3 — #3 Skrzynka
- **Detail**: Inbox ładuje listę raz (`Inbox.tsx:47-60`); badge i licznik dla cudzego przekazania pojawią się po przeładowaniu.
- **Fix**: Dopisać do Out of scope / Open Risks: lista bez odświeżania na żywo.
- **Decision**: FIXED
