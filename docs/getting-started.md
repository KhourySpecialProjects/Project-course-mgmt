# Getting started

This guide takes you from a fresh computer to the app running in your browser. Expect it to take 10–20 minutes, most of it waiting for downloads.

## 1. Install the prerequisites

You only need two things installed. Everything else (Python, Node.js, Postgres) runs inside Docker containers, so you don't have to install or manage those yourself.

| Tool | What it's for | How to get it |
| ---- | ------------- | ------------- |
| **Git** | Downloading the code and tracking your changes | <https://git-scm.com/downloads> (macOS: run `git --version` in Terminal and accept the prompt to install it) |
| **Docker** | Running the app's three containers | [Docker Desktop](https://www.docker.com/products/docker-desktop/) for macOS and Windows. On Linux, install Docker Engine and the Compose plugin. |

After installing Docker Desktop, **start it** and wait until it reports that Docker is running. Then check both tools from a terminal:

```bash
git --version
```

```bash
docker compose version
```

Each should print a version number. If `docker compose version` fails, Docker isn't running yet.

> **Windows users:** run the commands in this guide from a WSL 2 terminal (Ubuntu) or Git Bash. Docker Desktop's installer can set up WSL 2 for you.

### Optional, but recommended

- **An editor.** [VS Code](https://code.visualstudio.com) works well. Useful extensions: *Python*, *Pylance*, *Ruff*, *ESLint*, *Prettier*, *Docker*.
- **`make`.** Lets you use the shortcuts in the [Makefile](../Makefile) (`make up`, `make test`, …). It is preinstalled on macOS and most Linux systems. Without it, every shortcut has an equivalent `docker compose` command, shown in the Makefile and in these docs.
- **[uv](https://docs.astral.sh/uv/) and [Node.js 22](https://nodejs.org).** Only needed if you want your editor's autocomplete and type checking to see the installed libraries. See [Editor setup](#editor-setup-optional) below.

## 2. Get the code

```bash
git clone https://github.com/KhourySpecialProjects/Project-course-mgmt.git
```

```bash
cd Project-course-mgmt
```

## 3. Create your `.env` file

Configuration (passwords, ports, API tokens) lives in a file called `.env` in the project root. It is **not** committed to git, so each person has their own. Start from the example:

```bash
cp .env.example .env
```

Open `.env` in your editor. For local development the defaults work as-is, but take a look at:

- `SUPERUSER_EMAIL` and `SUPERUSER_PASSWORD`: the account you'll log in with. It is created automatically the first time the app starts.
- `POSTGRES_PORT`: change this if something else on your machine already uses port 5432.

## 4. Start the app

```bash
docker compose up --build
```

(or `make up`, which runs it in the background).

The first run downloads base images and installs dependencies, which takes a few minutes. Later starts take seconds. You'll see interleaved logs from three services, `db`, `api`, and `web`. It's ready when you see a line like:

```
web-1  |  ✓ Ready in 1.2s
```

Leave this terminal open; it shows the logs. Press `Ctrl+C` to stop everything.

## 5. Log in

Open <http://localhost:3000>. You'll be sent to the sign-in page. Use the `SUPERUSER_EMAIL` and `SUPERUSER_PASSWORD` from your `.env` file.

Things to try:

- **Users** (left sidebar, under *Admin*): add a second account, then sign in as that person in a private browser window. Non-superusers don't see the Admin section.
- **Account** (menu under your name, top right): change your password.
- **The moon/sun button** (top right): switch between light and dark mode.
- **API docs** at <http://localhost:8000/api/docs>: every API endpoint, with a *Try it out* button. Endpoints that need a login use the session cookie. Browsers share cookies between ports on the same host, so once you're signed in at `localhost:3000`, the docs page can call protected endpoints too. You can also sign in from the docs page with `POST /api/auth/login`.

## 6. Stop and restart

| To… | Run |
| --- | --- |
| Stop (data is kept) | `Ctrl+C` in the logs terminal, or `docker compose down` |
| Start again | `docker compose up` (add `--build` after dependency changes) |
| Start in the background | `docker compose up -d`, then `docker compose logs -f` to watch logs |
| Wipe the database and start fresh | `docker compose down -v` (the `-v` deletes the data volume) |

## Editor setup (optional)

The code runs inside containers, but your editor runs on your machine. To get autocomplete and inline type errors, install the dependencies locally as well:

```bash
cd api && uv sync
```

Then point your editor's Python interpreter at `api/.venv`.

```bash
cd web && npm install
```

These local installs are only for your editor. The containers keep their own copies, so the two never conflict.

## Next steps

- Read [Architecture](architecture.md) for a tour of the codebase.
- Read [Development workflow](development-workflow.md) before your first change.
- If anything went wrong, check [Troubleshooting](troubleshooting.md).
