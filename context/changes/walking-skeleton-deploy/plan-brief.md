# Szkielet aplikacji z darmowym auto-deployem — Plan Brief

> Full plan: `context/changes/walking-skeleton-deploy/plan.md`

## What & Why

Budujemy działający szkielet: FastAPI, React + TypeScript i PostgreSQL połączone w jedną aplikację bez funkcji domenowych. Aplikacja wdraża się automatycznie po merge do `main`. To fundament F-01 z roadmapy: bez niego żaden wycinek (logowanie, analiza zapytania, orchestrator) nie jest sprawdzalny end-to-end. Warunek użytkownika: całe demo za 0 USD i możliwość postawienia aplikacji lokalnie po sklonowaniu z GitHuba.

## Starting Point

Repo zawiera tylko wynik `uv init`: placeholder `main.py`, `pyproject.toml` z FastAPI (nazwa `agent-orchestrator`, Python 3.14) i `.git` bez commitów. Nie ma frontendu, bazy, migracji, Dockerfile ani CI. `tech-stack.md` zakładał Fly, który nie ma już darmowego planu.

## Desired End State

Po `git clone` i `docker compose up --build` każdy widzi pod `localhost:8000` stronę stanu aplikacji: API ok, baza ok, rewizja migracji. Każdy push i PR przechodzi pełne bramki jakości w GitHub Actions. Merge do `main` z zielonym CI wdraża tę samą aplikację na Render free z bazą w Supabase free, a publiczny URL pokazuje ten sam stan.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) |
| --- | --- | --- |
| Hosting aplikacji | Render free (Docker) | Fly nie ma darmowego planu dla nowych kont, a Render daje 0 USD i deploy po zielonym CI (`checksPass`). |
| Baza na produkcji | Supabase free przez session pooler | Wybór użytkownika; darmowy plan ma direct connection tylko po IPv6, więc jedyną drogą z Render jest session pooler. |
| Topologia | Jeden kontener, FastAPI serwuje SPA | Jeden origin bez CORS, a ciasteczka sesji dla logowania w S-01 działają od razu. |
| Lokalna baza i CI | Docker Compose / `services: postgres` | Ta sama wersja Postgresa wszędzie; `docker compose up --build` stawia całą aplikację dla osoby z zewnątrz. |
| Bramki jakości | ruff, mypy strict, pytest; eslint, tsc, vitest, build; docker build | Cel roadmapy „jakość”; dokładanie bramek po fakcie oznacza poprawki w całym kodzie. |
| Migracje | Alembic w skrypcie startowym kontenera | `preDeployCommand` jest płatny na Render, a pusta rewizja bazowa uruchamia łańcuch dla S-01. |
| Układ repo | `backend/` (uv, pakiet `app`) + `frontend/` (Vite, npm) | Dwa zestawy narzędzi rozdzielone, jeden Dockerfile w roocie. |

## Scope

**In scope:**
- restrukturyzacja do monorepo i zmiana nazwy na `sales-order-orchestrator`;
- FastAPI z `/api/health` (baza i rewizja migracji), SQLModel, psycopg 3, Alembic;
- React + TS ze stroną stanu (ok / degraded / błąd);
- Dockerfile, docker-compose z pełną aplikacją, `.env.example`;
- GitHub Actions, `render.yaml`, README z instrukcją uruchomienia;
- aktualizacja `tech-stack.md` i `roadmap.md` (Fly → Render + Supabase).

**Out of scope:**
- tabele domenowe, logowanie i role (S-01);
- śledzenie kosztów (F-02) i wywołania LLM;
- testy e2e w przeglądarce, staging, preview deploye, monitoring;
- Fly, płatne plany i dodatki;
- pliki dla agentów (`AGENTS.md`).

## Architecture / Approach

Obraz Docker ma dwa etapy. Node buduje `frontend/dist`, a Python 3.14 z uv instaluje backend i kopiuje frontend. FastAPI obsługuje `/api/*`, a pozostałe ścieżki dostają `index.html`. Przy starcie kontener robi `alembic upgrade head`, potem uruchamia uvicorn na `$PORT`. Ten sam obraz działa w compose (z bazą `db`), w CI (build check) i na Render (z `DATABASE_URL` z Supabase). Ustawienia normalizują schemat URL-a do `postgresql+psycopg://`, a silnik ma `pool_pre_ping` na wypadek uśpienia i pauz.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Backend i baza lokalnie | FastAPI + Alembic + `/api/health` na Postgresie z compose, ruff/mypy/pytest | Python 3.14 a dostępność wheeli zależności |
| 2. Frontend | Vite + React + TS ze stroną stanu, eslint/tsc/vitest | Rozjazd typu odpowiedzi health między backendem a frontendem |
| 3. Jeden kontener | Dockerfile, SPA z FastAPI, migracje przy starcie, `docker compose up` | Kolejność tras: fallback SPA przechwytujący `/api` |
| 4. CI/CD i wdrożenie | GitHub Actions, `render.yaml` (free, checksPass), README, aktualizacja docs | Błędny URL Supabase (direct zamiast session poolera) |

**Prerequisites:** konta GitHub, Supabase i Render (darmowe), Docker Desktop lokalnie. Pierwszy commit i publiczne repo zakłada człowiek w Fazie 4.
**Estimated effort:** ~2–3 sesje z agentem w 4 fazach, plus ~30 min klikania w panelach.

## Open Risks & Assumptions

- **Pauza Supabase:** projekt free wstrzymuje się po 7 dniach bez aktywności. Przed demo trzeba sprawdzić i ewentualnie przywrócić projekt w panelu (opisane w README).
- **Usypianie Render:** free usypia po ~15 min, a pierwsze wejście trwa ~1 min. Przed pokazem rekruterowi otwórz link wcześniej.
- **Limity darmowych planów:** mogą się zmienić. Dane pochodzą z dokumentacji i źródeł z listopada 2026.
- **Repo publiczne:** zakładamy publiczne repo na GitHubie (darmowe Actions, warunek „ktoś może pobrać z GH”). Sekrety są wyłącznie w panelach, nigdy w repo.

## Success Criteria (Summary)

- Osoba z zewnątrz klonuje repo i jednym poleceniem widzi działającą aplikację z bazą.
- Merge do `main` z zielonym CI daje działającą aplikację pod publicznym URL-em, a czerwone CI blokuje deploy.
- Całkowity koszt wynosi 0 USD.
