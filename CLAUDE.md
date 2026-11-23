# CLAUDE.md

Guidance for AI coding assistants working in this repository. Humans: see README.md and docs/.

## Layout

- `api/` — FastAPI (Python 3.13, uv, SQLAlchemy 2, Alembic, Pydantic v2). Feature folders use `models.py` / `schemas.py` / `service.py` / `router.py`.
- `web/` — Next.js 16 App Router, React 19, TypeScript, Mantine 9. Pages are client components; data comes from the API via `src/lib/api.ts`.
- `docker-compose.yml` — `db` (Postgres 17), `api` (:8000), `web` (:3000). The web server rewrites `/api/*` to the API.
- Tool modules: `api/app/modules/<id>/module.py` + `api/app/modules/__init__.py` registry; `web/src/modules/<id>/` + `web/src/modules/registry.ts`. Outside-API calls go in the module's `client.py` via `app.core.http.request_json` (tests fake it).
- Teams (dashboard cards): `api/app/teams/` + `web/src/components/teams/`. A module with a `team_service` (see `api/app/modules/base.py`) gets a create button on every team card. See `docs/teams.md`.
- Coolify panel and Security page: `api/app/modules/coolify/` (`client.py` REST, `ssh.py` server patching/scans over SSH with Coolify's key, `service.py`, background `ServerJob`s) + `web/src/modules/coolify/`. Per-team keys use `CredentialScope.TEAM` (`app/teams/credentials.py`).

## Commands

Run inside containers (`docker compose exec api …` / `docker compose exec web …`), or locally from `api/` with `uv run …` and from `web/` with `npm run …`.

- API: `pytest`, `ruff check .`, `ruff format .`, `mypy app tests`
- Web: `npm run lint`, `npm run typecheck`, `npm run format`, `npm run build`
- All checks: `make check`
- New migration: `alembic revision --autogenerate -m "..."` (after importing the model in `api/app/models.py`); review the generated file.

## Rules

- Enforce auth in the API with `CurrentUser` / `CurrentSuperuser` (`api/app/auth/dependencies.py`); UI checks are cosmetic.
- Every schema change needs an Alembic migration. Never edit a migration that is already on `main`.
- Keep `web/src/lib/types.ts` in sync with API schemas.
- Server settings go through `api/app/core/config.py` and are documented in `.env.example`. No secrets in code.
- Third-party API keys are NOT env vars: declare a `CredentialSpec` (module `credentials=[...]` or `CORE_CREDENTIALS` in `api/app/credentials/registry.py`) and read with `get_user_credential` / `get_system_credential`. Never return or log values.
- New users join via invites (`api/app/invites/`); tokens are stored only as SHA-256 hashes.
- Next.js 16 differs from older versions; consult `web/node_modules/next/dist/docs/` before using unfamiliar APIs.
- Update docs in `docs/` when behavior or setup changes.
