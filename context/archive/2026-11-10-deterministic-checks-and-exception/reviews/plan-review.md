<!-- PLAN-REVIEW-REPORT -->

# Plan Review: S-03 deterministic-checks-and-exception

- **Plan**: context/changes/deterministic-checks-and-exception/plan.md
- **Mode**: Deep
- **Date**: 2026-11-10
- **Verdict**: REVISE → SOUND (after triage)
- **Findings**: 1 critical, 2 warnings, 1 observation

## Verdicts

| Dimension             | Verdict |
| --------------------- | ------- |
| End-State Alignment   | FAIL    |
| Lean Execution        | PASS    |
| Architectural Fitness | WARNING |
| Blind Spots           | PASS    |
| Plan Completeness     | WARNING |

## Grounding

Grounding: 8/8 paths ✓, 6/6 symbols ✓, brief↔plan ✓ (ryzykowne założenia sprawdzone bezpośrednio: `main.py:13-16`, `conftest.py:100-118`, `fake.py:83-91`, `AnalysisPanel.tsx:514`)

## Findings

### F1 — Wspólny run psuje dowód „0 tokenów” na Groq

- **Severity**: ❌ CRITICAL
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: End-State Alignment
- **Location**: Critical Implementation Details; Faza 2 §1–2; Faza 3 §2; kryterium 3.8
- **Detail**: Sprawdzenia biegną w runie analizy, a baner standardu pokazuje metryki tego runu jako „0 tokenów”. Na Groq `parse` to krok `llm`, więc run ma tokeny > 0; Metrics S-02 (`AnalysisPanel.tsx:514`) pokazywałby kroki sprawdzeń drugi raz; po korekcie sprawdzenia mają osobny run — model niespójny.
- **Fix A ⭐ Recommended**: Sprawdzenia zawsze we własnym runie (po analizie, po korekcie, w POST /checks)
  - Strength: Jedna ścieżka; run sprawdzeń czysto deterministyczny; analiza bez zmian względem S-02.
  - Tradeoff: Analiza tworzy dwa runy.
  - Confidence: HIGH — ścieżka korekt w planie już tak działa.
  - Blind spot: Zmienia sformułowanie „ten sam przebieg” z wywiadu.
- **Fix B**: Ten sam run, metryki sprawdzeń filtrowane do kroków sprawdzeń
  - Strength: Jeden run na analizę.
  - Tradeoff: Filtrowanie po nazwach kroków; dwie różne sumy jednego runu.
  - Confidence: MEDIUM — kruche przy krokach S-04.
  - Blind spot: Sumy RunSummary sprzeczne z banerem.
- **Decision**: FIXED (Fix A): sprawdzenia zawsze we własnym runie — Key Discoveries, Critical Implementation Details, Faza 2 §1–2 i testy, brief

### F2 — InquiryDetail dziedziczy outcome bez źródła

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Faza 2 §4
- **Detail**: `read_inquiry` buduje szczegół przez `model_validate(inquiry, from_attributes=True)` (`inquiries.py:51-56`); bez domyślnej wartości 500, z domyślną cichy `null`.
- **Fix**: `outcome` z domyślnym `None`; szczegół wypełnia je tym samym helperem co lista.
- **Decision**: FIXED: outcome z domyślnym None, read_inquiry używa helpera listy — Faza 2 §4

### F3 — Cena, rabat i kredyt bez dopasowanego klienta

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Implementation Approach — Reguły
- **Detail**: Cena standardowa i kredyt zależą od klienta; plan nie mówi, co przy `not_found`/`ambiguous`.
- **Fix**: Bez dopasowanego klienta cena, rabat i kredyt są `skipped`; stan liczony nadal.
- **Decision**: FIXED: reguła skipped bez klienta/produktu/ilości — Reguły

### F4 — Wynik zapisany dwa razy (kolumny + JSONB)

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Architectural Fitness
- **Location**: Faza 1 §1 i §3
- **Detail**: `outcome` i `exception_type` są i kolumnami, i polami `CheckResults` — dwa źródła prawdy.
- **Fix**: `outcome` i `exception_type` tylko w kolumnach; `CheckResults` trzyma wyniki sprawdzeń i `reasons`.
- **Decision**: FIXED: outcome i exception_type tylko w kolumnach — Faza 1 §3–4
