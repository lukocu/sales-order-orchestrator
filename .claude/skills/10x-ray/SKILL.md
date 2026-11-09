---
name: 10x-ray
description: >
  Learn how a skill works by watching it run. Maps the target skill's anatomy
  (steps, loops, fan-outs, human gates, branches, and why each exists), runs
  the skill in a background subagent, and reveals the map concept by concept
  as the run reaches each step, ending with a full "skill anatomy". The
  skill's own questions are handed to the user exactly as the skill would ask
  them. Use when the user invokes /10x-ray <skill> [args], or asks to
  "x-ray", "watch", "trace", "visualize" or "understand" a skill by running
  it. `--mode html` shows the same view on a live page in the browser instead
  of the terminal.
---

# 10x-ray

Jesteś obserwatorem i interpretatorem. Czytasz docelową umiejętność i mapujesz
jej anatomię, działający w tle podagent (worker) uruchamia ją i oznacza każde zdarzenie
krokiem mapy, w którym się znajduje, a proces monitorujący zamienia to na ramki
na poziomie koncepcji: „umiejętność teraz rozdziela zadania między podagentów i oto dlaczego”.
Użytkownik powinien zyskać zrozumienie projektu umiejętności, a nie tylko obserwować
przewijające się wywołania narzędzi. Pośredniczysz też w każdym pytaniu, które
umiejętność kieruje do człowieka.

Skrypt: `XRAY=<this skill's base directory>/scripts/xray.mjs`. Harness
wypisuje katalog bazowy podczas ładowania umiejętności (`Base directory for this
skill: …`); umiejętność może znajdować się w `the AI tool's configuration directory/skills/` projektu lub w
`~/.claude/skills/`, dlatego nigdy nie wyprowadzaj go z bieżącego repozytorium. Używaj
wszędzie ścieżki bezwzględnej; worker również jej potrzebuje. Wymaga Node 18+.

## 1. Przeanalizuj wywołanie

- Wiodące `--mode <terminal|html>` (lub `--mode=<…>`) wybiera miejsce wyświetlania
  widoku; domyślnie `terminal`. Liczy się tylko flaga trybu _przed_ nazwą umiejętności;
  wszystko po nazwie umiejętności należy do umiejętności.
- Następny token = docelowa nazwa umiejętności (usuń wiodące `/`). Wszystko po nim
  = `ARGS` dla tej umiejętności, przekazane dosłownie.
- Nie podano umiejętności: wypisz kilka umiejętności z listy dostępnych umiejętności i zapytaj,
  którą uruchomić. Na tym zakończ.
- Cel musi znajdować się na liście dostępnych umiejętności. Jeśli go tam nie ma, powiedz o tym i
  zasugeruj najbliższe nazwy. Odmów użycia samego `10x-ray` jako celu.
- `LANG` = język, w którym użytkownik pisze do Ciebie w tej rozmowie: `pl`
  dla polskiego, `en` dla każdego innego. Ustawia każdą etykietę widzianą przez użytkownika, język,
  w którym piszesz mapę, oraz narrację workera.

## 2. Zmapuj umiejętność

Przeczytaj `references/mapping-guide.md` (schemat, wzorce, jak pisać koncepcje)
oraz, po raz pierwszy w sesji, `references/example-map-10x-research.json`.
Następnie przeczytaj SKILL.md docelowej umiejętności (`the AI tool's configuration directory/skills/<skill>/` lub
`~/.claude/skills/<skill>/`) oraz pliki, których nakazuje przestrzegać w ramach swojego
przepływu pracy. Zapisz mapę do pliku roboczego i ją zarejestruj:

```bash
LOG=$(node "$XRAY" init <skill> "<ARGS>" --lang <LANG>)
node "$XRAY" map "$LOG" <map.json>      # validates; fix and rerun on error
node "$XRAY" emit "$LOG" start - "Worker launched: /<skill> <ARGS>"
```

Zachowaj mapę dla siebie. Nie wypisuj jej ani nie opisuj kroków umiejętności na
czacie: użytkownik odkrywa je pojedynczo, gdy uruchomienie do nich dotrze.

## 3. Uruchom widoki

**tylko tryb html:** uruchom serwer strony w tle:
`node "<XRAY>" serve "<LOG>"`. Odczytaj jego wyjście
w poszukiwaniu linii `x-ray page: http://127.0.0.1:<port>/` (pojawia się w ciągu
sekundy), a następnie otwórz `<url>`. Strona (`assets/xray.html`) pokazuje jedną kartę
na ujawniony krok, z jego koncepcją, bieżącą linią „teraz”, notatkami i
zwiniętym śladem agentów; ścieżki rozgałęzienia zagnieżdżają się w niej. Po zakończeniu uruchomienia
serwer zapisuje samodzielny migawkę obok logu (`<LOG>.html`).

Uruchom proces monitorujący:

- `command`: `node "<XRAY>" watch "<LOG>"` w trybie terminala,
  `node "<XRAY>" watch "<LOG>" --quiet` w trybie html (ścieżki bezwzględne,
  już rozwinięte). Cichy monitoring wybudza Cię tylko dla pytań i końca
  uruchomienia. Dodaj `--verbose` tylko wtedy, gdy użytkownik poprosi o zobaczenie każdej akcji agenta.
- `description`: `x-ray of /<skill>`
- `timeout_ms`: `1800000`

`watch` pamięta, co już wyrenderował, więc ponowne uzbrojenie nigdy nie powtarza
ramki.

## 4. Uruchom workera

Przeczytaj `references/worker-brief.md`, weź wszystko poniżej jego linii `---` i
wypełnij `{{SKILL}}`, `{{ARGS}}`, `{{LANG}}`, `{{XRAY}}`, `{{LOG}}` oraz `{{NODES}}`. Dla
`{{NODES}}` użyj jednej linii na węzeł mapy, `<id>  <pattern>  <title>`, z
dziećmi wciętymi o dwie spacje pod rodzicem. Uruchom go jako działającego w tle
podagenta ogólnego przeznaczenia z opisem `x-ray: /<skill>`. Zanotuj jego ID agenta,
aby móc wysyłać mu wiadomości.

Powiedz użytkownikowi w jednej linii, że x-ray jest uruchomiony (tryb html: wraz z adresem URL
strony), a następnie zakończ swoją turę.

## 5. Pętla przekazywania

**tryb terminala**, przy każdym powiadomieniu monitoringu:

- Pierwsza linia jest linią statusu `x-ray tick …`, którą host już
  pokazuje w swoim wierszu powiadomień. Pomiń ją i wypisz resztę dosłownie wewnątrz
  ogrodzenia ` ```text `. Powiadomienia przychodzą z encjami HTML: zamień `&amp;`
  `&lt;` `&gt;` z powrotem na `&` `<` `>`. Nie zmieniaj niczego więcej. Ramki
  zawierają materiał dydaktyczny (koncepcja na krok, notatki o rezultatach), więc dodaj co najwyżej
  jedną krótką linię pod ogrodzeniem, tylko gdy ramka wymaga kontekstu, na który użytkownik
  może zareagować (np. `WARNING`). Nie przewiduj nadchodzących kroków.
- Monitoring wygasł i nie ma jeszcze ramki anatomii: ponownie uzbrój to samo polecenie.

**tryb html:** nie wypisuj ramek. Ciche ticki przychodzą tylko dla pytań
(obsłuż je jak poniżej) oraz dla końca uruchomienia (wypisz ramkę anatomii
w ogrodzeniu, a następnie wynik).

### Przekazywanie kontroli użytkownikowi

Gdy umiejętność o coś pyta, użytkownik otrzymuje dokładnie tę samą interakcję, którą
by wyświetliła. Działaj na podstawie **zdarzenia monitoringu**, a nie zakończenia workera.
Gdy linia ticka kończy się na `· ask=<payload file>`:

1. Przekaż ramki jak zwykle (tryb terminala).
2. Odczytaj plik payload i dokładnie naśladuj dziecko:
   - `"mode":"choice"`: Zadaj użytkownikowi tablicę `questions`
     payloadu bez zmian: to samo sformułowanie, nagłówki, opcje, opisy,
     `multiSelect`. Nie parafrazuj, nie łącz ani nie skracaj niczego.
   - `"mode":"text"`: wypisz `prompt` payloadu dosłownie jako swoją wiadomość,
     poza ogrodzeniem, i zakończ swoją turę. Następna wiadomość użytkownika jest
     odpowiedzią.
3. Zapisz odpowiedź w śladzie:
   `node "$XRAY" answer "$LOG" "<short form, e.g. Depth: Quick overview · Focus: Identity & sessions>"`.
4. Wyślij ją workerowi przy użyciu jego ID agenta: dla wyborów,
   `User answer:` następnie po jednej linii na pytanie, `<header>: <chosen labels>`,
   wraz z dowolnym wolnym tekstem wpisanym w Other lub w notatkach; dla trybu tekstowego
   odpowiedź dosłownie. Jeśli zakończenie workera `NEEDS_INPUT` jeszcze nie nadeszło,
   najpierw na nie zaczekaj, aby wiadomość wznowiła workera zamiast
   trafić w środek tury.
5. Ponownie uzbrój proces monitorujący, jeśli w międzyczasie się zatrzymał.

Jeśli zapytanie użytkownika zostanie odrzucone lub użytkownik odpowie poza opcjami, przekaż
jego słowa jako odpowiedź. Nie pytaj ponownie. Nie wypisuj wiadomości zakończenia workera
`NEEDS_INPUT`; nie wnosi niczego poza payloadem.

### Koniec uruchomienia

Przy końcowym powiadomieniu o zakończeniu workera (nie `NEEDS_INPUT`):

- Jeśli log nie zawiera zdarzenia `done`/`fail` (worker uległ awarii lub zapomniał), wyemituj je
  za niego, aby anatomia się wyrenderowała:
  `node "$XRAY" emit "$LOG" fail - "Worker ended without a final event" "<one-line reason>"`
  (`done` zamiast tego, jeśli worker wyraźnie zakończył się sukcesem).
- Przekaż ramkę anatomii z procesu monitorującego. Zawiera każdy zmapowany krok,
  odwiedzony lub nie, więc jest to moment, w którym widoczny jest cały projekt.
- tryb html: zatrzymaj serwer strony, gdy jego wyjście pokaże linię
  `x-ray snapshot:`, i podaj użytkownikowi ścieżkę do migawki.
- Podaj rzeczywisty wynik umiejętności z końcowej wiadomości workera: utworzone
  pliki wraz ze ścieżkami, kluczowe ustalenia lub decyzje, otwarte dalsze kroki. Następnie, w
  2–4 zdaniach, podaj wniosek dotyczący projektu umiejętności: jedną lub dwie idee,
  które sprawiają, że działa (np. „tanie pytanie o zakres przed kosztownym
  rozgałęzieniem”). To jest sens x-ray.

## 6. Wczesne zatrzymanie

Jeśli użytkownik prosi o zatrzymanie, zatrzymaj workera, a następnie wyemituj `fail`
z tytułem `Stopped by user` (oznaczonym bieżącym krokiem). Proces monitorujący
sam wyrenderuje anatomię i zakończy działanie (najpierw uzbrój go ponownie, jeśli
wygasł). Przekaż ją i zgłoś, co worker zdążył już zmienić na dysku.
