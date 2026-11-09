---
name: 10x-status
description: Show status of changes by reading change.md frontmatter and parsing each plan's ## Progress section
---

# /10x-status — Status zmiany

Pokaż status każdej zmiany w drzewie `context/` bieżącego projektu, odczytując frontmatter `change.md` i analizując sekcję `## Progress` każdego planu. **Nie jest używany żaden plik stanu** — Progress jest jedynym źródłem prawdy (zobacz `references/progress-format.md`).

## Tryby

- **Bez argumentu** — wyświetl każdy folder w `context/changes/` i `context/archive/` wraz ze statusem + ukończeniem Progress + ostrzeżeniami o rozbieżnościach.
- **`<change-id>`** — szczegółowy widok pojedynczej zmiany: wyświetl każdy artefakt w folderze tej zmiany i zgłoś obecność/status każdego z nich.

## Renderowanie dla każdej zmiany

Dla każdego folderu w `context/changes/<change-id>/` i `context/archive/<dated-id>/`:

1. Odczytaj frontmatter `change.md`, aby uzyskać `change_id`, `title`, `status`, `updated`, `created`.
2. Jeśli istnieje `plan.md`, przeanalizuj jego sekcję `## Progress`:
   - `total` = liczba wierszy `- [ ]` + `- [x]` pod nagłówkiem Progress.
   - `done` = liczba wierszy `- [x]`.
   - `current_phase`/`current_step` = nagłówek `### Phase N:` oraz indeks `N.M` pierwszego `- [ ]` (lub „all complete”, jeśli `done == total`).
3. Wyemituj jeden wiersz:

   ```
   <change-id> — <status> (<done>/<total> kroków, bieżący krok <N.M>, zaktualizowano <YYYY-MM-DD>)
   ```

## Wskazówka wznowienia

Po wyświetleniu listy, jeśli jakakolwiek zmiana ma `status: implementing`, wybierz tę z najnowszym `updated` i skopiuj polecenie wznowienia do schowka:

```bash
echo -n "/10x-implement <change-id> phase <N>" | pbcopy 2>/dev/null || echo -n "/10x-implement <change-id> phase <N>" | clip.exe 2>/dev/null || echo -n "/10x-implement <change-id> phase <N>" | xclip -selection clipboard 2>/dev/null || true
```

```powershell
# PowerShell (Windows)
Set-Clipboard "/10x-implement <change-id> phase <N>"
```

Oznacz ten wiersz w wyjściu za pomocą `(✓ copied)`. Tylko JEDEN wiersz otrzymuje ten sufiks — zmiana o statusie implementing z najnowszym `updated`.

Jeśli sekcja Progress tej zmiany ma co najmniej jeden wiersz `- [x]`, którego linia kończy się sufiksem ` — <sha>` (7+ znaków szesnastkowych), dodaj `(closed at <sha>)` do wskazówki wznowienia, gdzie `<sha>` to SHA w ostatnio ukończonym wierszu (ostatni `[x]` poprzedzający pierwszy `[ ]`). Renderuj `(✓ copied)` po `(closed at <sha>)`. Całkowicie pomiń `(closed at …)` w wierszach bez SHA.

## Kontrole rozbieżności spójności (tylko ostrzeżenia, nigdy blokujące)

Podczas renderowania uwidocznij rozbieżności między `change.md.status` a rzeczywistym stanem Progress. Ostrzeżenia pojawiają się inline obok wiersza zmiany:

| Warunek                                                                 | Ostrzeżenie                                           |
| ----------------------------------------------------------------------- | ----------------------------------------------------- |
| `status: implementing` AND Progress has 0 `[x]`                         | `⚠ status drift: implementing but no progress`        |
| `status: implementing` AND every Progress item `[x]`                    | `⚠ status drift: should be implemented`               |
| `status: planned` AND any Progress item `[x]`                           | `⚠ status drift: should be implementing`              |
| `status: archived` AND folder is in `context/changes/` (not `archive/`) | `⚠ status drift: archived in wrong folder`            |
| Folder in `context/archive/` AND `status` ≠ `archived`                  | `⚠ status drift: in archive/ but status not archived` |
| `status: plan_reviewed` AND `reviews/plan-review.md` missing            | `⚠ missing plan-review artifact`                      |
| `status: impl_reviewed` AND no `reviews/impl-review*.md` present        | `⚠ missing impl-review artifact`                      |

Nigdy nie zgłaszaj błędu ani nie kończ z kodem niezerowym z powodu rozbieżności — `/10x-status` ma charakter informacyjny. Ostrzeżenie przypomina użytkownikowi o poprawieniu `change.md` lub przeniesieniu folderu.

## Szczegółowy widok pojedynczej zmiany (`/10x-status <change-id>`)

Po wywołaniu z argumentem `<change-id>`, wyświetl każdy plik w folderze tej zmiany z jednoliniowym opisem, a następnie wypisz pełną sekcję Progress z SHA renderowanymi inline obok ukończonych wierszy:

```
<change-id> — <status> (<done>/<total> kroków, zaktualizowano <YYYY-MM-DD>)

  change.md          ✓ frontmatter present
  frame.md           ✓ ([file size, line count])
  research.md        ✗ not present
  plan.md            ✓ ([N] phases; current step <N.M>)
  plan-brief.md      ✓
  test-plan.md       ✗ not present
  reviews/
    plan-review.md   ✓
    impl-review.md   ✗ not present
  follow-ups/
    review-fixes.md  ✗ not present

Progress:
  Phase 1: <phase title>
    [x] 1.1 <title> — <sha>
    [x] 1.2 <title>           ← SHA-less row (legacy / empty-diff phase)
    [ ] 1.3 <title>
  Phase 2: <phase title>
    [ ] 2.1 <title>
    ...
```

Renderuj każdy wiersz Progress, zachowując jego oznaczenie `[x]` / `[ ]` oraz oryginalny indeks kroku + tytuł. Dla wierszy `[x]` dodaj ` — <sha>` TYLKO wtedy, gdy linia źródłowa w `plan.md` już zawiera sufiks; nigdy nie twórz ani nie zgaduj SHA. Wiersze `[x]` bez SHA renderuj dokładnie jak dotychczas (bez sufiksu).

Rozwiąż `<change-id>` do `context/changes/<change-id>/` lub `context/archive/<change-id>/` (to drugie dla zmian, których folder archiwum zachowuje sam slug; foldery archiwum mogą również mieć postać `<created-date>-<change-id>/` — wypróbuj oba).

## Szkic wykonania

```bash
# 1. List all changes (active + archived)
find context/changes context/archive -mindepth 1 -maxdepth 1 -type d 2>/dev/null

# 2. For each, read change.md frontmatter (status, updated, title)
# 3. For each, parse plan.md ## Progress section if present
# 4. Render one line per change with completion + drift warnings
# 5. Pick the most-recently updated `implementing` change → clipboard hint
```

## Ważne uwagi

- **Progress jest autorytatywny.** Nigdy nie odczytuj ani nie zapisuj żadnego pliku pomocniczego state-file. Nigdy nie używaj grep do wyszukiwania znaczników postępu w komentarzach HTML.
- **Kontrole rozbieżności są wyłącznie ostrzeżeniami.** Uwidaczniaj niezgodności; nie naprawiaj ich automatycznie. Użytkownik aktualizuje `change.md` lub przenosi folder, jeśli ostrzeżenie jest zasadne.
- **Wpisy archiwalne są tylko do odczytu.** Renderuj je, ale nie sugeruj poleceń, które zapisywałyby dane w `context/archive/`.
- **Szybkość**: dla listy bez argumentów preferuj jeden zbiorczy odczyt wszystkich frontmatterów `change.md` oraz pojedyncze użycie grep dla sekcji Progress w plan.md, zamiast odczytywania każdego planu w całości. Analiza wymaga teraz końcowego sufiksu ` — <sha>` oraz indeksu `N.M`, ale nadal jest to jednoprzejściowe wyrażenie regularne dla sekcji Progress — bez dodatkowych odczytów plików.
