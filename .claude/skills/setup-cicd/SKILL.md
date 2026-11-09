---
name: setup-cicd
description: Generate a GitHub Actions validation and publish pipeline for an AI toolkit package published to AWS CodeArtifact through OIDC.
---

# /setup-cicd — Zbuduj potok publikowania CodeArtifact

Generujesz przepływ pracy CI/CD dla pakietu zestawu narzędzi Model 2 AI.

Potok waliduje pakiet i publikuje go do AWS CodeArtifact z GitHub Actions przy użyciu OIDC. Nie może zależeć od długotrwałych kluczy dostępu AWS.

## Dane wejściowe

Odczytaj te pliki, jeśli są obecne:

Specyfikacje `m5l4-*.md` pochodzą z `10x get m5l4`, które zapisuje je w katalogu promptów Twojego narzędzia (katalog konfiguracji AI tool/prompts/, lub `.cursor/prompts/`, `.github/prompts/`, `.agents/prompts/` dla innych narzędzi). Najpierw sprawdź tam, a następnie użyj katalogu głównego repozytorium, jeśli osoba ucząca się je przeniosła.

- `m5l4-codeartifact-spec-cicd.md`
- `m5l4-codeartifact-spec-terraform.md`
- `context/spec-cicd.md`
- `context/spec-terraform.md`
- `packages/ai-toolkit/package.json`
- `packages/ai-toolkit/pack.yaml`

Jeśli brakuje domeny CodeArtifact, repozytorium, regionu AWS, lokalizacji pakietu lub gałęzi, zapytaj o nie przed zapisaniem przepływu pracy.

## Przepływ pracy

1. Ustal:
   - domyślną gałąź,
   - lokalizację pakietu,
   - region AWS,
   - domenę CodeArtifact,
   - repozytorium CodeArtifact,
   - przestrzeń nazw pakietu,
   - nazwę sekretu ARN roli.
2. Utwórz `.github/workflows/ci.yml`.
3. Dodaj uprawnienia przepływu pracy:

```yaml
permissions:
  contents: read
  id-token: write
```

4. Dodaj zadanie walidacji, które sprawdza:
   - czy `pack.yaml` istnieje,
   - czy wymagane pola `pack.yaml` są obecne,
   - czy każde `skills/*/SKILL.md` ma frontmatter `name` i `description`,
   - czy frontmatter `name` pasuje do katalogu umiejętności,
   - czy `npm pack --dry-run` kończy się powodzeniem.
5. Dodaj zadanie publikacji, które uruchamia się tylko przy push do domyślnej gałęzi.
6. Skonfiguruj poświadczenia AWS za pomocą `aws-actions/configure-aws-credentials@e1253824e5c10ff9df46874f81ed3ec929e19cfd # v6.3.0`.
   Przypnij `actions/checkout` (`3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`) i `actions/setup-node` (`949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0`) do pełnych SHA w ten sam sposób i użyj `node-version: 24`. Sprawdź ponownie SHA za pomocą `gh api repos/<owner>/<repo>/commits/<tag> --jq .sha` (to rozwiązuje tagi adnotowane do commitu), jeśli istnieją nowsze tagi.
7. Uruchom `aws codeartifact login`.
8. Publikuj z katalogu pakietu.

## Zasady bezpieczeństwa

- Użyj OIDC przez `AWS_ROLE_ARN`; nie generuj przepływów pracy z `AWS_ACCESS_KEY_ID` ani `AWS_SECRET_ACCESS_KEY`.
- Nie wypisuj tokenów.
- Przechowuj identyfikator konta i ARN roli w sekretach GitHub, chyba że użytkownik wyraźnie wybierze inny mechanizm.
- Nie publikuj przy pull requestach.

## Weryfikacja

Uruchom lokalne kontrole, gdy to możliwe:

```bash
test -f .github/workflows/ci.yml
grep -q "id-token: write" .github/workflows/ci.yml
grep -q "aws codeartifact login" .github/workflows/ci.yml
npm --prefix packages/ai-toolkit pack --dry-run
```

Zakończ, wymieniając wymagane sekrety GitHub oraz wszelką ręczną konfigurację AWS, która musi istnieć przed pierwszym uruchomieniem.
