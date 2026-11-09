# Mom Test Validation Plan

## Input Idea

Intelligent Sales Order Orchestration System: hybrydowy system dla MŚP handlowych i produkcyjnych. Standardowe zapytania ofertowe obsługuje deterministyczny workflow, a wyjątki (brak pełnej ilości, zamienniki, konflikt cena–termin, nietypowy rabat) trafiają do orchestratora delegującego zadania do wyspecjalizowanych agentów AI. Decyzję końcową zatwierdza policy engine albo człowiek. Pierwszy kandydat z mapy możliwości: Quote Context Card (karta zapytania read-only na danych mock).

Źródło: `context/team/opportunity-map.md` oraz opis projektu od autora. Plan jest w oryginalnej formie testu problemu (bez uwzględniania celu portfolio).

## Hypotheses

- **User/role**: handlowiec / opiekun klienta / dział ofertowania w firmie handlowej lub produkcyjnej (MŚP). Role poboczne: przełożony akceptujący wyjątki, magazynier, zakupowiec.
- **Friction**: przygotowanie oferty wymaga ręcznego składania informacji z poczty, CRM, ERP, magazynu, cenników i historii klienta; trudne przypadki (brak pełnej dostępności, zamienniki, cena vs termin) wymagają decyzji, nie tylko wyszukania danych.
- **Current workaround**: Excel z cennikami, ERP otwarte w kilku oknach, telefon do magazynu lub dostawcy, pamięć handlowca, szablony maili, pytanie do przełożonego na czacie.
- **Risky assumptions**:
  1. Wyjątki są wystarczająco częste i kosztowne (czas, utracone zamówienia), żeby uzasadniać osobną warstwę.
  2. Kontekst faktycznie jest rozproszony w 5+ systemach. W wielu MŚP jest jeden ERP i Excel, więc ból może być mniejszy.
  3. Obecne ERP/CRM (ATP, zamienniki, workflow akceptacji) nie rozwiązują już tego wystarczająco.
  4. Dane są na tyle uporządkowane (parametry techniczne, powiązania zamienników, ETA dostawców), żeby agent mógł z nich wnioskować.
  5. Firmy pozwolą wysłać treści maili, ceny i marże do zewnętrznego LLM.
  6. Handlowcy zaufają rekomendacji i nie będą jej w całości weryfikować ręcznie.
  7. Szybkość odpowiedzi realnie wpływa na wygranie zamówienia.
  8. Wolumen zapytań jest wystarczający, żeby automatyzacja się opłaciła.
- **Evidence already present**: brak. Jest jeden hipotetyczny scenariusz (ABC-100 × 80) i lista kroków bez liczb. Brak rozmów z użytkownikami, logów, ticketów i danych o wolumenie, czasie przygotowania oferty czy odsetku wyjątków. Dokument jest dopracowany technicznie, ale dowodowo pusty.

## Critique

- **Rozwiązanie zamiast problemu.** Zdecydowana większość opisu to architektura (orchestrator, rejestr kompetencji, stack). Ból zajmuje jeden akapit i jest sformułowany przez autora, nie przez użytkownika.
- **Zbyt czysty scenariusz.** Przykład z ABC-100/ABC-110 zakłada dokładne stany, wiarygodne ETA i znaną kompatybilność. W realnych firmach stany bywają nieaktualne, kompatybilność siedzi w głowie technologa, a ETA dostawcy trzeba wywalczyć telefonem. Jeśli luka jest w danych, a nie w rozumowaniu, agent jej nie zamknie.
- **Przyszłe intencje.** "Zaufają rekomendacji", "oszczędzą czas", "zaakceptują zamiennik" to przypuszczenia o przyszłości. Trzeba pytać, kiedy ostatnio zaproponowali zamiennik i kto o tym zdecydował.
- **Odpowiedzialność.** Kto dziś bierze odpowiedzialność za zamiennik lub niższą marżę? Jeśli to zawsze człowiek z doświadczeniem i podpisem, system może tylko podpowiadać, a to zmienia wartość.
- **Już rozwiązane gdzie indziej?** Moduły ofertowania ERP, portale B2B, EDI, szablony i dobry handlowiec mogą już wystarczać. Najczęstszą "konkurencją" nie jest produkt, tylko Excel plus doświadczenie.
- **Co dowiodłoby, że nie warto budować:** wyjątki to kilka procent zapytań, rozwiązuje je się w kilka minut, albo ból leży gdzie indziej (np. w jakości danych, a nie w składaniu kontekstu).
- **Co byłoby silnym dowodem za:** kilku rozmówców niezależnie opisuje podobne, niedawne wyjątki zajmujące 30+ minut, obejmujące kilka systemów i telefony, z udokumentowanym kosztem (opóźniona oferta, utracone zamówienie, zbyt niska marża).

## Interview Guide

Cel: 5–8 rozmów po 20–30 minut z handlowcami / opiekunami klienta / osobami ofertującymi w MŚP handlowych i produkcyjnych, plus 2 z przełożonymi lub zakupowcami. Nie opisuj pomysłu. Jeśli zapytają, powiedz tylko, że badasz, jak wygląda przygotowanie ofert.

**Zasady prowadzenia:** pytaj o ostatni raz, nie o ogół. Milcz po odpowiedzi. Nie podpowiadaj. Proś o artefakty (zanonimizowany mail, arkusz, zrzut ekranu). Na koniec nie sprzedawaj, tylko poproś o kontakt.

1. **Rozgrzewka.** "Opowiedz, czym się zajmujesz w ciągu typowego dnia. Ile zapytań ofertowych obsługujesz tygodniowo?"
   - Pogłębienie: "Kto je przysyła i jakim kanałem?"
2. **Ostatnie zapytanie.** "Przypomnij sobie ostatnie zapytanie ofertowe, przy którym coś było nietypowe. Opowiedz krok po kroku, co zrobiłeś od otrzymania maila do wysłania odpowiedzi."
   - Pogłębienie: "Które programy i pliki otwierałeś? Do kogo dzwoniłeś lub pisałeś?"
3. **Czas.** "Ile to trwało od początku do wysłania oferty? Gdzie ten czas poszedł?"
4. **Wyjątki.** "Jak często zdarza się, że nie ma pełnej ilości albo termin jest nierealny? Kiedy to było ostatnio?"
   - Pogłębienie: "Co wtedy zrobiłeś? Kto o tym zdecydował?"
5. **Zamienniki.** "Kiedy ostatnio proponowałeś klientowi zamiennik? Skąd wiedziałeś, że pasuje?"
   - Pogłębienie: "Czy ta wiedza jest gdzieś zapisana, czy jest w czyjejś głowie?"
6. **Rabaty i marża.** "Opowiedz o ostatnim razie, gdy musiałeś zapytać przełożonego o rabat lub niższą marżę. Jak to wyglądało i ile trwało?"
7. **Obecne obejścia.** "Czego dziś używasz, żeby to ogarnąć? Excel, notatki, ERP, coś jeszcze? Co jest w tym najbardziej uciążliwe?"
8. **Koszt.** "Czy zdarzyło się, że oferta wyszła za późno, z błędem albo zamówienie przepadło przez to, jak to wyglądało? Opowiedz o ostatnim takim przypadku."
   - Pogłębienie: "Ile to kosztowało, jeśli wiesz?"
9. **Alternatywy.** "Próbowaliście kiedyś coś z tym zrobić: nowy moduł, skrypt, szablon, dodatkowa osoba? Co z tego wyszło?"
10. **Dane.** "Gdzie trzymacie stany magazynowe, ceny, historię klienta, powiązania zamienników? Jak aktualne to jest?"
11. **Zaufanie i odpowiedzialność.** "Kiedy ostatnio ktoś inny (lub program) coś Ci zaproponował przy ofercie, a Ty to sprawdzałeś? Co sprawdzałeś i dlaczego?"
12. **Zamknięcie.** "Kogo jeszcze powinienem o to zapytać? Czy mogę zobaczyć zanonimizowany przykład takiego zapytania i odpowiedzi? Czy mogę wrócić z dalszymi pytaniami?"

**Czego nie pytać** (i czym zastąpić):

```text
Instead of:
Czy system, który sam przygotuje ofertę, by Ci się przydał?

Ask:
Opowiedz o ostatniej ofercie, której przygotowanie zajęło najwięcej czasu. Co dokładnie było najdłuższe?

Why:
Pokazuje faktyczny koszt i miejsce bólu zamiast uprzejmej aprobaty.
```

```text
Instead of:
Ile byś zapłacił za takie narzędzie?

Ask:
Na co dziś wydajecie pieniądze lub czas, żeby to ogarnąć (osoba, licencja, nadgodziny)?

Why:
Ujawnia istniejący budżet i priorytet, a nie fantazję cenową.
```

```text
Instead of:
Czy ufałbyś rekomendacji AI?

Ask:
Kiedy ostatnio program lub koleżanka coś Ci zaproponowali i co zrobiłeś, zanim to wysłałeś klientowi?

Why:
Pokazuje rzeczywisty poziom weryfikacji i odpowiedzialności.
```

## Survey

Dystrybucja: do osób w sprzedaży B2B / ofertowaniu w MŚP (grupy branżowe, LinkedIn, kontakty z wywiadów). Cel: szerszy sygnał częstotliwości i kosztu, nie ocena pomysłu.

1. **Przesiew.** Czy w ciągu ostatnich 30 dni przygotowywałeś/aś oferty lub wyceny dla klientów firmowych? (Tak / Nie → koniec)
2. Ile zapytań ofertowych obsługujesz średnio tygodniowo? (<5 / 5–20 / 21–50 / >50)
3. Z ilu różnych systemów lub źródeł zwykle korzystasz przy jednej ofercie? (1 / 2–3 / 4–5 / 6+)
4. Ile średnio trwa przygotowanie oferty dla standardowego zapytania? (<10 min / 10–30 min / 30–60 min / >1 h)
5. Jaki odsetek zapytań z ostatniego miesiąca wymagał nietypowej decyzji (brak ilości, zamiennik, specjalny rabat, termin)? (<5% / 5–15% / 16–30% / >30%)
6. Jak długo trwa przygotowanie oferty w takim nietypowym przypadku? (<30 min / 30–60 min / 1–3 h / >3 h / dłużej niż dzień)
7. Jak często musisz konsultować decyzję z przełożonym lub innym działem? (Codziennie / Co tydzień / Rzadziej / Nigdy)
8. Czy w ostatnich 3 miesiącach zdarzyło się, że oferta wyszła za późno lub z błędem i miało to konsekwencje? (Tak, kilka razy / Raz / Nie) — jeśli tak: *Opisz ostatni taki przypadek w 1–2 zdaniach.*
9. Czego dziś używasz do składania oferty? (wielokrotny wybór: ERP, CRM, Excel, poczta, telefon do magazynu/dostawcy, portal B2B, inne)
10. (Otwarte) Opisz ostatnie zapytanie, które zajęło Ci najwięcej czasu, i co było najtrudniejsze.

## Decision Criteria

- **Proceed** jeśli: co najmniej 3 z 5 rozmówców bez podpowiedzi opisuje niedawny wyjątek, który zajął 30+ minut i wymagał kilku systemów lub telefonów, oraz co najmniej 40% ankietowanych zgłasza nietypowe decyzje w >15% zapytań lub oferty >1 h, i przynajmniej 2 osoby podają konkretny koszt (opóźnienie, błąd, utracone zamówienie).
- **Narrow scope** jeśli: ból dotyczy tylko jednego wycinka (np. samej weryfikacji dostępności albo samego parsowania maili), tylko niektórych branż albo głównie jakości danych. Wtedy zawęź do tego wycinka (np. samo Quote Context Card bez orchestratora).
- **Do not build yet** jeśli: wyjątki to <5% zapytań lub zajmują <15 minut, rozmówcy nie potrafią przywołać niedawnego przypadku albo mówią tylko ogólnikami ("fajnie by było"), albo największym problemem są dane, a nie składanie kontekstu.
- **Try existing tool/process first** jeśli: rozmówcy mówią, że ich ERP/CRM ma ATP, zamienniki i workflow akceptacji, ale nikt ich nie skonfigurował, albo prosty szablon plus arkusz rozwiązuje większość problemu.

## Co zrobić z wynikami

Po wywiadach przynieś notatki (nawet surowe) i ankietę. Zestawię odpowiedzi z kryteriami powyżej i zaktualizuję werdykt.
