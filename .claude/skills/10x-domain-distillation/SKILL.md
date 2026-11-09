---
name: 10x-domain-distillation
description: >
  Distil the business domain of an existing codebase into one map
  (context/domain/domain-distillation.md): the ubiquitous language with
  sources in the docs and in the code, subdomains classified as Core,
  Supporting or Generic, aggregate candidates and policies with their
  invariants and whether the code enforces them, the model-vs-code drift list,
  a ranking of what to fix first with a "done when" per item, owner-routed
  questions, and a compact glossary for agents (context/domain/glossary.md).
  Findings carry stable IDs and are diffed against the previous run.
  Tech-stack agnostic; works with or without requirement documents. Use when
  the user wants to discover or name the domain of a grown
  codebase, build a ubiquitous language or glossary from the repo, check
  whether the code matches the product documents, find the model-vs-code
  drift, classify subdomains, or asks for "domain distillation", "destylacja
  domeny", "słownik domeny", "DDD map of this repo".
---

# Destylacja domeny: domena, której kod nigdy nie nazwał

Przygotuj jeden raport, `context/domain/domain-distillation.md`, który odpowiada na pytania:
**z czego składa się domena tego produktu, jakie słowa ją nazywają, czy kod
używa tych samych słów i tych samych reguł oraz gdzie kod oddalił się od
biznesu?**

Produktem jest **mapa domeny, a nie kod ani plan refaktoryzacji**.
Nie zakładaj niczego z góry: żadnych nazw encji, agregatów, ścieżek ani
numerów wymagań. Odkryj je i wskaż źródło każdego z nich.

**Domena jest odkrywana, a nie dana.** Umiejętność nie przyjmuje docelowego terminu
ani obszaru. Destyluje cały produkt (lub poddrzewo `--root`) i kończy się
rankingiem; wybór tego, co zmienić dalej, pozostaje po stronie użytkownika.

## Wyniki

Wszystkie wyniki znajdują się w `<repo-root>/context/domain/`, również gdy `--root`
zawęża zakres kodu.

| Ścieżka                                        | Co                                                                                       |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `context/domain/domain-distillation.md`        | **Raport** — jedyny plik przeznaczony do czytania przez ludzi i w późniejszej pracy      |
| `context/domain/glossary.md`                   | Zwięzły słownik dla agentów i ludzi: termin, znaczenie, nazwa w kodzie, nie nazywaj tego |
| `context/domain/evidence/0-sources.md`         | Zakres kodu, stos i warstwy, wykluczenia — bez słownictwa domenowego                     |
| `context/domain/evidence/0-documents.md`       | Dokumenty domenowe i cele produktu                                                       |
| `context/domain/evidence/1-docs-language.md`   | Terminy, definicje, cykle życia, reguły i cele określone w dokumentach                   |
| `context/domain/evidence/2-code-language.md`   | Nazwy domenowe w kodzie: typy, tabele, stany, operacje, zdarzenia                        |
| `context/domain/evidence/3-code-rules*.md`     | Reguły biznesowe, których strzeże kod: gdzie, na której warstwie, jak rygorystycznie     |
| `context/archive/<stamp>-domain-distillation/` | Wcześniejszy raport, słownik i materiał dowodowy, przeniesione tutaj przy zastąpieniu    |

## 1. Kontrola wstępna

- Jeśli istnieje `context/domain/domain-distillation.md`: przy użyciu `--replace` lub gdy
  nie ma nikogo, kogo można zapytać (uruchomienie zorkiestrowane lub CI), przenieś go do
  `context/archive/<stamp>-domain-distillation/domain-distillation.md`, wraz z
  `glossary.md` i starym `evidence/` obok niego
  — `<stamp>` to czas modyfikacji raportu w formacie `YYYY-MM-DD-HHMM` — wskaż w polu
  `evidence:` zarchiwizowanego raportu jego nowe `evidence/`, a następnie
  kontynuuj; w przeciwnym razie zapytaj raz: czy go zastąpić. To jedyne
  pytanie.
- **Zakres.** Bez `--root` zakres kodu obejmuje całe repozytorium. W monorepo,
  którego dokumenty wymagań opisują jedną aplikację, ustaw zakres kodu na tę
  aplikację i wymień pozostałe pakiety jako wykluczone, z jednozdaniowym
  uzasadnieniem dla każdego. Dokumenty są zawsze odkrywane od korzenia
  repozytorium (oraz `--docs`), niezależnie od zakresu kodu.
- Język raportu: `--lang`, w przeciwnym razie język żądania użytkownika, a w ostateczności
  angielski. Terminy domenowe pozostają w języku użytym przez źródła; nigdy nie
  tłumacz terminu, który kod lub dokumenty zapisują w innym języku.
- Utwórz `context/domain/evidence`. Wylistuj pliki za pomocą
  `git ls-files --cached --others --exclude-standard` w repozytorium git,
  aby ignorowane i generowane drzewa pozostały pominięte, a nieśledzone dokumenty zostały uwzględnione.
- Ścieżki w każdym pliku są względne wobec repozytorium. Gdy zakres kodu jest głęboki,
  nagłówek raportu może definiować jeden alias (`app/` = `apps/shop/src/`).
- Zapisz krótki HEAD oraz informację, czy worktree ma niezatwierdzone zmiany.

## 2. Inwentaryzacja źródeł (główny agent)

Zbuduj wspólny stan faktyczny przed delegowaniem, zgodnie z
[references/source-inventory.md](references/source-inventory.md). Celowo zawiera dwa
pliki:

- `evidence/0-sources.md` — zakres kodu, stos, lokalizację każdej warstwy,
  wykluczenia. **Bez słownictwa domenowego**: agenci kodu go czytają, a
  terminy z dokumentów, które do nich dotrą, zamieniłyby ich ustalenia w potwierdzenie
  tego, co im powiedziano.
- `evidence/0-documents.md` — dokumenty domenowe według rodzaju, cele produktu
  i ich cytaty. Czytane wyłącznie przez agenta dokumentów i podczas syntezy.

Przeczytaj nagłówki i krótkie fragmenty; pełną lekturę pozostaw pod-agentom.

## 3. Równolegle deleguj pod-agentów zbierających materiał dowodowy

Uruchom ich w **jednej wiadomości**. Każdy prompt zawiera: bezwzględną ścieżkę tego
katalogu umiejętności (`<loaded-skill-dir>` w opisach), ścieżkę do jego opisu,
korzeń repozytorium, zakres kodu, pliki inwentaryzacyjne, które może czytać, ścieżkę
wyjściową, język raportu oraz poniższe reguły. Każdemu pod-agentowi powiedz, aby najpierw przeczytał
swój opis.

| Pod-agent     | Opis                                                                   | Czyta                      | Pytanie                                           |
| ------------- | ---------------------------------------------------------------------- | -------------------------- | ------------------------------------------------- |
| docs-language | [references/agent-docs-language.md](references/agent-docs-language.md) | oba pliki inwentaryzacyjne | Jakie słowa, cykle życia i reguły określa biznes? |
| code-language | [references/agent-code-language.md](references/agent-code-language.md) | tylko `0-sources.md`       | Jakich słów używa kod i do czego?                 |
| code-rules    | [references/agent-code-rules.md](references/agent-code-rules.md)       | tylko `0-sources.md`       | Których reguł kod faktycznie strzeże i gdzie?     |

**Duży zakres kodu.** Gdy zakres kodu zawiera więcej niż ~1,500 plików źródłowych,
podziel code-rules na jednego agenta dla każdej grupy warstw lub obszarów
najwyższego poziomu z `0-sources.md` (maksymalnie cztery), przy czym każdy zapisuje do
`evidence/3-code-rules-<group>.md`. Pokrycie jest ważniejsze niż głębia: obszar, którego żaden agent
nie przeszukał, jest niewiadomą, nigdy „brakiem reguł”.

W swoim asystencie kodowania AI deleguj za pomocą natywnej funkcji pod-agentów;
potrzebują oni uprawnień do zapisu. Bez obsługi pod-agentów uruchom opisy
sekwencyjnie samodzielnie, najpierw agentów kodu, zanim przeczytasz jakikolwiek dokument.

Podział jest celowy: agenci języka nigdy nie widzą wzajemnie swoich wyników,
a agent reguł inwentaryzuje zabezpieczenia bez wskazywania mu, których reguł ma
szukać. Zgodność odkryta później podczas syntezy jest wtedy rzeczywistą zgodnością.

Reguły do przekazania każdemu pod-agentowi:

1. Cytuj każdy termin, regułę i zabezpieczenie jako `path:line`, zweryfikowane w tej sesji.
   Nigdy nie wymyślaj terminu, definicji ani lokalizacji.
2. Cytuj własne sformułowania źródła dla definicji i reguł; parafrazuj wyłącznie
   w wyraźnie oznaczonym wyjaśnieniu.
3. Oznacz ustalenia jako `evidence`, `inference` lub `unknown`. Wyszukiwanie, które niczego
   nie znalazło, zgłaszaj wraz z przeszukanym zakresem, nigdy jako „nie istnieje”.
4. Tylko odczyt: bez zmian w kodzie, buildów i instalacji.
5. Zwróć głównemu agentowi maksymalnie 15 wierszy: najsilniejsze ustalenia,
   luki i pokrycie.

Poczekaj na wszystkie. Nieudany lub częściowy pod-agent stanowi wskazaną lukę w
raporcie; ponów próbę tylko raz, wyłącznie jeśli awaria była mechaniczna.

## 4. Zsyntetyzuj raport

Połącz pliki materiału dowodowego i zapisz `context/domain/domain-distillation.md`
zgodnie z [references/report.md](references/report.md): wszechobecny
język z lokalizacją w kodzie lub wyraźnym **missing in code** dla każdego
terminu Core i Supporting, granice kontekstów, subdomeny, kandydatów na agregaty
i polityki ze statusem każdego niezmiennika (**enforced**,
**declared**, **ignored**, **contradicted**; **undocumented** dla
ekspozycji, których nie obejmuje żaden dokument), lista rozbieżności
modelu względem kodu oraz ranking — następnie nadaj mu charakter operacyjny, jak opisuje `report.md`: stabilne
ID, stronę naprawy dla każdego wiersza rozbieżności, kryterium _done when_ dla każdej pozycji rankingu,
pytania z właścicielem, zmiany od poprzedniego uruchomienia oraz
`context/domain/glossary.md`.

Zanim nazwiesz udokumentowaną regułę _ignored_ lub termin _missing in code_, wykonaj
samodzielnie ukierunkowane wyszukiwanie (`rg` po terminie, jego wariantach i synonimach w
warstwie, w której powinien się znajdować). Grupuj je według warstw i cytuj zakres każdej grupy raz.

## 5. Zweryfikuj, a następnie przedstaw

Wykonaj przebieg weryfikacyjny z
[references/report.md](references/report.md#verification). Następnie przedstaw w
5–8 zdaniach: ścieżkę raportu, liczbę terminów Core i Supporting oraz
ile z nich nie występuje w kodzie, subdomenę(-y) Core, najsilniejszą rozbieżność,
kandydata nr 1 i dlaczego, liczbę rozbieżności według strony naprawy (kod /
dokumenty / decyzja), otwarte pytania oraz główne ograniczenie. Wskaż słownik
jako plik, do którego należy odwoływać się w instrukcjach dla agentów. Zakończ na tym; destylacja
nie projektuje ani nie rozpoczyna refaktoryzacji.
