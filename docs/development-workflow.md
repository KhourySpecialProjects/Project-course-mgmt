# Development workflow

How to make a change, check it, and get it merged.

## The everyday loop

1. **Start the stack** (if it isn't running): `docker compose up -d`.
2. **Edit code** in your editor. Both containers watch your files:
   - Saving a `.py` file in `api/` restarts the API server within a second or two.
   - Saving a `.tsx` file in `web/` updates the browser automatically, usually without a full reload.
3. **Watch the logs** to see errors: `docker compose logs -f api` or `docker compose logs -f web`.
4. **Run the checks** before committing: `make check` (details below).

You don't need to rebuild containers for code changes. You **do** need to rebuild after changing dependencies (see [Adding a dependency](#adding-a-dependency)).

## Running commands inside a container

The tools (Python, pytest, npm, …) are installed inside the containers. Run them with `docker compose exec <service> <command>`:

```bash
docker compose exec api pytest
```

```bash
docker compose exec web npm run lint
```

To get an interactive shell inside a container (type `exit` to leave):

```bash
docker compose exec api bash
```

The web container uses Alpine Linux, which has `sh` instead of `bash`:

```bash
docker compose exec web sh
```

## Checks: tests, linting, type checking, formatting

| Check | What it catches | Command (make) | Command (direct) |
| ----- | --------------- | -------------- | ---------------- |
| API tests | Broken behavior | `make test` | `docker compose exec api pytest` |
| Python lint | Bugs, unused imports, style issues | `make lint` | `docker compose exec api ruff check .` |
| Python types | Wrong types passed around | `make lint` | `docker compose exec api mypy app tests` |
| TypeScript lint | React mistakes, unused variables | `make lint` | `docker compose exec web npm run lint` |
| TypeScript types | Wrong types, typos in property names | `make lint` | `docker compose exec web npm run typecheck` |
| Formatting | Inconsistent whitespace and quotes | `make lint` | see Makefile |
| **Everything** | | `make check` | |

To **fix** formatting and auto-fixable lint issues: `make format`.

CI (GitHub Actions, see [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) runs all of these on every pull request, plus a production build of both Docker images. A red ❌ on your PR means one failed; click *Details* to see which.

### Writing tests

API tests live in `api/tests/` and use [pytest](https://docs.pytest.org). Read [`api/tests/conftest.py`](../api/tests/conftest.py) first; it provides fixtures you'll use constantly:

- `client` — a test HTTP client that calls the API without a real server.
- `make_user("x@example.com", is_superuser=True)` — creates a user (password `PASSWORD`).
- `login("x@example.com")` — logs `client` in as that user.
- `db` — a database session for setting up or checking data directly.

A typical test:

```python
def test_regular_user_cannot_list_users(client, make_user, login):
    make_user("student@example.com")
    login("student@example.com")
    assert client.get("/api/users").status_code == 403
```

Tests run against a separate `coursemgmt_test` database that is rebuilt from the migrations at the start of each run and emptied before every test. Your development data is never touched.

Run one file or one test:

```bash
docker compose exec api pytest tests/test_auth.py
```

```bash
docker compose exec api pytest -k change_password
```

Rule of thumb: every new API endpoint gets at least one test for the success case and one for the "not allowed" case.

## Adding a dependency

### Python (API)

From your machine, with [uv](https://docs.astral.sh/uv/) installed:

```bash
cd api && uv add httpx
```

This updates `pyproject.toml` and `uv.lock`. Commit both. Then rebuild the container so it installs the new package:

```bash
docker compose up -d --build api
```

(Use `uv add --dev <package>` for tools only needed during development, like test helpers.)

### JavaScript (web)

```bash
cd web && npm install some-package
```

Commit `package.json` and `package-lock.json`. Then rebuild. The `-V` flag makes Docker discard the container's old `node_modules` so the new package is picked up:

```bash
docker compose up -d --build -V web
```

## Git and pull requests

We use a simple branch-and-pull-request flow. Never commit directly to `main`.

1. Update your local `main`:
   ```bash
   git checkout main
   ```
   ```bash
   git pull
   ```
2. Create a branch named after the change:
   ```bash
   git checkout -b feature/roster-import
   ```
3. Make small commits as you go, with messages that say *what* and *why*:
   ```bash
   git add -A
   ```
   ```bash
   git commit -m "Add CSV upload endpoint for course rosters"
   ```
4. Run `make check`.
5. Push and open a pull request on GitHub:
   ```bash
   git push -u origin feature/roster-import
   ```
6. Fill in the PR description: what changed, why, and how you tested it. Add screenshots for UI changes.
7. Wait for CI to go green and for a review. Address comments by pushing more commits to the same branch.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the review checklist.

## Useful URLs while developing

| URL | What |
| --- | ---- |
| <http://localhost:3000> | The web app |
| <http://localhost:8000/api/docs> | Interactive API docs (Swagger UI), generated from the code |
| <http://localhost:8000/api/redoc> | The same docs in a different layout |
| <http://localhost:8000/api/health> | Returns `{"status": "ok"}` if the API and database are up |

## Learning resources

- FastAPI tutorial: <https://fastapi.tiangolo.com/tutorial/>
- SQLAlchemy 2.0 ORM quick start: <https://docs.sqlalchemy.org/en/20/orm/quickstart.html>
- Next.js App Router docs: <https://nextjs.org/docs/app>
- React docs (start with "Describing the UI"): <https://react.dev/learn>
- Mantine components (browse and copy examples): <https://mantine.dev/core/button/>
- Tabler icons (search for an icon name): <https://tabler.io/icons>
