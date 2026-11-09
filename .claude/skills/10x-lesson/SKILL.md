---
name: 10x-lesson
description: Capture a recurring rule or pattern into context/foundation/lessons.md. Use when you spot a class of bug or design pitfall worth surfacing for future reviews and implementations.
---

# /10x-lesson — Uchwyć powtarzalną regułę

Dodaj pojedynczy wpis do `context/foundation/lessons.md`, aby przyszłe uruchomienia `/10x-frame`, `/10x-research`, `/10x-plan`, `/10x-plan-review`, `/10x-implement` i `/10x-impl-review` ponownie odczytały go jako wcześniejszą wskazówkę. Jest to proaktywny odpowiednik opcji triage „Accept as recurring rule” w `/10x-impl-review` — wywołaj ją inline, gdy zauważysz wzorzec wart uwidocznienia, bez czekania na ustrukturyzowany przegląd.

„Lekcja” jest powtarzalną regułą — a nie jednorazową poprawką błędu. Kryterium brzmi: „to zmieniłoby sposób ujęcia problemu lub poprawkę w przeszłej pracy i będzie nadal się pojawiać”. Jeśli to opis pojedynczego incydentu, jest to niewłaściwy skill.

## Początkowa odpowiedź

Gdy ten skill zostanie wywołany:

1. **Jeśli opis swobodny został podany inline** (np. `/10x-lesson feature flags should always have a kill date`), użyj go jako zalążka pola Rule i przejdź do wywiadu.
2. **Jeśli nic nie zostało podane**, odpowiedz:

```
Zapiszę powtarzalną regułę w context/foundation/lessons.md.

Zadam cztery krótkie pytania, a następnie dodam wpis. Cztery pola to:
  1. Context — gdzie obowiązuje ta reguła (podsystem / faza / wzorzec plików)
  2. Problem — co idzie nie tak bez tej reguły
  3. Rule — sama reguła, w jednym lub dwóch zdaniach
  4. Applies to — które skille powinny najsilniej uwzględniać tę regułę (frame / plan / implement / review)

Następnie czekaj.
```

## Proces

### Krok 1: Wywiad

Poproś użytkownika o podanie czterech pól. Możesz zgrupować je w jednej rundzie czterech swobodnych promptów albo przeprowadzić cztery kolejne rundy. Obie formy są poprawne; celem jest to, aby sformułowania napisał użytkownik, a nie skill.

Nie wypełniaj wstępnie żadnych pól. Użytkownik podaje każde pole. Jeśli podczas wywołania przekazano swobodną intencję, pokaż ją jako sugestię obok promptu Rule — nie jako wartość domyślną.

Cztery pola wraz z jednoliniowymi wskazówkami:

- **Context** — gdzie obowiązuje ta reguła? Podsystem / faza / wzorzec plików. Bądź wystarczająco konkretny, aby przyszły skill mógł dopasować wzorzec (np. „any phase that adds a feature flag”, „research on multi-tenant systems”, nie „everywhere”).
- **Problem** — co konkretnie idzie nie tak, jeśli reguła zostanie naruszona? Przytocz wcześniejszy incydent lub powtarzalny schemat awarii. Jedno lub dwa zdania.
- **Rule** — sama reguła, w trybie rozkazującym („Always …”, „Never …”, „Before X, do Y”). Jedno lub dwa zdania. Osoba czytająca przyszły przegląd powinna móc wkleić to dosłownie do ustalenia.
- **Applies to** — rozdzielona przecinkami lista nazw skilli, dla których ta reguła powinna mieć największą wagę: `frame`, `research`, `plan`, `plan-review`, `implement`, `impl-review`. Użyj `all`, jeśli reguła obejmuje cały cykl życia.

### Krok 2: Powtórz i potwierdź

Wyrenderuj proponowany wpis jako blok markdown i pokaż go użytkownikowi. Zapytaj użytkownika:

- question: "Dodać tę lekcję do `context/foundation/lessons.md`?"
  header: "Potwierdź"
  options:
  - label: "Dodaj"
    description: "Zapisz wpis w pokazanej formie."
  - label: "Edytuj"
    description: "Pozwól mi poprawić jedno lub więcej pól przed zapisaniem."
  - label: "Anuluj"
    description: "Odrzuć — niczego nie zapisuj."
    multiSelect: false

Kształt proponowanego wpisu (jest to kanoniczny format wpisu lekcji):

```markdown
## <Rule title — short imperative phrase, derived from the Rule field>

- **Context**: <Context field>
- **Problem**: <Problem field>
- **Rule**: <Rule field>
- **Applies to**: <Applies-to field>
```

Nagłówek H2 JEST tytułem reguły. Zachowaj jego zwięzłość — lista H2 jest tym, co przyszłe skille skanują najpierw.

### Krok 3: Samodzielne utworzenie i dodanie

Jeśli `context/foundation/lessons.md` nie istnieje, utwórz go z tym kanonicznym 5-wierszowym nagłówkiem (osadzonym inline — bez osobnego pliku szablonu; ten sam nagłówek jest używany przez gałąź triage „Accept as recurring rule” w `/10x-impl-review` oraz tutaj):

```
# Lessons Learned

> Append-only register of recurring rules and patterns. Re-read at start by /10x-frame, /10x-research, /10x-plan, /10x-plan-review, /10x-implement, /10x-impl-review.

```

Jeśli plik istnieje, pozostaw go bez zmian i dodaj wpis na końcu. Nie zmieniaj kolejności, nie usuwaj duplikatów ani nie formatuj ponownie istniejących wpisów — plik jest przeznaczony wyłącznie do dopisywania.

Zmodyfikuj plik (lub utwórz go w przypadku inicjalizacji), aby zastosować zmianę. Po dodaniu wpisu odczytaj plik ponownie i potwierdź, że nowy H2 jest ostatnią sekcją.

### Krok 4: Powtórz wynik

Wypisz ścieżkę i tytuł reguły:

```
Dodano do context/foundation/lessons.md:
  ## <Rule title>
```

Zatrzymaj się. Nie przechodź do innych skilli. Użytkownik wywołał to w celu pojedynczego zapisu; uszanuj zakres.

## Uwagi

- **Tylko dopisywanie.** Nigdy nie edytuj ani nie usuwaj istniejących lekcji za pomocą tego skilla. Jeśli reguła wymaga poprawy, użytkownik otwiera plik i edytuje go bezpośrednio — to celowe utrudnienie, ponieważ przepisywanie powtarzalnych reguł bez namysłu jest trybem awarii, któremu ta konwencja zapobiega.
- **Jeden wpis na wywołanie.** Jeśli użytkownik ma wiele lekcji do zapisania, wywołuje skill wielokrotnie. Grupowanie sprzyja wpisom napisanym tylko częściowo.
- **Samodzielne utworzenie jest domyślne.** Nie mów użytkownikowi „run /10x-init first” — utwórz plik z kanonicznym nagłówkiem przy pierwszym użyciu. (`/10x-init` tworzy szkielet katalogu `/context`; ten skill obsługuje `lessons.md` kompleksowo.)
- **Nie wypełniaj wstępnie żadnych pól.** W przeciwieństwie do gałęzi triage `/10x-impl-review` (która wypełnia Context i Problem na podstawie ustalenia), ten proaktywny skill oczekuje, że użytkownik wykona pisanie. Taka jest cena zapisywania reguł poza ustrukturyzowanym przeglądem.
