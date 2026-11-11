# Rekomendacja z uzasadnieniem i pewnością: brief planu

> Pełny plan: `context/changes/recommendation-with-confidence/plan.md`
> Research: `context/changes/recommendation-with-confidence/research.md`

## Co i po co

**Co powstaje:** czwarty etap potoku zapytania (S-05, FR-007). Handlowiec widzi jedną rekomendowaną opcję realizacji: częściową dostawę, zamiennik, inne źródło albo ich kombinację. Opcja ma uzasadnienie odwołujące się do danych firmy i pewność wyliczoną z jawnych sygnałów, nie z samooceny modelu.

**Dlaczego to ważne:** to „gwiazda przewodnia” roadmapy. W tym miejscu orchestrator ma pokazać przewagę nad stałym workflow.

## Stan wyjściowy

**S-04** zapisuje wyniki czterech deterministycznych agentów w `inquiry_orchestrations`:
- zgodność zamiennika;
- stan zamiennika;
- oferta dostawcy;
- historia klienta.

**S-03** zapisuje stan, brak i rabat klienta w `inquiry_checks`.

Danych o koszcie i marży nie ma. Wzorzec etapu (fake/LLM, run, upsert z łańcuchem wersji, `stale`, re-run) jest gotowy w `orchestration/`.

## Stan docelowy

Pod sekcją orchestracji pojawia się panel rekomendacji:
- **wybrana opcja:** linie (produkt, ilość, źródło, data), pokrycie, termin, wartość, marża i pasmo HIGH/MEDIUM/LOW;
- **„Dlaczego ta rekomendacja?”:** uzasadnienie z listą sygnałów pozytywnych i ryzyk;
- **pozostałe opcje**, do porównania;
- **re-run**.

W trybie fake ACME dostaje stan + zamiennik ABC-110 (HIGH, 25,51%), Omega stan + Hydro-Valve (HIGH, 23,75%), a Delta najlepszą możliwą kombinację, 290/500 (LOW).

## Kluczowe decyzje

| Decyzja | Wybór | Dlaczego | Źródło |
|---|---|---|---|
| Marża | Dosiać `unit_cost` produktów i ofert dostawców w S-05; marża jest pokazywana i trafia do rekomendera | PRD każe wybierać najlepszą marżę, a S-06 dostanie gotowe liczby | Plan |
| Cena linii | Cena katalogowa produktu faktycznie oferowanego × (1 − rabat standardowy) | Sprzedaż zamiennika w cenie produktu żądanego to późniejsza polityka | Plan (korekta użytkownika) |
| Kto wybiera | LLM wybiera spośród opcji zbudowanych przez kod i pisze uzasadnienie; kod waliduje `option_id` i cytowane sygnały | Orchestrator faktycznie decyduje, a liczby i oceny zostają w kodzie | Plan |
| Ranking | Deterministyczny ranking (pasmo → pokrycie → data → marża) tylko jako strategia `FakeRecommender` | Nie narzuca wyboru LLM; daje przewidywalny tryb lokalny i testy | Plan (korekta użytkownika) |
| Opcje | Stan + zamiennik / + dostawca / + oba, gdy żadne pojedyncze źródło nie pokrywa braku | Trudne przypadki (Delta) dostają maksymalne pokrycie | Plan |
| Pewność | Pasma z jawnych reguł plus lista sygnałów ✓/⚠, bez liczby 0–100 | Ręcznie wymyślone wagi dawałyby pseudoprecyzję | Plan (propozycja użytkownika) |
| Reguły pasm | LOW: niepełne pokrycie lub przekroczony termin. MEDIUM: wykonalne, ale z ryzykiem. HIGH: bez ryzyk | Czytelne i sprawdzalne | Plan |
| Niepełne dane | Opcje tylko z ukończonych tasków; brakujący task to ryzyko. Nieudana lub nieaktualna orchestracja: brak rekomendacji z powodem. Błąd LLM: zapisany błąd, opcje widoczne, re-run | Maksimum informacji z nazwanym ryzykiem | Plan |
| Granica z S-06 | Bez progu marży; rabat i kredyt ocenia S-06 | Progi żyją tylko w polityce | Plan |
| Łańcuch wersji | Rekomendacja przypięta do analizy, sprawdzeń i `orchestrated_at` | Ta sama lekcja co F1 w S-04 | Research |

## Zakres

**W zakresie:**
- migracja 0009 (koszt + tabela `inquiry_recommendations`);
- rdzeń opcji, wyceny i pasm;
- rekomender fake i LLM z walidacją;
- etap w łańcuchu, widok, `POST /inquiries/{id}/recommendation`;
- panel w UI, README, weryfikacja na Render.

**Poza zakresem:**
- progi i werdykt polityki (S-06);
- edycja opcji, szkic odpowiedzi i decyzja (S-07);
- regułowy fallback przy błędzie LLM;
- pewność liczbowa;
- nowe agenty i ponowne planowanie;
- zmiany istniejących modeli JSONB i `trace_steps`.

## Architektura

Łańcuch wygląda tak: `analyze/correct` → checks → orchestration → **recommendation**.

Etap rekomendacji:
1. Czyta bieżące sprawdzenia, orchestrację i ceny.
2. `build_options` składa opcje i je wycenia.
3. `assess` nadaje pasma i sygnały.
4. Rekomender (fake albo LLM) zwraca `{option_id, justification, cited_signals}`.
5. `validate_choice` sprawdza wybór.
6. Wynik jest zapisywany z kontrolą wersji pod `FOR UPDATE`.

Każde wywołanie ma własny run z krokami `options` i `choose`.

## Fazy w skrócie

| Faza | Co dostarcza | Główne ryzyko |
|---|---|---|
| 1. Dane kosztu i schemat | `unit_cost`, tabela rekomendacji, seed | Backfill NOT NULL na danych spoza seedu |
| 2. Rdzeń rekomendacji | Opcje, wycena, sygnały, pasma, fake, walidacja | Kombinatoryka opcji i przypadki brzegowe tasków |
| 3. Serwis, zapis i API | Etap w łańcuchu, `stale`, re-run, widok | Wyścigi wersji między trzema etapami |
| 4. Rekomender LLM | Wybór i uzasadnienie z Groq | Model cytuje sygnały spoza opcji, co daje odrzucenia |
| 5. Frontend i wdrożenie | Panel, README, Render | Czytelność wielu opcji w UI |

**Warunki wstępne:** S-04 zarchiwizowany i wdrożony (0008 na Render).

**Szacowany nakład:** ok. 4–5 sesji w 5 fazach.

## Ryzyka i założenia

- Stan własny jest dostępny w `reference_date` analizy, bez czasu kompletacji.
- Koszty w seedzie są przykładowe i dobrane tak, żeby marże opcji się różniły.
- Opcje są podawane LLM w kolejności budowania. Model może wybrać opcję z niższym pasmem. Jest to dozwolone i widoczne, bo pasmo i ryzyka są przy opcji.
- Walidacja uzasadnienia sprawdza cytowane kody sygnałów, a nie sens tekstu.

## Kryteria sukcesu (podsumowanie)

- Dla zapytania z wyjątkiem handlowiec widzi jedną wybraną opcję z uzasadnieniem, pasmem i sygnałami. Wszystkie liczby pochodzą z danych.
- Trzy scenariusze seedu dają w trybie fake wyniki z tabeli. Z Groq wybór przechodzi walidację, a krok `choose` ma tokeny i koszt.
- Rekomendacja nigdy nie jest cicho nieaktualna: przy zmianie danych jest odrzucana albo oznaczona `stale`.
