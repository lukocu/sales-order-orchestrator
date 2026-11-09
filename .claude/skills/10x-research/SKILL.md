---
name: 10x-research
description: Investigate codebase questions with source-backed findings, scoped research and parallel sub-agents. Save research for implementation planning.
---

# Badanie bazy kodu

Odpowiedz na pytanie badawcze użytkownika, korzystając z aktualnych ustaleń popartych źródłami. Zachowaj implementację, decyzje produktowe i zmiany cyklu życia poza zakresem badania, chyba że zostaną osobno zażądane.

## Zacznij od dostarczonego żądania

Jeśli dostarczono pytanie, change-id lub plik, zacznij od tego kontekstu; nie pytaj ponownie o to samo żądanie. Dla `/10x-research <change-id>` użyj artefaktów request/change/frame aktywnej zmiany, aby ustalić pytanie. Poproś o brakujące pytanie tylko wtedy, gdy ani wiadomość, ani te artefakty go nie definiują.

Rozwiąż aktywną zmianę przed jakimikolwiek zapisami. Jawnie zarchiwizowana zmiana jest tylko do odczytu: wyjaśnij, że potrzebna jest nowa zmiana, i zakończ przed zapisem w niej. Jeśli nie podano change-id, wyprowadź go z tematu podczas zapisywania dokumentu.

## 1. Ustal dowody i zakres

- Jeśli użytkownik wspomina konkretne pliki (tickety, dokumenty, JSON), przeczytaj je najpierw W CAŁOŚCI (bez limitu/offsetu)
- **KRYTYCZNE**: Przeczytaj te pliki samodzielnie w głównym kontekście przed uruchomieniem jakichkolwiek podzadań

Przeczytaj `context/foundation/lessons.md`, jeśli istnieje, i traktuj jego wpisy jako uprzednio znane wzorce podczas kształtowania obszarów badawczych — powtarzające się reguły już zaakceptowane przez zespół zawężają to, co warto ponownie badać.

Prowadź zwięzłą listę pytań wymagających odpowiedzi, istniejących dowodów, nierozwiązanych sprzeczności i kolejnych kontroli. Skoncentrowane pytanie może wymagać jednego lokalnego wyszukania; kompleksowy zakres domyślnie wymaga pokrycia każdego uzgodnionego obszaru, delegowanego równolegle (krok 2).

Doprecyzuj tylko niejednoznaczność, która istotnie zmieniłaby badanie. Gdy jest dostępna, użyj rzeczywistej możliwości zadawania pytań strukturyzowanych przez hosta, przestrzegając jej schematu, wielkości rundy i niestandardowych danych wejściowych. Używaj krótkich nagłówków (maksymalnie 12 znaków) oraz konkretnych opcji z opisami. W hoście bez tej możliwości zadaj użytkownikowi zwięzłe pytanie tekstowe w celu wymaganego doprecyzowania zakresu; nie symuluj wywołania narzędzia. Jednoznaczne żądanie badawcze nie wymaga wywiadu ani zmiany trybu. Preferencje użytkownika są decyzjami; zweryfikuj skorygowane twierdzenia faktyczne względem wskazanego źródła.

## 2. Wybierz i przeprowadź badanie

Pracuj lokalnie dla pojedynczego zlokalizowanego faktu lub rozumowania sekwencyjnego. Kompleksowe badanie lub badanie wielu obszarów jest domyślnie delegowane, a nie traktowane jako wyjątek. Przed pierwszym delegowaniem przeczytaj [references/task-orchestration.md](references/task-orchestration.md) i użyj opisanych tam ograniczonych przydziałów, kontroli dostępnych modeli/możliwości, procedury awaryjnej na wypadek niepowodzenia oraz wymagań dotyczących dowodów. Uruchom 2–4 pracowników równolegle w jednej wiadomości, każdego dla innego wymiaru badania i każdego z prośbą o kotwice `file:line` — na przykład jednego znajdującego każdy plik związany z X, jednego szukającego wcześniejszych decyzji dotyczących Y w `context/changes/**/` i `context/archive/**/`, jednego analizującego działanie podsystemu Z. Deleguj mniej tylko wtedy, gdy zakres rzeczywiście dotyczy jednego obszaru albo gdy luka zależy od warunku wstępnego, który nadal jest nierozstrzygnięty. Używaj natywnej możliwości sub-agentów lub zadań swojego AI coding assistant do lokalizowania kodu i analizy, wybierając odpowiedni dostępny typ agenta. Używaj śledzenia zadań, gdy pomaga ono koordynować kilka obszarów i host je udostępnia; w przeciwnym razie wystarczy lista robocza.

Główny agent odpowiada za pytanie i syntezę. Agenci podrzędni badają tylko do odczytu i zwracają kotwice, niepewność oraz rzeczywisty zakres pokrycia. Nie proś każdego pracownika o przeczytanie całego repozytorium ani tych samych dużych dokumentów. Kontynuuj niezależną pracę podczas ich działania; sprawdzaj istotne dowody w miarę napływania wyników. Poczekaj na ukończenie WSZYSTKICH oddelegowanych pracowników przed syntezą — częściowe przeszukanie jest wskazaną luką, a nie odpowiedzią.

Przy kontynuacji lub korekcie zakresu zaktualizuj pytania i pracowników, których to dotyczy, zachowując niepowiązane ustalenia. Późna odpowiedź oparta na zastąpionym zakresie nie może nadpisać nowej decyzji. Zajmij się konkretną luką zamiast ponownie rozpoczynać szerokie odkrywanie.

## 3. Dokonaj syntezy i zamknij odkrywanie

Połącz dowody w odpowiedź na pierwotne pytanie. Rozróżniaj zaobserwowane zachowanie, wnioskowanie i nierozstrzygnięte fakty. Sprawdź decydujące/sprzeczne ścieżki kodu i wywołujących; sam brak wyników wyszukiwania nie dowodzi nieobecności. Przy negatywnym ustaleniu cytuj sprawdzony zakres. Poszerzaj zakres tylko wtedy, gdy może to rozstrzygnąć uzgodnione pytanie lub istotną sprzeczność, a nie po to, aby wypełnić opcjonalną sekcję dokumentu.

Gdy żądane są rekomendacje, zachowaj ustalone wymagania i odrzuć opcje osłabiające wymagane gwarancje. Rozróżniaj rozstrzygnięte decyzje, rzeczywiste wybory i brakujące dowody.

Zakończ, gdy uzgodnione pytania mają wystarczające dowody, a istotne konflikty są rozwiązane. Zamknij lub anuluj przestarzałe zadania. Nadal brakujące wymagane dowody oznaczają częściowe ustalenie z podaną luką i jej wpływem; nie deklaruj ukończenia ani nie uruchamiaj bez końca równoważnych wyszukiwań. Nie uruchamiaj buildów ani testów, chyba że ich wyniki odpowiadają na konkretne pytanie badawcze i host na to pozwala.

## 4. Zapisz i zweryfikuj artefakt badawczy

Gdy zapisy do repozytorium są dozwolone, zapisz `context/changes/<change-id>/research.md`, zachowując istniejący materiał i edycje użytkownika. Utwórz aktywny folder i `change.md` tylko, jeśli ich brakuje, zgodnie z semantyką `/10x-new`. Nigdy nie nadpisuj innej zmiany ani nie zapisuj w `context/archive/`. Na tym etapie przeczytaj [references/research-document.md](references/research-document.md), aby poznać format wyjściowy; nie ładuj go wyłącznie na potrzeby odkrywania źródeł.

Przed zapisaniem `research.md` zastosuj kontrole ograniczonych twierdzeń oraz prozy/JSON z tego odwołania. Każde ilościowe lub uniwersalne twierdzenie w prozie wymaga jawnego warunku, kwantyfikatora (dokładnego zbioru, liczby lub „this inspected path”) oraz kotwicy źródłowej. Nie pisz „always”, „never”, „every”, „only” ani „on the first attempt”, chyba że nazwany warunek i sprawdzona ścieżka faktycznie mają taki zakres. Rozstrzygaj każde twierdzenie historyczne osobno: dokument nieaktualny pod względem liczebności może nadal być poprawny w innym polu; pozytywna lista nie jest zbiorem wyłącznym, chyba że źródło tak mówi.

Gdy zażądano pliku ustrukturyzowanych faktów (JSON lub tabeli), przed utrwaleniem któregokolwiek pliku wykonaj osobne przejście proza-kontra-JSON: dla każdego liścia zapisz zdanie prozą, które ta wartość oznaczałaby, gdyby była prawdziwa, potwierdź, że to samo zdanie znajduje się w `research.md`, i potwierdź, że wartość JSON odpowiada temu samemu źródłu. Zgodność JSON nie certyfikuje otaczającej prozy. Uruchom dołączony kontroler Node jeden raz:

```sh
node <loaded-skill-dir>/scripts/prose-json-check.mjs <research.md> <facts.json>
```

Sprawdza on wyłącznie, czy każda liczba i wartość logiczna JSON występuje w prozie; nie dowodzi poprawności kwantyfikatorów. Brakujące liście lub dodatkowe uniwersalne sformułowania nadal wymagają ręcznej korekty. Jeśli Node jest niedostępny, wykonaj tę samą listę kontrolną ręcznie.

Zbierz metadane z rzeczywistego repozytorium i aktualnego zegara jeden raz; nie twórz fikcyjnej gałęzi, commitu, znacznika czasu ani tożsamości badacza. Zapisuj metadane change.md **wyłącznie** przez dołączony [scripts/metadata-guard.mjs](scripts/metadata-guard.mjs) z użyciem Node — nigdy nie przepisuj istniejącego YAML z szablonu ani nie usuwaj pól tożsamości:

```sh
node <loaded-skill-dir>/scripts/metadata-guard.mjs inspect <change-dir>
node <loaded-skill-dir>/scripts/metadata-guard.mjs mark-researched <change-dir> --expected-sha256 <inspected-change-sha256> --date <YYYY-MM-DD>
```

`mark-researched` przesuwa wyłącznie `new` do `preparing`, ustawia `updated` na dzisiaj, dodaje brakujące posiadane pola i zachowuje `change_id`, `title`, `created`, niepowiązany YAML, treść oraz późniejsze stany cyklu życia. Wymaga zapisanego `research.md`. Nieaktualny fingerprint wymaga ponownego odczytania zmienionych metadanych. Jeśli Node jest niedostępny lub składnia nie jest obsługiwana, sprawdź plik i dokonaj tylko tej samej wąskiej edycji statusu/dat; nigdy nie zastępuj frontmatter. Pomocnik używa optymistycznych fingerprintów i atomowego zastąpienia, a nie transakcji z zewnętrznymi edytorami. Dokument badawczy może być kompletny lub częściowy niezależnie od cyklu życia zmiany.

Przejrzyj końcowy artefakt raz, aby sprawdzić jego odpowiedź, cytowania, luki i metadane: odczytaj zapisane treści ponownie albo przejrzyj kompletny szkic podczas prezentowania go niezapisanego w rozmowie. W tym samym przejściu ponownie wykonaj listę kontrolną ograniczonych twierdzeń i prozy/JSON (nie pomijaj jej, ponieważ pierwszy szkic już istniał):

- Powiąż przykład liczbowy z jego nazwanymi danymi wejściowymi, jednostkami i warunkami przed wyprowadzeniem jego wyniku; rozróżniaj sumy od dodatkowych operacji. Nie wyciągaj znaczenia wartości wyłącznie z nazwy pola lub znanej liczby.
- Dla każdej istotnej wartości logicznej sformułuj twierdzenie, które oznaczałaby, gdyby była prawdziwa, a następnie sprawdź, czy sprawdzone źródło wspiera to twierdzenie przed przypisaniem wartości. Pole opisujące, czy twierdzenie historyczne jest poparte, odpowiada na pytanie o to poparcie, a nie na pytanie, czy dokument historyczny zawiera twierdzenie.
- Koryguj twierdzenia historyczne indywidualnie. Niektóre twierdzenia w nieaktualnym dokumencie mogą nadal być prawdziwe: dołącz bieżący werdykt do każdego istotnego twierdzenia historycznego zamiast oznaczać cały akapit jako nieaktualny. Prześledź istotnych konsumentów, zanim nazwiesz współdzieloną regułę wyłączną dla jednego komponentu. Preferuj dokładnie zaobserwowany zbiór lub predykat zamiast szerszych sformułowań, takich jak „all errors” lub „every status in a class”.

Ponownie użyj kotwic źródłowych i obliczeń już zweryfikowanych. Niezgodność uruchamia wyłącznie sprawdzenie i korektę dotkniętego źródła/wywołującego w każdym wyniku, a nie nowe przejście odkrywania. Jeśli pozostaje nierozstrzygnięta, zakwalifikuj twierdzenie i konsekwentnie wskaż lukę. Ta kontrola domyślnie nie wymaga dodatkowego artefaktu, pracownika ani uruchomienia testów.
Używaj zwięzłego wyjścia walidacji zamiast wielokrotnie je wypisywać. Uruchom wszystkie mające zastosowanie kontrole dokumentów repozytorium jeden raz. Dodaj permalinki commitów tylko wtedy, gdy cytowane bajty odpowiadają temu commitowi, a zdalne repozytorium na pewno go zawiera; lokalne niezatwierdzone dowody zachowują lokalne odwołania file:line. Nie twórz permalinku na podstawie nazwy gałęzi.

Jeśli host zabrania zapisów, przedstaw badanie i jawny status niezapisania w rozmowie. Nie twórz pliku zastępczego ani nie deleguj zapisu. Wznów zapisywanie w trybie z możliwością zapisu w tej samej rozmowie po sprawdzeniu bieżących plików docelowych i dostępnego kontekstu; nie rozpoczynaj ponownie rozstrzygniętego badania ani nie obiecuj odzyskania brakującej zawartości rozmowy.

## 5. Przedstaw ustalenia i obsłuż kontynuacje

Zacznij od odpowiedzi, lokalizacji artefaktu lub stanu niezapisania, decydujących referencji oraz istotnych ograniczeń. Badanie nie oznacza zatwierdzenia planu ani implementacji. Przy przekazaniu do planowania ujawnij rozstrzygnięte fakty, ich źródła, objęte kontrakty oraz nierozwiązane wybory produktowe, aby `/10x-plan` mógł na nich budować bez ponownego odkrywania.

Dodaj ustalenia z kontynuacji do tego samego dokumentu badawczego, zaktualizuj `last_updated`, `last_updated_by` i `last_updated_note` oraz wskaż wnioski zastąpione przez nowe dowody. Ponownie użyj niezmienionych wyników; zbadaj wyłącznie nowe lub unieważnione pytania. Zachowaj zakres, uprawnienia hosta oraz wszelkie pośrednie edycje dokonane przez ludzi.
