# Troubleshooting

Start by looking at the logs. Most problems explain themselves there:

```bash
docker compose logs --tail=50 api
```

```bash
docker compose logs --tail=50 web
```

```bash
docker compose ps
```

`docker compose ps` shows each container's state. `healthy` or `running` is good; `restarting` or `exited` means it crashed, and its logs say why.

---

### `Cannot connect to the Docker daemon` / `docker: command not found`

Docker Desktop isn't running (or isn't installed). Start it and wait until it reports Docker is running, then retry.

### `port is already allocated` / `address already in use`

Something else on your computer is using port 3000, 8000, or 5432.

- **Port 5432** (often a Postgres you installed separately): set `POSTGRES_PORT=5433` in `.env`, then `docker compose up -d`.
- **Port 3000 or 8000**: stop the other program, or change the left-hand number of the `ports:` mapping in `docker-compose.yml` (e.g. `"3001:3000"`) and use that port in your browser.

### The login page says "Invalid email or password" for the superuser

- Check `SUPERUSER_EMAIL` / `SUPERUSER_PASSWORD` in `.env`.
- If you changed `SUPERUSER_PASSWORD` **after** the first start, the existing account kept its original password (by design, see [Authentication](authentication.md#the-superuser)). Reset it:
  ```bash
  docker compose exec api python -m app.cli reset-password admin@example.com
  ```

### The web app shows errors for every `/api` request, or `500` errors

The API container is probably down or still starting. Check `docker compose ps` and `docker compose logs api`. Common causes:

- **A Python error in your code.** The API log shows a traceback. The bottom lines name the file and line. Fix it and save; the server reloads by itself.
- **A migration failed.** See below.

### `alembic` errors on start-up, e.g. `Can't locate revision` or `relation already exists`

Your local database is out of step with the migration files (common after switching branches that have different migrations).

- If you don't need your local data, reset it: `docker compose down -v`, then `docker compose up -d`.
- Otherwise, check `docker compose exec api alembic current` and `alembic history` and talk it through with a teammate before editing anything.

### I added a package but get `ModuleNotFoundError` / `Module not found`

The container still has the old dependencies. Rebuild it:

```bash
docker compose up -d --build api
```

```bash
docker compose up -d --build -V web
```

(`-V` gives the web container a fresh `node_modules`.)

### My changes don't show up

- **API:** check `docker compose logs api` for a line like `WatchFiles detected changes ... Reloading`. If it's missing, restart the container with `docker compose restart api`.
- **Web:** try a hard refresh (`Cmd+Shift+R` on macOS, `Ctrl+Shift+R` elsewhere). The container checks for file changes by polling (`WATCHPACK_POLLING` in `docker-compose.yml`), so updates can take a second or two to appear.
- Make sure you edited the file in this project folder and saved it.

### The web container is slow on macOS or Windows

Docker Desktop shares files between your computer and the containers through a virtual machine, which slows Next.js down. Options:

- Run only the web app on your machine and keep the API and database in Docker:
  ```bash
  docker compose up -d db api
  ```
  ```bash
  cd web && npm install && npm run dev
  ```
  The web app at <http://localhost:3000> forwards `/api` to `localhost:8000` by default, so no other changes are needed.
- On Windows, keep the project inside the WSL 2 filesystem (e.g. `~/code/...`), not under `/mnt/c/...`.

### Tests fail with `database "coursemgmt_test" does not exist`

The test database is created the first time the Postgres volume is initialized. If your volume predates that script (or you renamed `POSTGRES_DB`), create it once:

```bash
docker compose exec db sh -c 'createdb -U "$POSTGRES_USER" "${POSTGRES_DB}_test"'
```

### Everything is broken and I want a clean slate

This deletes your local database and rebuilds everything from scratch:

```bash
docker compose down -v --remove-orphans
```

```bash
docker compose up --build
```

### Still stuck?

Collect the exact command you ran, the full error message, and the output of `docker compose ps`. Open an issue or message the team with those. It makes the problem much faster to diagnose.
