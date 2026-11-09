---
change_id: walking-skeleton-deploy
title: Szkielet aplikacji (FastAPI + React + Postgres) z darmowym auto-deployem
status: implementing
created: 2026-11-09
updated: 2026-11-09
archived_at: null
---

## Notes

Roadmap item F-01. Hosting zmieniony z Fly na Render free + Supabase free (warunek użytkownika: całe demo darmowe, aplikację da się postawić lokalnie po sklonowaniu z GitHuba).

Faza 1 — adaptacje względem planu:
- Smart App Control na maszynie autora blokuje natywne wheele (pydantic_core, psycopg_binary), więc backend działa w kontenerze: serwis `backend` (profil `dev`) w docker-compose + `backend/check.sh` z bramkami. Host potrzebuje tylko Dockera. README (faza 4) ma to opisać jako główną ścieżkę dev.
- Porty hosta konfigurowalne: `POSTGRES_HOST_PORT`, `BACKEND_HOST_PORT` (u autora 55432 / 8001, bo 5432 i 8000 zajmują inne projekty).
- Do zrobienia przy okazji: Starlette ostrzega, że TestClient z `httpx` jest deprecated na rzecz `httpx2`.
