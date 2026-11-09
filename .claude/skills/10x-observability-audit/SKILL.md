---
name: 10x-observability-audit
description: >
  Audit an existing codebase for code logic that hides production errors:
  swallowed exceptions, errors turned into redirects or 200s, lost stack
  traces and causes, code paths running outside the error tracker, logs that
  never become alerts. Picks the critical user flows from
  context/foundation (shape-notes, PRD, roadmap) or asks for 2-3 areas,
  fans out full-stack subagent audits, optionally proves gaps at runtime
  with a local fake error-tracker endpoint, and writes a new dated report
  under context/audits/observability/ on every run. Use whenever the user
  asks why production errors are missing or hard to debug, wants an
  observability / monitoring / error-tracking / logging audit, asks "what
  does Sentry (or Datadog, Rollbar, CloudWatch…) miss", "audyt
  observability", "czego nie widzimy w monitoringu", or wants to re-run a
  previous observability audit. Tech-stack agnostic.
---

# Audyt obserwowalności: gdzie znikają błędy produkcyjne?

Celem jest jedno pytanie, zadawane dla każdego krytycznego przepływu użytkownika: **gdy to zepsuje się na produkcji, czy ktokolwiek się o tym dowie i czy będzie w stanie stwierdzić dlaczego?**

Większość baz kodu nie przechodzi tego testu na kilka systemowych sposobów, a nie w setkach niezwiązanych ze sobą miejsc. Niektóre ścieżki kodu działają poza zakresem trackera błędów. Awarie wracają jako zwykłe odpowiedzi. Obiekty błędów są porzucane przy pierwszym `catch`. Filtry prywatności usuwają dane diagnostyczne. Wdrożenia nie są oznaczane. Zadaniem audytu jest znaleźć te mechanizmy, pokazać konkretne miejsca, w których szkodzą przepływom mającym znaczenie, oraz udowodnić najgorsze z nich. Nie tworzy on listy w stylu lintera, zawierającej każdy pusty `catch`.

**Przedmiotem jest kod aplikacji.** Audyt pyta, co kod robi z awarią, gdy potok monitorowania już istnieje: czy ją rzuca, przechwytuje, loguje, raportuje, spłaszcza czy porzuca? To, czy produkt do logowania lub tracker błędów jest włączony, jest warunkiem wstępnym, a nie pytaniem audytu. Często ustawia się to w panelu platformy lub dostawcy, więc repozytorium nie może tego pokazać. Zakładaj, że potok działa na produkcji, chyba że użytkownik stwierdzi inaczej. Konfiguracja, której repozytorium nie zawiera, jest **nieznana, a nie brakująca**, i nigdy nie staje się przyczyną źródłową.

Umiejętność nigdy nie modyfikuje audytowanego kodu w głównym drzewie roboczym. Zapisuje jeden nowy raport na uruchomienie. Dowód działania w runtime następuje wyłącznie w jednorazowej, odizolowanej kopii.

## Kiedy używać, kiedy pominąć

**Użyj, gdy** projekt ma kod działający na produkcji (lub zaraz będzie go miał), a użytkownik podejrzewa, że błędy są niewidoczne, zaszumione lub niemożliwe do zdiagnozowania. Użyj także przed premierą, po incydencie typu „nie mieliśmy żadnych logów” albo aby ponownie sprawdzić wcześniejszy audyt.

**Pomiń, gdy** użytkownik chce naprawić jeden konkretny znany błąd: to jest zwykłe debugowanie. Pomiń także, gdy chce _wybrać_ dostawcę monitorowania (`/10x-infra-research`) albo przeprowadzić ogólną kontrolę kondycji projektu (`/10x-health-check`).

## Dane wejściowe

- **Dokumenty bazowe (opcjonalne, preferowane):** `context/foundation/shape-notes.md`, `context/foundation/prd.md`, `context/foundation/roadmap.md`. Informują, które przepływy mają znaczenie dla użytkowników i biznesu, dzięki czemu audyt przeznacza na nie swój budżet.
- **Objaw (opcjonalny, najcenniejszy):** to, co użytkownik już widzi, np. „żądania pojawiają się w logach, ale błędy, których szukam, nie”. Taki objaw potwierdza, że potok działa, i kieruje audyt na ścieżki kodu, które gubią błędy. Użyj go do ukierunkowania wyboru obszarów i briefów dla audytorów.
- **Argumenty (opcjonalne):** nazwy obszarów (np. `login checkout "admin import"`) zastępują wybór obszarów. `--runtime` włącza dowód runtime bez pytania. `--verify <report>` ponownie sprawdza ustalenia wcześniejszego raportu zamiast szukać nowych (zobacz _Tryb weryfikacji_). `--out <dir-or-file>` albo wskazanie przez użytkownika lokalizacji słowami zastępuje miejsce zapisu raportu (zobacz Krok 6).
- **Poprzednie raporty (opcjonalne):** `*.md` w katalogu raportów (domyślnie `context/audits/observability/`).

## Przepływ pracy

Śledź kroki za pomocą listy zadań. Audyt jest długi, a użytkownik powinien widzieć, na jakim jest etapie.

### Krok 0 — Warunki wstępne i tożsamość uruchomienia

1. Potwierdź, że cwd jest bazą kodu (manifest projektu, katalogi źródłowe). Jeśli nie, zatrzymaj się i to powiedz.
2. Zapisz tożsamość uruchomienia. Każdy raport jest zakotwiczony dokładnie w tym, co zostało poddane audytowi, co umożliwia porównywanie ponownych uruchomień:
   - data (`date +%Y-%m-%d`) i czas (`date +%H:%M`), bieżący commit (`git rev-parse --short HEAD`), gałąź oraz informacja, czy drzewo jest brudne (`git status --porcelain`). Brudne drzewo jest w porządku, ale należy to zaznaczyć w raporcie.
3. Wyświetl listę wcześniejszych raportów w katalogu raportów (domyślnie `context/audits/observability/`): `ls <report-dir> 2>/dev/null`. Przeczytaj frontmatter najnowszego z nich: objęte obszary, commit, otwarte ustalenia. Wybierz go według klucza `date`, który zawiera czas; nazwy plików zawierają tylko dzień. Użyjesz go w Kroku 2 i Kroku 6.

### Krok 1 — Odkryj stos obserwowalności

Przed audytem przepływów zbuduj **model przechwytywania**: krótki, poparty dowodami opis tego, jak awaria przechodzi od kodu do człowieka. Zrób to samodzielnie (wymaga to osądu i jest niewielkie). Cytuj plik:wiersz dla każdego twierdzenia.

- **Runtime i platforma:** długo działający serwer, funkcje serverless/edge, kontenery, mobile, browser SPA, framework SSR, workery w tle, cron, kolejki.
- **Tracker błędów:** Sentry, Datadog, Rollbar, Bugsnag, Honeybadger, New Relic, OpenTelemetry exporter, Application Insights, Crashlytics lub żaden. Znajdź _każde_ miejsce inicjalizacji i zanotuj, co obejmuje każde z nich.
- **Granice przechwytywania:** gdzie tracker faktycznie otrzymuje aktywnego klienta? Globalny handler procesu, middleware per-request, wrapper per-route, integracja frameworka, filtr wyjątków, granica błędów. Centralne pytanie brzmi: **które ścieżki kodu wykonują się poza jakąkolwiek granicą**. Przykłady: middleware ustawione przed trackerem, trasy rezygnujące z niego, strumieniowane ciała odpowiedzi, zadania w tle po odpowiedzi, procesy workerów bez własnej inicjalizacji, aplikacja po stronie klienta.
- **Logowanie:** logger(y), miejsce docelowe logów (usługa logów platformy, plik, stdout), czy linie logów kiedykolwiek stają się alertami lub zgłoszeniami oraz jak logger serializuje obiekty błędów.
- **Czyszczenie i próbkowanie:** hooki w stylu `beforeSend`, filtry PII, współczynniki próbkowania, listy ignorowania, head-sampling logów.
- **Tożsamość wdrożenia:** tagi wydania/wersji i środowiska; source maps lub debug symbols; czy ruch preview/staging można odróżnić od produkcyjnego.

Ten krok powinien być krótki. To kontekst dla audytu kodu, a nie sam audyt. Oznacz każde twierdzenie jako **w repozytorium** (cytowany plik:wiersz) lub **poza repozytorium** (ustawienie panelu lub platformy, którego nie możesz zobaczyć). Dla elementów spoza repozytorium zapisz założenie („założono: zbieranie logów platformy jest włączone”) zamiast ustalenia. Jeśli cały audyt zależy od jednego z nich (brak SDK trackera gdziekolwiek w kodzie, a użytkownik nie wspomniał o objawie), zadaj użytkownikowi jedno pytanie o to, co widzi na produkcji, zanim przejdziesz dalej. Nie zgaduj.

Umieść model przechwytywania w raporcie. Podagenci także go potrzebują, aby każdy z nich nie odkrywał go ponownie.

### Krok 2 — Wybierz obszary (przepływy, które mają znaczenie)

Wybierz **2–4 krytyczne przepływy użytkownika**, każdy audytowany pełnostosowo (UI → API → usługi → dane/wywołania zewnętrzne → praca w tle). Rozstrzygaj je w tej kolejności:

1. **Argumenty:** użyj ich zgodnie z podaniem.
2. **Dokumenty bazowe:** przeczytaj trzy istniejące pliki. Wybierz przepływy, których awaria zaszkodziłaby najbardziej: główną pętlę wartości (to, po co użytkownicy przychodzą), tożsamość/dostęp (logowanie, rejestracja, uprawnienia), pieniądze lub nieodwracalne zapisy (płatności, publikowanie, importy, usuwanie danych) oraz wszystko, co roadmapa oznacza jako w toku lub niedawno dostarczone (nowy kod, najsłabiej przetestowany bojowo). Przedstaw wybór z jednoliniowym uzasadnieniem każdego i pozwól użytkownikowi go dostosować. Zapytaj użytkownika: „Czy chcesz przeprowadzić audyt tych rekomendowanych obszarów, czy je dostosować?”
3. **Brak dokumentów bazowych:** Zapytaj użytkownika: „Które 2–3 obszary powinny zostać przejrzane pełnostosowo?” Zaoferuj 3–4 konkretne kandydatury wywnioskowane ze struktury tras/stron/modułów, aby nie odpowiadał w ciemno.

**Rotacja przy ponownych uruchomieniach.** Jeśli istnieją wcześniejsze raporty, preferuj przepływy, których nie obejmowały lub które obejmowały przy starszym commicie, i powiedz o tym („login i CMS zostały poddane audytowi 2026-09-24; to uruchomienie proponuje checkout i notifications”). Użytkownik nadal może wybrać ponowny audyt tych samych obszarów; raport rejestruje wtedy, jak zmieniło się każde wcześniejsze ustalenie.

### Krok 3 — Rozdziel audyty (równoległe podagenty)

Uruchom w jednej wiadomości, aby działały jednocześnie:

- **Jeden audytor na obszar** (tylko do odczytu).
- **Jeden audytor infrastruktury pomocniczej** (tylko do odczytu). Obejmuje przekrojowy _kod_, którego nie posiada żaden obszar: kod inicjalizacji trackera, granice i kolejność middleware, serializację błędów loggera, hooki czyszczące, tagowanie wydań w kodzie, punkty wejścia zadań w tle/workerów, globalne handlery po stronie klienta oraz przeszukanie całego repozytorium z licznikami. Nie audytuje ustawień panelu ani platformy.

Użyj briefów z `references/auditor-briefs.md`. Wklej model przechwytywania z Kroku 1 do każdego briefu, wraz z objawem użytkownika (jeśli występuje) i znanymi problemami z wcześniejszych raportów lub dokumentów triage. Sklasyfikuj każde ustalenie zgodnie z taksonomią i skalą ważności z `references/gap-taxonomy.md`, aby wyniki obszarów można było czysto połączyć.

Gdy działają, przygotuj Krok 4, jeśli ma zastosowanie.

### Krok 4 — Dowód runtime (opcjonalny, odizolowany)

Statyczne czytanie mówi „to _powinno_ być niewidoczne”. Sonda runtime to pokazuje. Zaproponuj ten krok, gdy audyt znalazł krytyczne luki w pokryciu, a aplikacja może uruchomić się lokalnie. Uruchom go, gdy użytkownik przekazał `--runtime` lub wyraził zgodę.

Postępuj zgodnie z `references/runtime-probes.md`. Najważniejsze elementy:

- Pracuj wyłącznie w **odizolowanej kopii**: git worktree albo tymczasowym klonie. Nigdy nie dotykaj głównego drzewa, nigdy nie commituj, nigdy nie pushuj, nigdy nie wdrażaj.
- Skieruj tracker błędów na **lokalny fałszywy endpoint ingest** (`scripts/fake-ingest.mjs`) zamiast prawdziwej usługi. Nigdy nie wysyłaj zdarzeń sondy do produkcyjnego trackera i nigdy nie używaj produkcyjnych baz danych ani kont zewnętrznych.
- Wstrzyknij stały katalog kształtów awarii (rzucone w handlerze, rzucone we wczesnym middleware, błąd zwrócony jako 5xx bez rzucania, zignorowany wynik błędu, nieobsłucone odrzucenie, awaria zadania w tle, obiekt błędu przekazany loggerowi…) z wyzwalaczem sondy (np. `?probe=<id>`). Zapisz wynik HTTP / wyjście konsoli platformy / co dotarło do fałszywego trackera.
- Zautomatyzuj uruchomienie (skrypt `suite`), aby można było je identycznie powtórzyć. Zachowanie harnessu umożliwia później dowód przed/po.

Jeśli aplikacja nie może się uruchomić (brakująca infrastruktura, sekrety, płatne usługi), zgłoś dokładną przeszkodę. Oznacz dotknięte ustalenia jako _static-only_; nigdy nie zgaduj wyników runtime.

### Krok 5 — Zweryfikuj, następnie zsyntetyzuj

Podagenci zgłaszają zbyt wiele. Przed raportem:

- **Sprawdź wyrywkowo** samodzielnie 3–5 najbardziej zaskakujących lub najpoważniejszych twierdzeń (przeczytaj cytowane wiersze, uruchom regex, sprawdź źródło SDK w katalogu zależności). Odrzuć lub obniż rangę wszystkiego, co się nie potwierdza, i zaznacz w raporcie, że to zweryfikowałeś.
- **Usuń duplikaty** między obszarami. Kilka ustaleń obszarowych to często jeden mechanizm: „12 tras nie wywołuje reportera” to _jedna_ luka w pokryciu z 12 lokalizacjami, a nie 12 ustaleń.
- **Odrzuć ustalenia dotyczące warunków wstępnych.** „Logowanie nie jest włączone w konfiguracji wdrożenia”, „brak przekazywania logów”, „brak reguł alertów w repozytorium” lub „brak klucza trackera w przykładowym pliku env” nie są ustaleniami, gdy ustawienie może znajdować się poza repozytorium. Przenieś je na listę _Założenia_ raportu. Zachowaj element konfiguracji tylko wtedy, gdy kod, który możesz zacytować, aktywnie pogarsza zdarzenia (hook czyszczący, który porzuca stack traces, próbkowanie błędów poniżej 100%, lista ignorowania pasująca do błędów first-party).
- **Nazwij systemowe przyczyny źródłowe** (zwykle 3–6). To najcenniejsza część raportu, ponieważ naprawa jednej przyczyny źródłowej zamyka wiele ustaleń. Każda przyczyna źródłowa musi być mechanizmem kodu z dowodem plik:wiersz: miejscem, w którym błąd jest przechwytywany, konwertowany, pozbawiany danych lub wykonywany poza granicą. „Monitoring nie jest skonfigurowany” nigdy nie jest przyczyną źródłową. Nie da się tego zweryfikować z repozytorium, a gdyby to było prawdą, ukrywałoby każdą lukę na poziomie kodu za jedną naprawą, która nie pomaga.
- **Uporządkuj poprawki** według usuniętej ślepoty na jednostkę wysiłku. Poprawki kodu o szerokim pokryciu (jedna globalna granica, serializacja loggera, zakres czyszczenia, współdzielony helper error-to-response zachowujący przyczynę) zwykle poprzedzają lokalne.

### Krok 6 — Napisz raport (nowy plik przy każdym uruchomieniu)

Napisz raport, używając `references/report-template.md`, do:

```
<project-root>/context/audits/observability/<YYYY-MM-DD>_<slug>.md
```

- `<project-root>` to katalog główny audytowanego projektu (`git rev-parse --show-toplevel` albo cwd poza git), a nie katalog umiejętności.
- `<slug>` to audytowane obszary w kebab-case, połączone przez `-` (np. `login-checkout`), albo `verify-<areas>` w trybie weryfikacji.
- Utwórz katalog, jeśli jest potrzebny.
- **Nadpisanie przez użytkownika:** jeśli użytkownik przekazał `--out` lub wskazał inną lokalizację, użyj jej. Katalog otrzymuje tę samą nazwę pliku `<YYYY-MM-DD>_<slug>.md`; ścieżka kończąca się na `.md` jest używana bez zmian. W każdym innym przypadku użyj domyślnej wartości i nie pytaj o to.

- **Nigdy nie nadpisuj ani nie edytuj wcześniejszego raportu.** Jeśli ścieżka istnieje, dodaj `-2`, `-3`. Wcześniejsze raporty są historią, z którą porównują późniejsze uruchomienia.
- Frontmatter raportu zapisuje tożsamość uruchomienia, obszary, tryb, status dowodu runtime oraz link do poprzedniego raportu. Następne uruchomienie polega na tym frontmatter, więc zachowaj stabilność jego kluczy.
- Jeśli istnieje poprzedni raport, wypełnij **Zmiany od ostatniego audytu**: dla każdego wcześniejszego ustalenia w obszarze, który został ponownie objęty audytem, oznacz je jako `fixed`, `still open`, `changed` lub `not re-checked`, z dowodami.
- Każde ustalenie ogranicz do jego lokalizacji, kategorii, ważności, **tego, co dzieje się na produkcji, gdy wystąpi awaria**, oraz jednoliniowego kierunku naprawy. Konsekwencja produkcyjna sprawia, że ustalenie jest możliwe do wykonania, więc nigdy jej nie pomijaj.

### Krok 7 — Przekaż dalej

Powiedz użytkownikowi w kilku wierszach: ścieżkę raportu, 3 najważniejsze przyczyny źródłowe, liczbę ustaleń według ważności, co zostało potwierdzone runtime, a co tylko statycznie, oraz rekomendowaną pierwszą poprawkę. Zaproponuj kolejne kroki:

- udowodnij konkretną poprawkę za pomocą uruchomienia przed/po na tym samym zestawie sond (zobacz _Tryb weryfikacji_);
- przekształć najważniejszą poprawkę w zmianę za pomocą `/10x-new` + `/10x-plan`.

Wspomnij, że odizolowane worktree lub pliki harnessu z Kroku 4 nadal istnieją i gdzie się znajdują. Nie usuwaj ich bez pytania, ponieważ są potrzebne do dowodu przed/po.

## Tryb weryfikacji (`--verify <report>`)

Użyj tego po wdrożeniu poprawek albo aby udowodnić, że proponowana poprawka działa. Przeczytaj wskazany raport i ponownie sprawdź każde ustalenie: ponownie przeczytaj cytowany kod oraz, jeśli raport ma harness sondy, uruchom ponownie ten sam zestaw. Utwórz nowy raport z datą i `mode: verify`, którego treść stanowi głównie **Zmiany od ostatniego audytu** oraz tabela przed/po. Ten sam katalog sond przed i po zmienia „uważamy, że jest naprawione” w dowód.

## Zasady

- **Kod ponad konfiguracją.** Zakładaj, że logi i tracker są zbierane na produkcji. Pytanie brzmi, co przekazuje im kod. Brakujące ustawienie, którego nie widać w repozytorium, to założenie do potwierdzenia, a nie ustalenie.
- **Najpierw pokrycie, potem wierność, potem szum.** Awaria, której tracker nigdy nie widzi, ma większe znaczenie niż taka, którą widzi bez stack trace, a ta ma większe znaczenie niż taka, którą widzi zbyt często.
- **Oceniaj według tego, co otrzyma osoba reagująca.** Dla każdej luki zapytaj, co inżynier on-call zobaczy o 3 nad ranem: alert? zgłoszenie ze stackiem oraz użytkownikiem/trasą/encją? linię logu, której musiałby już wiedzieć, aby jej szukać? nic?
- **Łagodne degradowanie wymaga własnego sygnału.** Fallbacki, które nie blokują użytkowników, są dobre. Fallbacki, które jednocześnie usuwają jedyny znak awarii, są ustaleniami.
- **Prywatność jest ograniczeniem, a nie wymówką.** Rekomenduj poprawki, które zachowują działanie czyszczenia (hash lub id zamiast email, zachowaj nazwy/kody błędów i stack traces, odrzuć tylko wartości). Nigdy nie rekomenduj wysyłania PII.
- **Sformułowania niezależne od stosu.** Opisuj mechanizmy („trasa rezygnuje z reporting wrapper”), a następnie konkretne lokalne API. Taksonomia działa dla każdego języka i frameworka.
