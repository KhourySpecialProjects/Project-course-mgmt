# Project Course Management Workbench

A web app for instructors running practicum / project-based courses. It is one place to do the setup and monitoring work that otherwise takes hundreds of clicks across GitHub and Linear.

> **New here?** Start with [Getting started](docs/getting-started.md). You'll have the app running on your machine in about ten minutes.

## Quick start

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine with the Compose plugin) and Git.

```bash
git clone https://github.com/KhourySpecialProjects/Project-course-mgmt.git
```

```bash
cd Project-course-mgmt
```

```bash
cp .env.example .env
```

```bash
docker compose up --build
```

Then open <http://localhost:3000> and sign in with `SUPERUSER_EMAIL` / `SUPERUSER_PASSWORD` from your `.env` file (by default `admin@example.com` / `change-me-please`).

| What                  | Where                                |
| --------------------- | ------------------------------------ |
| Web app               | <http://localhost:3000>              |
| API (interactive docs)| <http://localhost:8000/api/docs>     |
| Database              | `localhost:5432` (see `.env`)        |

## Tech stack

| Tier      | Technology | Why |
| --------- | ---------- | --- |
| Front end | [Next.js](https://nextjs.org) (React + TypeScript) with [Mantine](https://mantine.dev) UI components | File-based routing keeps each tool's pages organized; Mantine (MIT-licensed) provides forms, tables, modals, notifications, and dark mode out of the box. |
| API       | [FastAPI](https://fastapi.tiangolo.com) (Python 3.13, fully type-hinted) with [SQLAlchemy](https://www.sqlalchemy.org) and [Alembic](https://alembic.sqlalchemy.org) | Type hints drive request validation and auto-generated API docs. Python has good client libraries for GitHub and Linear. |
| Database  | [PostgreSQL 17](https://www.postgresql.org) | Reliable relational store for the course model. |

Each tier runs in its own Docker container, wired together by [`docker-compose.yml`](docker-compose.yml).

## Documentation

| Guide | Read it when… |
| ----- | ------------- |
| [Getting started](docs/getting-started.md) | You want to run the app for the first time. |
| [Architecture](docs/architecture.md) | You want to understand how the pieces fit together and where code lives. |
| [Development workflow](docs/development-workflow.md) | You're about to write code: the day-to-day loop, tests, linting, branches, and pull requests. |
| [Authentication](docs/authentication.md) | You're working on login, invitations, users, permissions, or the superuser. |
| [API keys and tokens](docs/api-keys.md) | You need a key for GitHub, Linear, Anthropic, etc., or are adding one. |
| [Database & migrations](docs/database-and-migrations.md) | You're adding or changing a table. |
| [Adding a tool module](docs/adding-a-tool-module.md) | You're building a new integration (or the real GitHub/Linear tools). |
| [Troubleshooting](docs/troubleshooting.md) | Something isn't working. |
| [Glossary](docs/glossary.md) | You hit a term you don't recognize. |
| [Contributing](CONTRIBUTING.md) | You're opening a pull request. |

## Why

Setting up a practicum course means doing the same tasks over and over: creating repos, building teams, adding students, linking teams to projects, and repeating all of it in Linear. The workbench turns these into bulk, repeatable operations driven by a course roster.

## Tools

### GitHub

- Create a set of project repos in bulk from a template, with standard settings, branch protection, and labels.
- Create teams and add students to them in bulk from a roster (CSV).
- Give teams access to their project repos at the right permission level.
- See an overview of the org: repos, teams, members, and pending invitations.

### Linear

- Invite users and create one team per project group.
- Create projects, starting issues, and workflow states from course templates.
- Monitor progress across teams: activity, issue throughput, and stalled projects.

### Coolify

- Create one Coolify project per team, with standard environments.
- Deploy each team's app from its GitHub repo.
- Set environment variables in bulk from a course template.
- See every team's deployments at a glance: status, last deploy, and live URL.

### Future tools

New tools plug into the workbench without changes to the core. Possible additions: Slack or Discord channel setup, grading or peer-evaluation exports, and LMS roster import.

## Architecture

The design is modular:

- **Core shell**: authentication, navigation, course and roster model, and shared UI components.
- **Course model**: the shared source of truth. It holds the course, its students, its teams, and its projects. Every tool reads from it and writes to it.
- **Tool modules**: each integration (GitHub, Linear, …) is a self-contained module. A module registers its own routes, UI pages, API client, and actions with the shell.
- **Integration adapters**: thin wrappers around each external API. They handle auth tokens, rate limits, and idempotent retries, so a bulk job can be safely run again.
- **Job runner**: runs long bulk operations in the background, with progress, logs, and a dry-run preview before any changes are made.

To add a tool, create a new module that uses the course model and registers with the shell. See [Adding a tool module](docs/adding-a-tool-module.md).

## Status

The skeleton is in place:

- [x] Three-tier app (Next.js → FastAPI → Postgres), each in its own container
- [x] Email/password login with secure session cookies
- [x] Superuser created automatically from environment variables
- [x] User management for superusers, with one-time invite links for new users
- [x] Encrypted API key storage: personal keys per user, system-wide keys for admins
- [x] Tool-module registry with placeholder GitHub, Linear, and Coolify modules
- [x] Automated tests, linting, type-checking, and CI
- [ ] Course model (courses, students, teams, projects)
- [ ] Roster CSV import
- [ ] GitHub tools
- [ ] Linear tools
- [ ] Coolify tools
- [ ] Background job runner with dry-run preview
