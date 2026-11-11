# Werdykt polityki — Plan Brief

> Full plan: `context/changes/policy-verdict/plan.md`
> Research: `context/changes/policy-verdict/research.md`

## What & Why

Handlowiec ma zobaczyć, czy rekomendowana opcja mieści się w polityce firmy: werdykt każdej reguły
(marża, rabat, wartość zamówienia, kredyt) i wynik łączny „bez akceptacji” albo „wymaga przełożonego”
(FR-008, US-01, US-02). Progi są konfiguracją jawnie oznaczoną jako przykładowa, bo nie pochodzą
z prawdziwej firmy. Ten etap odblokowuje S-07 (szkic i decyzja), S-08 (przełożony) i S-10 (ewaluacja).

## Starting Point

S-05 zapisuje rekomendację z wybraną opcją (wartość, koszt, marża), a S-03 trzyma rabat żądany przez
klienta i dane kredytowe w checks. Rabat i kredyt S-03 są tylko informacyjne — ich ocenę jawnie odłożono
do S-06. Nie ma miejsca na progi ani żadnego etapu po rekomendacji.

## Desired End State

Po każdej rekomendacji z wyborem powstaje werdykt polityki widoczny w sekcji „Policy” z etykietą
„Example thresholds”. Na seedzie ACME i Omega przechodzą bez akceptacji, Delta wymaga przełożonego
(prosi o 25% rabatu przy maksimum 15%). Werdykt można ponownie przeliczyć przyciskiem.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Miejsce progów | Tabela `policy_rules` zasiana migracją 0011, `is_example` | Zgodne z „seeded example policy thresholds”, trafia na Render przez migrację | Plan |
| Reguła rabatu | Rabat żądany przez klienta ≤ maks. rabat | Ceny opcji mają zawsze rabat standardowy, więc tylko prośba klienta jest wyjątkiem | Research + Plan |
| Reguła kredytu | Saldo + wartość wybranej opcji ≤ limit; `blocked` = fail | Ocenia to, co faktycznie zostanie zamówione; działa dla edycji w S-07 | Research + Plan |
| Reguła wartości | Wartość opcji ≤ próg PLN | Ta sama podstawa co kredyt i marża | Plan |
| Braki danych | `not_evaluated` z powodem; każdy fail lub not_evaluated → wymaga przełożonego | Brak danych nigdy nie przepuszcza oferty bez człowieka | Plan |
| Progi przykładowe | Marża ≥ 20%, rabat ≤ 15%, wartość ≤ 30 000 PLN | Czysty podział demo: dwa „bez akceptacji”, jeden „wymaga przełożonego” | Plan |
| Brak wybranej opcji | Brak werdyktu; re-run → 409 | Spójne z S-05 („Nothing to recommend”) | Plan |
| Przechowywanie | Osobna tabela z FK CASCADE do rekomendacji i pinem `recommended_at` | Nie rusza JSONB S-03/S-05 (lekcja), kaskada obsługuje usuwanie | Research + Plan |

## Scope

**In scope:**
- Tabele `policy_rules` (seed) i `inquiry_policy_verdicts`, migracja 0011
- Czyste reguły + wynik łączny, krok tracingu `rules` (deterministyczny)
- Auto-uruchomienie po rekomendacji, `POST /api/inquiries/{id}/policy`, `AnalysisView.policy`
- Sekcja „Policy” w UI z etykietą „Example thresholds”, README

**Out of scope:**
- Akceptacja przełożonego, role, audyt decyzji (S-08)
- Szkic i edycja ceny/ilości (S-07) — tylko rdzeń jest na to gotowy
- Edycja progów w UI; przecena opcji o rabat żądany; wybór rekomendera „pod politykę”

## Architecture / Approach

`policy/rules.py` (czyste funkcje: `PolicyInputs` + `PolicyThresholds` → `PolicyResult`) +
`policy/service.py` (odczyt rekomendacji, checks i progów; zapis pod `lock_analysis` z pinem).
Hook `policy_after_recommendation` na końcu `recommend_after_orchestration` i ręcznego re-runu
rekomendacji; usunięcie rekomendacji kaskaduje werdykt, rekomendacja `failed` go usuwa.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Model danych i rdzeń reguł | Migracja 0011 z seedem progów, typy, 4 reguły z testami na seedzie | Semantyka granic i braków danych |
| 2. Serwis, pipeline i API | Werdykt po każdej rekomendacji, widok ze `stale`, `POST /policy` | Kolejność hooka i wyścigi z nowszym runem |
| 3. Frontend i wdrożenie | Sekcja Policy, guard, deploy i weryfikacja na Render | Delta na Render wymaga najpierw re-run orkiestracji |

**Prerequisites:** S-05 zarchiwizowane (done); seed z S-03/S-04/S-05.
**Estimated effort:** ~2–3 sesje w 3 fazach.

## Open Risks & Assumptions

- Omega jest 2 064 PLN pod progiem wartości — zmiana seedu może przestawić jej wynik.
- Wynik reguł marży/wartości dla Delty zależy od opcji wybranej przez rekomender (fake: combined 14.29% / 31 500 PLN; Groq może wybrać inną) — rabat oblewa Deltę zawsze.
- Zmiana progu nie oznacza werdyktu jako nieaktualnego; trzeba go przeliczyć ręcznie.

## Success Criteria (Summary)

- Handlowiec widzi werdykt czterech reguł i wynik łączny dla każdej rekomendacji z wyborem.
- ACME/Omega: „No approval needed”; Delta: „Requires supervisor approval”, z widocznym powodem.
- Progi są widocznie oznaczone jako przykładowe i zmienialne bez zmiany kodu.
