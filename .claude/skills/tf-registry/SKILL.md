---
name: tf-registry
description: Generate Terraform for the Model 2 AWS CodeArtifact npm registry, including domain, repositories, KMS and IAM policy wiring.
---

# /tf-registry — Wygeneruj rejestr CodeArtifact

Generujesz Terraform dla prywatnego rejestru npm Model 2 używanego przez pakiet zestawu narzędzi AI.

Ta umiejętność obejmuje ścieżkę zarządzanej infrastruktury z m5l4: AWS CodeArtifact provisioned through Terraform. Należy jej używać wyłącznie wtedy, gdy osoba ucząca się świadomie wybierze ścieżkę dodatku AWS, a nie jako domyślnej opcji dla każdego zespołu.

## Dane wejściowe

Odczytaj te pliki, jeśli istnieją:

Specyfikacje `m5l4-*.md` pochodzą z `10x get m5l4`, które zapisuje je w katalogu promptów Twojego narzędzia (katalogu konfiguracji narzędzia AI lub `.cursor/prompts/`, `.github/prompts/`, `.agents/prompts/` dla innych narzędzi). Najpierw szukaj tam, a następnie przejdź do katalogu głównego repozytorium, jeśli osoba ucząca się je przeniosła.

- `m5l4-codeartifact-spec-terraform.md`
- `m5l4-codeartifact-spec-cicd.md`
- `context/spec-terraform.md`
- `context/spec-cicd.md`

Jeśli wymagane wartości są niedostępne, zapytaj użytkownika o:

- region AWS,
- identyfikator konta AWS,
- nazwę domeny CodeArtifact,
- nazwę prywatnego repozytorium,
- nazwę repozytorium proxy,
- przestrzeń nazw pakietu,
- bucket/key stanu Terraform,
- nazwę lub ARN roli GitHub Actions.

## Cele Terraform

Wygeneruj katalog `terraform/` z plikami takimi jak:

```text
terraform/
├── main.tf
├── variables.tf
├── outputs.tf
├── codeartifact.tf
├── iam.tf
├── kms.tf
└── terraform.tfvars.example
```

Przypnij `required_version = ">= 1.10"` oraz dostawcę `hashicorp/aws` do `~> 6.0`, chyba że specyfikacja stanowi inaczej.

Infrastruktura powinna obejmować:

- konfigurację backendu S3 z natywnym blokowaniem S3, gdy wersja Terraform je obsługuje,
- domenę CodeArtifact,
- prywatne repozytorium npm,
- repozytorium upstream/proxy npm public,
- zewnętrzne połączenie npm,
- klucz i alias KMS,
- zarządzaną politykę IAM dla operacji odczytu/publikowania CodeArtifact,
- punkt podpięcia dla roli GitHub Actions używanej przez CI/CD.

## Pułapki, które należy zachować

- Domena CodeArtifact i zakres pakietu npm to różne pojęcia.
- `aws codeartifact login --namespace` oczekuje zakresu npm bez `@`.
- Terraform nie powinien zawierać zakodowanych na stałe osobistych danych uwierzytelniających.
- Rola GitHub Actions może być wskazana jako istniejąca rola, gdy organizacja ma już skonfigurowane OIDC.

## Weryfikacja

Uruchom, gdy jest to możliwe:

```bash
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate
```

Jeśli Terraform nie jest zainstalowany lub inicjalizacja dostawcy jest niedostępna, poinformuj o tym i mimo to uruchom statyczne kontrole wygenerowanych plików.

Nie uruchamiaj `terraform apply`, chyba że użytkownik wyraźnie o to poprosi.
