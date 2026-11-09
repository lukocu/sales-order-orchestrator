---
name: 10x-opportunity-map
description: >
  Turn recurring friction or an unmet need into a
  build-vs-buy-vs-complement-vs-wait decision artifact: an opportunity map with
  the existing/default response, a thin complement, a first useful version, and a
  data-risk caveat, plus one recommended candidate to try. Works for any idea —
  product, feature, internal tool, service, or automation — with a worked
  internal-builder lens. Use when someone wants to classify pain or signals,
  decide whether something is worth building before writing code, or sort a "let's
  build a dashboard / agent / app / automation" idea into build, buy, complement,
  or wait.
---

# Mapa Możliwości: Klasyfikuj Pomysły Przed Rozpoczęciem Budowy

Ta umiejętność pomaga użytkownikowi zdecydować, czy powtarzające się tarcie lub niezaspokojona potrzeba powinny zostać obsłużone przez istniejące narzędzie lub domyślny workflow, przez cienkie uzupełnienie wokół tego, co już istnieje, przez pełniejszą budowę później, czy też przez całkowity brak budowy. Działa dla każdego pomysłu — produktu, funkcji, narzędzia wewnętrznego, usługi lub automatyzacji. Mapowanie możliwości jest ogólną techniką; bieżące przykłady używają **perspektywy twórcy narzędzi wewnętrznych** (narzędzia zespołowe, usługi, automatyzacje), ponieważ właśnie tam decyzja build-vs-buy jest najbardziej dotkliwa i tam podejmuje ją ścieżka 10xDevs internal-builder.

Wynikiem jest artefakt decyzyjny, a nie plan implementacji. Nie pisz kodu SDK, konfiguracji CI, pakietowania, auth, wdrożeń, harmonogramowania ani kroków backlogu/produktowania. Jeśli kandydat okaże się wartościowy, skieruj tę pracę dalej (zobacz Krok 5).

Domyślnie używaj angielskiego. Przełącz się na polski (lub inny język), jeśli użytkownik pisze do Ciebie w tym języku.

## Odpowiedź Początkowa

Po wywołaniu:

1. Jeśli użytkownik podał sygnały tarcia, notatki, tickety, notatki ze spotkań lub ścieżkę do pliku, odczytaj/zapisz je i kontynuuj.
2. Jeśli nie podano konkretnych danych wejściowych, poproś o **3–5 powtarzających się tarć lub niezaspokojonych potrzeb** oraz **źródła** stojące za nimi (GitHub, Linear/Jira, CI, Slack, docs, tickety wsparcia, analytics, wewnętrzna DB, CSV/mock data). Zachowaj otwartość — tarcie ma dowolną formę; nie wymuszaj dopasowania do opcji.
3. Zapytaj użytkownika: **Na jakich danych będzie działać pierwsza wersja?**

   - **Mock / local / read-only / non-sensitive (Recommended)**: Możesz zacząć lekko — bez kontroli dostępu lub audytowania na początku.
   - **Real company / customer / production data**: Rozważania o dostępie, uprawnieniach i audytowalności muszą poprzedzać implementację.
   - **Not sure yet**: Zaczniemy od najmniej wrażliwego wariantu i oznaczymy to jako do rozstrzygnięcia.

Następnie wyjaśnij, że najpierw sklasyfikujesz sygnały, a pierwszy kandydat zostanie zarekomendowany tylko wtedy, gdy na to zasłuży.

## Zasady Ochronne

- Traktuj „zbudujmy dashboard / agenta / app / automatyzację” jako proponowane rozwiązanie, a nie sygnał tarcia. Zapytaj, jaki powtarzający się ból, opóźnienie, koszt koordynacji lub ręczne sprawdzenie usuwa.
- Domyślnie kieruj ogólne workflowy narzędziowe/użytkowe do SaaS lub istniejących narzędzi, chyba że użytkownik pokaże lokalne tarcie między systemami.
- Preferuj uzupełnianie systemów źródłowych zamiast ich zastępowania. Pierwsza wersja może linkować do PRs, ticketów, jobs, docs i rekordów; nie może udawać nowego systemu of record.
- Utrzymuj pierwszą użyteczną wersję wąską, lokalną, tylko do odczytu i łatwą do porzucenia: skrypt, statyczny raport, podsumowanie CSV, widok podobny do arkusza kalkulacyjnego lub mockowany dashboard.
- Wcześnie eskaluj ryzyko danych. Dane mock/local/read-only/non-sensitive mogą pozostać lekkie. Rzeczywiste dane firmowe/klientów wymagają rozważań o kontroli dostępu i audytowalności przed implementacją.
- Zwracaj uwagę na złożoność istotną vs przypadkową. Niektóre tarcia są przypadkowe i cienkie uzupełnienie rzeczywiście je skraca; inne są istotne i odzwierciedlają rzeczywiste ograniczenie lub decyzję. Zanim uznasz tarcie za „naprawialne”, sprawdź, czy nie istnieje ono z konkretnego powodu.
- Nie sugeruj rezultatów (kariery, wzrostu, przychodu). Dźwignia oznacza realnie zmniejszony ból i zdobyte zaufanie, a nie gwarantowany wynik.

## Proces

### Krok 1: Normalizuj Sygnały

Przekształć surowe pomysły w konkretne sygnały. Dobre sygnały są obserwowalne i powtarzalne:

- „Każdego ranka ręcznie sprawdzamy, które PRs blokują release.”
- „Tickety i zmiany w kodzie rozchodzą się, więc statusowi trudno zaufać.”
- „Umiejętności i reguły AI są ręcznie kopiowane między repozytoriami.”
- „Komentarze do review się powtarzają, ale nie są zakodowane jako quality gate.”

Słabe sygnały wymagają rozwinięcia:

- „Zbuduj dashboard.”
- „Dodaj agenta.”
- „Zautomatyzuj wszystko.”

Dla każdego słabego sygnału zadaj jedno krótkie pytanie, które oddziela ból od proponowanego rozwiązania.

### Krok 2: Klasyfikuj Każdy Sygnał

Przejdź przez sygnały **po jednym na raz**, jako blok dla każdego sygnału — nie renderuj szerokiej tabeli w środku rozmowy. Każdy blok jest łatwiejszy do przeczytania i skomentowania oraz pozwala użytkownikowi skorygować jeden sygnał, zanim przejdziesz dalej:

```text
Signal: [repeated observable pain or unmet need]
  Existing / default response: [what existing tools or workflows already do]
  Thin complement: [the smallest complement around existing systems]
  First useful version: [local/read-only/mockable check]
  Data risk: [mock / local / read-only / non-sensitive / real company-customer data]
  Direction if it proves valuable: [product / feature / internal tool / service / wait]
```

Wskazówki dla każdego pola — utrzymuj komórki końcowej tabeli zwięzłe (fraza, nie akapit); dłuższe uzasadnienie przenieś do Kroku 4 i notatki „Why this candidate”:

- **Signal**: powtarzający się obserwowalny ból lub niezaspokojona potrzeba, najlepiej z kosztem koordynacji.
- **Existing / default response**: co GitHub, Linear/Jira, Slack, Notion, CI, dashboards, natywne podsumowania AI, raporty, filtry, gotowy SaaS lub istniejące procesy już robią.
- **Thin complement**: uzupełnienie wokół istniejących systemów, szczególnie gdy wartość wynika z połączenia dwóch lub większej liczby źródeł.
- **First useful version**: lokalna/tylko do odczytu/mockowalna wersja, która weryfikuje wartość bez pełnej odpowiedzialności za produkt.
- **Data risk**: `mock`, `local`, `read-only`, `non-sensitive` lub `real company/customer data`; dodaj praktyczne zastrzeżenie, gdy dane są wrażliwe.
- **Direction if it proves valuable** — rodzaj rozwiązania, w które rozwinie się po zdobyciu stałego użytkownika. Najpierw wybierz ogólny kształt: `Product`, `Feature` w istniejącym produkcie, `Internal tool`, `Service` lub `Wait / no build` (sygnał słaby, już rozwiązany lub niewart utrzymania). Gdy tym kształtem jest **internal tool**, ścieżki 10xDevs internal-builder go doprecyzowują:
  - `Team agent`, gdy potrzebuje SDK, tools, wywołań modelu, obsługi kosztów/prywatności lub metrics.
  - `Review / CI gate`, gdy wartością jest code review, PR gates, Definition of Done lub zachowanie CI.
  - `Shared artifact registry`, gdy problemem są współdzielone skills, prompts, rules, commands, packages lub dystrybucja artefaktów zespołowych.
  - `Async / remote work`, gdy pomocnik powinien działać zdalnie, asynchronicznie lub według harmonogramu.

Po sklasyfikowaniu wszystkich sygnałów możesz odczytać je ponownie jako zwartą tabelę porównawczą (jeden wiersz na sygnał, zwięzłe komórki) — ta łatwa do przeskanowania macierz trafia do zapisanego artefaktu.

### Krok 3: Zarekomenduj Jednego Kandydata

Wybierz co najwyżej jednego kandydata dla pierwszej użytecznej wersji. Uporządkuj według:

1. Powtarza się regularnie.
2. Łączy co najmniej dwa źródła informacji lub dwie role.
3. Ma dziś wyraźny ręczny ból.
4. Może zostać przetestowany tylko do odczytu lub na danych mock/wyeksportowanych.
5. Nie zastępuje odpowiedzialności istniejącej platformy.
6. Ma jasny późniejszy kierunek, jeśli okaże się wartościowy.

Jeśli żaden sygnał nie przejdzie, zarekomenduj brak budowy i wyjaśnij, które istniejące narzędzie lub domyślna odpowiedź powinny zostać wypróbowane najpierw. Zbudowanie dwóch lub trzech przemyślanych kandydatów jest lepsze niż wydanie dziesięciu prototypów, których nikt nie utrzymuje — deficytowym zasobem jest uwaga potrzebna do utrzymania ich przy życiu, a nie czas na ich rozpoczęcie.

### Krok 4: Przygotuj Pierwszą Użyteczną Wersję

Dla wybranego kandydata napisz:

```text
Candidate:
[working name]

Reads:
[sources, e.g. GitHub export, Jira CSV, CI logs, mock data]

Returns:
[short report/view/digest description]

Does not do:
[what is intentionally excluded now]

Data risk:
[mock/local/read-only/non-sensitive or real company/customer data; for real data, say what access limitation must come first]

Direction if it proves valuable:
[product / feature / internal tool / service / wait]
```

Następnie dodaj krótką notatkę „Why this one, not the others”.

### Krok 5: Zdecyduj o Następnym Ruchu

Mapa możliwości klasyfikuje problem na papierze. Zanim przekształcisz klasyfikację w kod, zdecyduj, jak postępować:

Zapytaj użytkownika: **Masz mapę i kandydata. Co dalej?**

- **Validate, then shape — /10x-mom-test → /10x-shape (Recommended)**: Sprawdź problem w rozmowach o wcześniejszych zachowaniach. Jeśli się utrzyma, zweryfikowana możliwość trafia do /10x-shape → /10x-prd → /10x-roadmap.
- **Shape now without validating — /10x-shape → /10x-prd → /10x-roadmap**: Tylko gdy masz już pewność, że problem jest realny, a ryzyko jest zrozumiane. Pomija najtańszy krok zbierania dowodów.
- **Go straight to building — /10x-new → /10x-research → /10x-plan → /10x-implement**: Gdy sygnał jest wąski, pierwsza wersja jasna, a ryzyka zrozumiane.
- **Nothing for now**: Zapisz mapę i wróć, gdy zgromadzi się więcej sygnałów.

Niezależnie od wybranej ścieżki najtańszym pierwszym krokiem jest zwykle krótka rozmowa z osobami, które żyją z tym tarciem (w przypadku narzędzia wewnętrznego — z menedżerem i zespołem, dla którego jest przeznaczone) — często wiedzą, dlaczego tarcie istnieje i czy Twój obraz sytuacji jest pełny. W końcowej wiadomości nazwij wybraną umiejętność; nie uruchamiaj jej samodzielnie, chyba że użytkownik o to poprosi.

## Artefakt

Zaproponuj zapisanie wyniku. Zapytaj użytkownika: **Save the opportunity map to a file?**

- **Yes — context/team/opportunity-map.md (Recommended)**: Standardowa ścieżka. Utwórz katalog, jeśli go brakuje.
- **Different path**: Podaj własną lokalizację pliku.
- **Don't save**: Zachowaj mapę wyłącznie w rozmowie.

Podczas zapisu utwórz katalog docelowy, jeśli jest potrzebny. Użyj następującej struktury pliku:

```markdown
# Opportunity Map

## Context

- **Project / context**:
- **Data constraint**:
- **Date**:

## Map

One row per signal, terse cells (a phrase each) — longer reasoning belongs in the sections below:

| Signal | Existing / default response | Thin complement | First useful version | Data risk | Direction if valuable |
| ------ | --------------------------- | --------------- | -------------------- | --------- | --------------------- |

## Recommended First Candidate

[first useful version block]

## Why This Candidate

[brief justification]

## Next Direction If Valuable

[direction and rationale]
```
