---
change_id: walking-skeleton-deploy
title: Szkielet aplikacji (FastAPI + React + Postgres) z darmowym auto-deployem
status: archived
created: 2026-11-09
updated: 2026-11-09
archived_at: 2026-11-09T19:48:39Z
---

## Notes

Roadmap item F-01. Hosting zmieniony z Fly na Render free + Supabase free (warunek użytkownika: całe demo darmowe, aplikację da się postawić lokalnie po sklonowaniu z GitHuba).

Faza 1 — adaptacje względem planu:
- Smart App Control na maszynie autora blokuje natywne wheele (pydantic_core, psycopg_binary), więc backend działa w kontenerze: serwis `backend` (profil `dev`) w docker-compose + `backend/check.sh` z bramkami. Host potrzebuje tylko Dockera. README (faza 4) ma to opisać jako główną ścieżkę dev.
- Porty hosta konfigurowalne: `POSTGRES_HOST_PORT`, `BACKEND_HOST_PORT` (u autora 55432 / 8001, bo 5432 i 8000 zajmują inne projekty).
Faza 2 — adaptacje względem planu:
- Linter frontendu to oxlint (`oxlint --deny-warnings`) z aktualnego szablonu Vite zamiast ESLint — decyzja użytkownika. Szablon daje też TypeScript 7 i Vite 8. Frontend działa natywnie na Windows (SAC nie blokuje binarek Node).
- Cel proxy dev: zmienna `API_PROXY_TARGET` (frontend/.env.local, gitignorowany), domyślnie http://localhost:8000.
- Do sprawdzenia później: przy zatrzymanej bazie /api/health odpowiada 503 dopiero po ~10 s (timeouty połączenia), strona pokazuje w tym czasie „Checking…”.

Faza 4 — adaptacje i stan wdrożenia:
- Gałąź przemianowana z master na main (CI i render.yaml celują w main). Autor commitów: lukocu (noreply GitHub), bez współautorów.
- Repo: https://github.com/lukocu/sales-order-orchestrator, demo: https://sales-order-orchestrator.onrender.com (health ok, 0001_baseline). Baza: Supabase session pooler, eu-west-1.
- Sync Blueprinta w Renderze pokazał błąd mimo działającego serwisu; API Rendera potwierdza plan free, frankfurt, healthCheckPath /api/health i autoDeployTrigger=checksPass.
- 4.6 (czerwone CI blokuje deploy) pominięte na decyzję autora — sprawdzona tylko konfiguracja, nie zachowanie przy czerwonym CI.
- `.mcp.json` (serwer MCP Supabase autora) jest w .gitignore.

- Do zrobienia przy okazji: Starlette ostrzega, że TestClient z `httpx` jest deprecated na rzecz `httpx2`.
