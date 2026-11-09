---
name: 10x-mom-test
description: >
  Validate any idea — product, feature, internal tool, service, or workflow —
  using The Mom Test principles before building. Use after someone has a draft
  idea or supporting notes (user interviews, tickets, or a shape/PRD/roadmap/
  opportunity-map) and wants to check whether the problem is real. Produces a
  non-leading critique, an interview guide, survey questions, and go/no-go
  decision criteria grounded in past behavior and concrete pain, not opinions
  about the solution.
---

# Mom Test: Zweryfikuj problem przed rozpoczęciem budowy

Ta umiejętność poddaje pomysł testowi wytrzymałości przed wdrożeniem. Pomaga użytkownikowi unikać uprzejmych fałszywych pozytywów, aspiracyjnych odpowiedzi i ankiet, które proszą ludzi o zatwierdzenie rozwiązania, którego faktycznie nigdy nie potrzebowali. Działa w przypadku każdego rodzaju pomysłu — aplikacji konsumenckiej, B2B SaaS, funkcji, narzędzia wewnętrznego lub firmy usługowej.

Domyślnie używaj języka angielskiego. Przełącz się na polski (lub dowolny inny język), jeśli użytkownik pisze do Ciebie w tym języku.

## Główna zasada

Nigdy nie pytaj, czy ludziom podoba się pomysł, czy używaliby produktu ani czy uważają funkcję za przydatną. Pytaj o to, co już robią, co wydarzyło się niedawno, czego próbowali, jaki ponieśli koszt i jakie obejście stosują obecnie.

Dobre pytania ujawniają zachowanie (w różnych dziedzinach):

- "Opowiedz mi krok po kroku, jak ostatnim razem próbowałeś zaplanować posiłki na tydzień — co dokładnie zrobiłeś?"
- "Co zrobiłeś ostatnim razem, gdy faktura nie odpowiadała wykonanej pracy?"
- "Kiedy ostatnio ręcznie sprawdzałeś, które PR-y blokowały wydanie?"
- "Jak radzisz sobie z tym dzisiaj, bez żadnego nowego narzędzia?"

Słabe pytania zachęcają do uprzejmości lub fantazjowania:

- "Czy używałbyś produktu takiego jak ten?"
- "Czy podoba Ci się ten pomysł?"
- "Czy dashboard z tymi danymi byłby przydatny?"
- "Ile zapłaciłbyś za to?"

## Dane wejściowe

Akceptuj dowolne z poniższych:

- pomysł podany inline,
- notatki od użytkowników, klientów, zgłoszeń, incydentów, wątków wsparcia, notatki ze spotkań lub wcześniejszych wywiadów,
- pomocniczy artefakt, jeśli istnieje, taki jak `context/team/opportunity-map.md`, `context/foundation/shape-notes.md`, `context/foundation/prd.md` lub `context/foundation/roadmap.md`.

Jeśli nie ma żadnych danych wejściowych, poproś o:

1. rozważany pomysł lub rozwiązanie,
2. docelowych użytkowników, klientów lub role,
3. podejrzewany problem lub utrudnienie,
4. informację, czy użytkownik chce wywiady, ankietę, czy oba.

## Proces

### Krok 1: Wyodrębnij hipotezy

Przeczytaj dostarczony materiał i wyodrębnij:

- **Użytkownik/rola**: kto ma problem.
- **Podejrzewane utrudnienie**: jaki powtarzalny problem występuje.
- **Obecne obejście**: jak użytkownik prawdopodobnie rozwiązuje to dzisiaj.
- **Proponowane rozwiązanie**: co twórca chce stworzyć.
- **Ryzykowne założenia**: twierdzenia, które mogą być błędne.
- **Istniejące dowody**: fakty z logów, zgłoszeń, wywiadów, incydentów lub danych użycia.

Oddziel fakty od przypuszczeń. Jeśli PRD jest dopracowane, ale dowody są skąpe, powiedz to wprost.

### Krok 2: Podważ pomysł w rozmowie

Przeprowadź krótką krytykę przed wygenerowaniem pytań:

- W którym miejscu użytkownik może mylić rozwiązanie z problemem?
- Które założenia zależą od przyszłych intencji zamiast od przeszłych zachowań?
- Co dowiodłoby, że nie warto budować rozwiązania dla tego problemu?
- Jaki istniejący produkt, narzędzie, proces lub ręczne obejście może już być wystarczająco dobre?
- Co byłoby silnym dowodem, że warto kontynuować?

Zadaj maksymalnie trzy pytania doprecyzowujące, tylko gdy są potrzebne. Preferuj pytania o użytkowników, niedawne incydenty, obecne obejścia lub wagę decyzji.

### Krok 3: Przepisz złe pytania

Jeśli użytkownik podaje robocze pytania, sklasyfikuj każde z nich:

- `keep`: konkretne i oparte na zachowaniu,
- `rewrite`: użyteczna intencja, ale pytanie sugerujące odpowiedź lub abstrakcyjne,
- `drop`: prosi o komplementy, hipotetyczne odpowiedzi, fantazje cenowe lub zatwierdzenie rozwiązania.

Dla każdego przepisanego pytania pokaż:

```text
Instead of:
[bad question]

Ask:
[better question]

Why:
[what signal this question can reveal]
```

### Krok 4: Przygotuj scenariusz wywiadu

Utwórz scenariusz wywiadu na 20–30 minut:

1. **Rozgrzewka kontekstowa**: rola, workflow, częstotliwość.
2. **Niedawna historia**: zapytaj o ostatnie rzeczywiste wystąpienie utrudnienia.
3. **Obecne obejście**: narzędzia, osoby, artefakty, czas, błędy.
4. **Koszt problemu**: opóźnienia, ponowna praca, ryzyko, obciążenie koordynacyjne.
5. **Istniejące alternatywy**: produkty, narzędzia, skrypty, dashboardy, ręczne nawyki lub rytuały.
6. **Sygnał decyzyjny**: co sprawiłoby, że warto byłoby to zmienić.
7. **Prośba na zakończenie**: zgoda na kontakt w przyszłości lub wgląd w zanonimizowane artefakty.

Uwzględnij 8–12 pytań. Zachowaj neutralność. Dodaj opcjonalne pytania pogłębiające dla interesujących odpowiedzi.

### Krok 5: Przygotuj ankietę

Utwórz krótką ankietę, aby uzyskać szerszy sygnał:

- Maksymalnie 6–10 pytań.
- Preferuj zakresy wielokrotnego wyboru dla częstotliwości i nakładu pracy.
- Uwzględnij 1–2 pytania otwarte o niedawne przykłady.
- Unikaj proszenia użytkowników o ocenę rozwiązania, którego nie doświadczyli.
- Uwzględnij jedno pytanie przesiewowe sprawdzające, czy respondent faktycznie ma do czynienia z tym workflow.

Ankieta powinna dostarczać dowodów do decyzji go/no-go, a nie oklasków.

### Krok 6: Zdefiniuj kryteria decyzji

Zakończ konkretnymi kryteriami:

- **Kontynuuj** jeśli: [obserwowalny próg]
- **Zawęź zakres** jeśli: [mieszany sygnał]
- **Nie buduj jeszcze** jeśli: [słaby sygnał]
- **Najpierw wypróbuj istniejące narzędzie/proces** jeśli: [istniejący produkt, narzędzie lub proces jest już wystarczająco dobry]

Używaj progów odpowiednich do kontekstu, na przykład:

- "Co najmniej 3 z 5 rozmówców opisuje to samo niedawne obejście bez zachęty."
- "Co najmniej 40% ankietowanych użytkowników docelowych zgłasza, że dzieje się to co tydzień lub częściej."
- "Problem kosztuje mierzalny czas, pieniądze lub dodatkową pracę — nie jest tylko lekką niedogodnością."

## Artefakt wyjściowy

Zaproponuj zapisanie wyniku w `context/team/mom-test-validation.md`, gdy istnieje katalog `context/` lub użytkownik chce trwałego artefaktu. Utwórz katalog `context/team/`, jeśli nie istnieje. Jeśli użytkownik preferuje inną ścieżkę, użyj jej.

Użyj następującej struktury:

```markdown
# Mom Test Validation Plan

## Input Idea

[short summary]

## Hypotheses

- **User/role**:
- **Friction**:
- **Current workaround**:
- **Risky assumptions**:
- **Evidence already present**:

## Critique

[non-leading critique]

## Interview Guide

[questions + follow-ups]

## Survey

[questions]

## Decision Criteria

- **Proceed**:
- **Narrow scope**:
- **Do not build yet**:
- **Try existing tool/process first**:
```
