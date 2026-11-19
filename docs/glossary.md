# Glossary

Terms you'll run into in this codebase and its docs.

**Alembic** — The tool that manages database schema changes (migrations). See [Database & migrations](database-and-migrations.md).

**API** — Application Programming Interface. Here, the FastAPI service in `api/` that the web app calls over HTTP to read and change data.

**AppShell** — The Mantine component that provides the page frame: header, sidebar, and content area. Used in `web/src/components/AppLayout.tsx`.

**API key / token** — A secret string that lets the app call an outside service (GitHub, Linear, Anthropic) on someone's behalf. Stored encrypted; see [API keys and tokens](api-keys.md).

**Argon2** — A password-hashing algorithm designed to be slow to brute-force. Used to store passwords.

**CI (continuous integration)** — Automated checks (tests, lint, builds) that run on GitHub for every pull request. Configured in `.github/workflows/ci.yml`.

**Client component** — A React component that runs in the browser. Marked with `"use client"` at the top of the file. Needed for interactivity (`useState`, `onClick`, …).

**Container** — An isolated, lightweight environment running one service (here: `web`, `api`, or `db`). Built from an **image**, which is described by a **Dockerfile**.

**CORS** — Browser rules for requests between different origins. This app avoids needing it by sending all API calls through the web app's own origin.

**CSRF (cross-site request forgery)** — An attack where another website makes your browser send a request using your cookies. The `SameSite=Lax` cookie setting blocks the common forms of it.

**Dependency (FastAPI)** — A function FastAPI runs before an endpoint, declared with `Depends(...)` or an `Annotated` alias like `CurrentUser`. Used for things like "get a database session" or "require login".

**Docker Compose** — The tool that starts and connects several containers from one file, `docker-compose.yml`.

**Encryption** — Scrambling data so it can only be read with a key. Unlike a hash, it can be reversed by whoever has the key. Used for stored API keys.

**Endpoint / route** — One URL + HTTP method the API responds to, e.g. `GET /api/users`.

**Environment variable** — A named setting given to a program from outside its code, e.g. `POSTGRES_PASSWORD`. Locally they come from `.env`.

**FastAPI** — The Python web framework used for the API. It uses type hints to validate requests and generate docs.

**Fixture (pytest)** — A reusable piece of test setup, requested by naming it as a test function parameter (e.g. `client`, `make_user`).

**Hash** — A one-way transformation of data. You can check whether a password matches a hash, but you can't recover the password from it.

**HTTP-only cookie** — A cookie the browser's JavaScript can't read, which protects the session token from malicious scripts.

**Idempotent** — Safe to run more than once with the same result. Bulk operations should be idempotent so they can be re-run after a partial failure.

**Invite link** — A one-time URL a superuser creates so a new person can set their password and join. See [Authentication](authentication.md#invitations).

**Lint / linter** — A tool that flags likely bugs and style problems without running the code. Here: `ruff` (Python) and `eslint` (TypeScript).

**Mantine** — The open-source (MIT) React component library used for the UI. Docs: <https://mantine.dev>.

**Migration** — A versioned script that changes the database structure. Lives in `api/migrations/versions/`.

**Model (SQLAlchemy)** — A Python class that maps to a database table, e.g. `User` → `users`.

**Next.js** — The React framework used for the web app. Provides routing, the dev server, and production builds.

**ORM (object-relational mapper)** — A library that lets you work with database rows as Python objects. Here: SQLAlchemy.

**Pull request (PR)** — A request on GitHub to merge your branch into `main`, where it's reviewed and checked by CI.

**Pydantic schema** — A Python class describing the shape of JSON going into or out of the API. Lives in `schemas.py` files.

**Rewrite (Next.js)** — A rule that serves one URL from another location. Here, `/api/*` is rewritten to the API container.

**Route group** — A Next.js folder in parentheses, like `(app)`, that groups pages under a shared layout without affecting the URL.

**Session** — A record that a particular browser is logged in. Stored in the `auth_sessions` table and identified by the `session` cookie.

**Superuser** — An account with admin rights (can invite and manage users, and manage system settings). The first one is created from `SUPERUSER_EMAIL` / `SUPERUSER_PASSWORD`.

**Tool module** — A self-contained integration (GitHub, Linear, …) that plugs into the app. See [Adding a tool module](adding-a-tool-module.md).

**Type hints** — Annotations like `def f(x: int) -> str` that say what types a Python function expects. Checked by `mypy`.

**uv** — The Python package manager used for the API. `uv add <package>` adds a dependency.

**Volume (Docker)** — Storage that outlives a container. The database's data lives in the `db-data` volume, so it survives `docker compose down` (but not `down -v`).
