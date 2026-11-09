# Opportunity Map

## Context

- **Project / context**: Intelligent Sales Order Orchestration System — hybrydowy system (workflow + orchestrator agentów AI) do obsługi zapytań ofertowych w MŚP handlowych i produkcyjnych.
- **Data constraint**: mock / symulowane (ERP, CRM, magazyn, cennik); prawdziwe maile i cenniki dopiero po uzgodnieniu dostępu i anonimizacji.
- **Date**: 2026-11-09
- **Project goal (decyzja autora, 2026-11-09)**: projekt jest też portfolio pod rolę AI Engineer. Orchestrator, rejestr kompetencji, policy engine i observability zostają w zakresie jako cel pokazu technicznego, a nie tylko środek do rozwiązania bólu klienta. Karta zapytania (Quote Context Card) to pierwszy, zakotwiczony w domenie wycinek, a orchestrator buduje się na niej i mierzy względem prostszej bazy (stały workflow).
- **Evidence status**: hipoteza bez dowodów — brak danych o częstotliwości zapytań, odsetku wyjątków i czasie przygotowania oferty. Opis w większości dotyczy rozwiązania, nie obserwowanego bólu.

## Map

| Signal | Existing / default response | Thin complement | First useful version | Data risk | Direction if valuable |
| ------ | --------------------------- | --------------- | -------------------- | --------- | --------------------- |
| Ręczne zbieranie kontekstu z 5+ systemów przy każdym zapytaniu | Moduły ofertowania ERP/CRM, CPQ | Jedna karta zapytania obok maila | Raport read-only na danych mock | mock / local | Product lub Feature |
| Powtarzalne obliczenia: cena, rabat, marża, termin | Cenniki i reguły rabatowe w ERP | Deterministyczny kalkulator + flagi polityki | Kalkulator na CSV | mock / local | Feature |
| Wyjątki: brak ilości, zamienniki, cena vs termin | Doświadczenie handlowca, ATP w ERP | 2–3 warianty z wyliczoną marżą | Raport wariantów dla testowych maili | mock; wrażliwe ceny i marże przy real data | Product |
| Nietypowe rabaty / niska marża → akceptacja przełożonego | Workflow akceptacji w ERP/CRM | Reguły polityki jako testowalne funkcje | Lista reguł w kodzie | mock | Feature |
| Niejasny mail klienta → ręczne przepisywanie na dane | Ręczne przepisywanie, EDI, formularze | Jedno wywołanie LLM ze structured output | Parser na zestawie testowych maili | mock; dane osobowe w real mailach | Feature |

## Recommended First Candidate

```text
Candidate:
Quote Context Card (karta zapytania ofertowego)

Reads:
testowe maile klientów + mock CRM / historia zamówień / stany / cennik (CSV lub Postgres)

Returns:
jedna strona na zapytanie: sparsowane żądanie, dane klienta, stan i ETA,
2–3 warianty dla wyjątku z marżą i flagą "wymaga akceptacji" według reguł polityki

Does not do:
nie wysyła maili, nie zapisuje w ERP/CRM, nie ma dynamicznego rejestru agentów,
nie podejmuje decyzji sam, nie ma dashboardu przebiegu

Data risk:
mock / local / read-only; przy prawdziwych mailach i cennikach najpierw uzgodnić dostęp i anonimizację

Direction if it proves valuable:
Product dla MŚP albo Feature w istniejącym ERP/CRM
```

## Why This Candidate

- Łączy kilka źródeł naraz (mail, CRM, magazyn, cennik), więc pasuje do wzorca "łączenie źródeł".
- Można ją przetestować tylko do odczytu na danych mock i porzucić bez strat.
- Przy 3–4 stałych narzędziach wystarczy stały graf workflow z jednym krokiem LLM. Dynamiczny wybór agentów po kompetencjach dodaje złożoność bez dowodu, że jest potrzebny, i przeczy tezie projektu (agenci tylko tam, gdzie workflow nie wystarcza).
- Elementy z sekcji "Najważniejsze elementy techniczne" (registry, capability discovery, tracing, idempotency) to cele pokazu technicznego, a nie bóle klienta. Jeśli projekt jest portfolio/szkoleniowy, karta jest rdzeniem, a orchestrator rozbudową w drugiej iteracji.

## Next Direction If Valuable

Najpierw Mom Test (3–5 rozmów z handlowcami: ostatnie zapytanie z wyjątkiem krok po kroku, ile systemów otwierali, ile to trwało, jak to dziś obchodzą), potem `/10x-shape` → `/10x-prd` → `/10x-roadmap`.
Największa luka: częstotliwość wyjątków, czas na ofertę i to, czy istniejące moduły ofertowania ERP/CRM już wystarczają.
