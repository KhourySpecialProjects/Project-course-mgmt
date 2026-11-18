# Architecture

This page explains how the app is put together: the three tiers, how a request flows through them, and where to find things in the code.

## The three tiers

```
 Your browser
     │  http://localhost:3000
     ▼
┌──────────────────────────┐
│  web  (Next.js + Mantine)│  Renders the UI. Forwards every /api/* request
│  container, port 3000    │  to the api container ("rewrite").
└────────────┬─────────────┘
             │  http://api:8000/api/...   (inside the Docker network)
             ▼
┌──────────────────────────┐
│  api  (FastAPI, Python)  │  Business logic, authentication, and (soon)
│  container, port 8000    │  calls to GitHub and Linear.
└────────────┬─────────────┘
             │  SQL over postgresql://db:5432
             ▼
┌──────────────────────────┐
│  db   (PostgreSQL 17)    │  Stores users, sessions, and the course model.
│  container, port 5432    │  Data lives in the `db-data` Docker volume.
└──────────────────────────┘
```

Each box is a separate **container**: a lightweight, isolated environment with its own operating system files and installed software. [`docker-compose.yml`](../docker-compose.yml) describes all three and connects them on a private network where they can reach each other by service name (`api`, `db`).

### Why the web app forwards `/api` requests

The browser only ever talks to `localhost:3000`. When the front-end code calls `fetch("/api/users")`, the Next.js server forwards it to `http://api:8000/api/users` (configured in [`web/next.config.ts`](../web/next.config.ts)).

Because the browser sees a single origin, the login cookie is sent automatically and there's no need for CORS configuration. In production the same pattern works behind any reverse proxy.

## Following a request: "list users"

1. You open **Users** in the sidebar. The browser loads the page component [`web/src/app/(app)/admin/users/page.tsx`](../web/src/app/(app)/admin/users/page.tsx).
2. The page runs `api.get("/users")` (helper in [`web/src/lib/api.ts`](../web/src/lib/api.ts)), which calls `GET /api/users`. The browser attaches the `session` cookie.
3. Next.js forwards the request to the API container.
4. FastAPI matches it to `list_users` in [`api/app/users/router.py`](../api/app/users/router.py). Before the function runs, the router's `require_superuser` dependency ([`api/app/auth/dependencies.py`](../api/app/auth/dependencies.py)) looks up the session cookie in the database and checks that the user is a superuser. If not, it returns `401` or `403` and the function never runs.
5. `list_users` queries the `users` table through SQLAlchemy and returns `User` objects.
6. FastAPI converts them to JSON using the `UserRead` schema ([`api/app/users/schemas.py`](../api/app/users/schemas.py)), which deliberately leaves out `password_hash`.
7. The page receives the JSON and renders it in a Mantine `Table`.

## Folder tour

```
.
├── docker-compose.yml      How the three containers are built, configured, and connected
├── .env.example            Template for your local .env (settings and secrets)
├── Makefile                Shortcuts: make up, make test, make lint, …
├── .github/workflows/      CI: runs lint, type checks, tests, and builds on every PR
├── db/init/                SQL/shell scripts Postgres runs on first start (creates the test DB)
├── docs/                   You are here
│
├── api/                    ── Python / FastAPI ──
│   ├── Dockerfile
│   ├── pyproject.toml      Python dependencies and tool settings (ruff, mypy, pytest)
│   ├── uv.lock             Exact versions of every dependency (generated; commit it)
│   ├── alembic.ini         Migration tool settings
│   ├── migrations/         Database migrations, one file per schema change
│   ├── scripts/start.sh    Container start-up: migrate → ensure superuser → run server
│   ├── tests/              pytest tests
│   └── app/
│       ├── main.py         Creates the FastAPI app and mounts every router
│       ├── models.py       Imports every database model (so Alembic sees them)
│       ├── cli.py          Admin commands (create user, reset password)
│       ├── core/           Shared infrastructure: config, db, security, bootstrap
│       ├── auth/           Login, logout, sessions, and the "require login" dependencies
│       ├── users/          The User model and superuser-only user management
│       └── modules/        Tool modules (github/, linear/) and their registry
│
└── web/                    ── TypeScript / Next.js ──
    ├── Dockerfile
    ├── package.json        JavaScript dependencies and npm scripts
    ├── next.config.ts      Includes the /api → api container rewrite
    └── src/
        ├── app/            Pages. The folder path is the URL path (see below)
        ├── components/     Shared UI pieces: AppLayout, AuthProvider, …
        ├── lib/            Non-UI helpers: api client, TypeScript types
        ├── modules/        Tool modules' UI code and the sidebar registry
        └── theme.ts        Colors, fonts, and other Mantine theme settings
```

### Code layout inside the API

Each feature folder in `api/app/` follows the same pattern:

| File | Contains | Knows about HTTP? |
| ---- | -------- | ----------------- |
| `models.py` | SQLAlchemy classes, one per database table | No |
| `schemas.py` | Pydantic classes describing request/response JSON | No |
| `service.py` | Business logic: functions that take a `db` session and do the work | No |
| `router.py` | FastAPI endpoints: parse the request, call the service, return a response | Yes |

Keeping logic in `service.py` means the CLI, the start-up bootstrap, background jobs, and tests can all reuse it without going through HTTP.

### How pages map to URLs in the web app

Next.js uses **file-based routing**: a `page.tsx` file's folder path is its URL.

| File | URL |
| ---- | --- |
| `src/app/login/page.tsx` | `/login` |
| `src/app/(app)/page.tsx` | `/` |
| `src/app/(app)/account/page.tsx` | `/account` |
| `src/app/(app)/admin/users/page.tsx` | `/admin/users` |
| `src/app/(app)/tools/github/page.tsx` | `/tools/github` |

A folder name in parentheses, like `(app)`, is a **route group**: it does not appear in the URL. It lets every page inside share [`(app)/layout.tsx`](../web/src/app/(app)/layout.tsx), which redirects logged-out visitors to `/login` and wraps the page in the sidebar and header.

Most pages start with `"use client"`, which makes them run in the browser. That's the right choice for this app: pages load data from the API after the user is known, and they use interactive hooks like `useState` and `useEffect`.

## The module system

The README describes a **core shell** plus pluggable **tool modules**. The skeleton implements the plumbing:

- **API side:** each module lives in `api/app/modules/<id>/module.py` and exports a `ToolModule` (id, name, description, router, and an `is_configured()` check). [`api/app/modules/__init__.py`](../api/app/modules/__init__.py) lists the installed modules. `main.py` mounts each module's router at `/api/tools/<id>/…`, and `GET /api/tools` lists them for the dashboard.
- **Web side:** each module's UI lives in `web/src/modules/<id>/`, its page in `web/src/app/(app)/tools/<id>/page.tsx`, and an entry in [`web/src/modules/registry.ts`](../web/src/modules/registry.ts) adds it to the sidebar and dashboard.

GitHub and Linear are placeholders that only report whether their API token is set. [Adding a tool module](adding-a-tool-module.md) walks through building one.

### Planned pieces not yet built

These are described in the README and will slot into the existing structure:

- **Course model** (`api/app/courses/`): courses, students, teams, projects. Tool modules read and write it.
- **Integration adapters** (`api/app/modules/<id>/client.py`): thin wrappers around the GitHub/Linear APIs that handle tokens, rate limits, and retries.
- **Job runner**: background execution of bulk operations with progress, logs, and a dry-run preview. A `jobs` table plus a worker process (a fourth container) is the likely shape.

## Configuration

All settings come from **environment variables**, read in [`api/app/core/config.py`](../api/app/core/config.py). Locally, Docker Compose loads them from `.env`. In production you'd set them in your hosting platform. Never hard-code secrets in source files.
