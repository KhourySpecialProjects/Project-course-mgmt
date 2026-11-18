# Authentication

How login works, how to protect pages and endpoints, and how the superuser is created.

## Overview

- Users sign in with **email and password**. There is no public sign-up; superusers create accounts on the **Users** page.
- Passwords are stored as **Argon2 hashes**, never as plain text ([`api/app/core/security.py`](../api/app/core/security.py)).
- A successful login creates a row in the `auth_sessions` table and sets a **`session` cookie** in the browser.
- The cookie is **HTTP-only** (JavaScript can't read it, which limits damage from cross-site scripting) and **SameSite=Lax** (the browser won't send it on cross-site form posts, which blocks most cross-site request forgery).
- The database stores only a SHA-256 hash of the session token, so a leaked database dump can't be used to log in.
- Sessions last `SESSION_TTL_HOURS` (default 7 days). Logging out deletes the session row.

### Why server-side sessions instead of JWTs?

A session row can be deleted, which logs that browser out immediately. That makes "log out", "deactivate this user", and "changing my password logs out my other devices" simple and reliable. With JWTs those need extra machinery.

## The login flow

```
Browser                          web (Next.js)          api (FastAPI)                  db
  │ POST /api/auth/login  ─────────▶ forwards ─────────▶ check password hash ───────────▶ users
  │ {email, password}                                    create session ────────────────▶ auth_sessions
  │ ◀──────────── 200 + Set-Cookie: session=<token>; HttpOnly; SameSite=Lax
  │
  │ GET /api/auth/me  (cookie sent automatically) ─────▶ hash token, look up session ───▶ auth_sessions
  │ ◀──────────── 200 {id, email, …}   or   401 if not logged in
```

On every page load, [`AuthProvider`](../web/src/components/AuthProvider.tsx) calls `GET /api/auth/me` to learn who is logged in. Any component can read the result:

```tsx
const { user } = useAuth();
if (user?.is_superuser) { /* show admin things */ }
```

## API endpoints

| Method & path | Who | What |
| ------------- | --- | ---- |
| `POST /api/auth/login` | anyone | Check credentials, set the session cookie |
| `POST /api/auth/logout` | anyone | Delete the session, clear the cookie |
| `GET /api/auth/me` | logged in | The current user |
| `POST /api/auth/change-password` | logged in | Change own password; logs out other sessions |
| `GET /api/users` | superuser | List users |
| `POST /api/users` | superuser | Create a user |
| `PATCH /api/users/{id}` | superuser | Change name, active, superuser flag, or password |

## Protecting things

### An API endpoint

Add a `CurrentUser` or `CurrentSuperuser` parameter. FastAPI runs the check first and returns `401`/`403` if it fails:

```python
from app.auth.dependencies import CurrentUser, CurrentSuperuser

@router.get("/my-courses")
def my_courses(user: CurrentUser, db: DbSession) -> list[CourseRead]:
    ...  # `user` is the logged-in User

@router.delete("/courses/{course_id}")
def delete_course(course_id: int, admin: CurrentSuperuser, db: DbSession) -> None:
    ...
```

To protect every endpoint in a router at once:

```python
router = APIRouter(dependencies=[Depends(require_user)])
```

**The API is the real security boundary.** Hiding a button in the UI is good for usability, but always enforce permissions in the API too, because anyone can call the API directly.

### A web page

Any page under `web/src/app/(app)/` is already login-only: [`(app)/layout.tsx`](../web/src/app/(app)/layout.tsx) redirects logged-out visitors to `/login?next=<page>`, and the login page sends them back afterwards.

For superuser-only UI, check `user.is_superuser` (see [`admin/users/page.tsx`](../web/src/app/(app)/admin/users/page.tsx)).

## The superuser

Every time the API container starts, [`scripts/start.sh`](../api/scripts/start.sh) runs [`app/core/bootstrap.py`](../api/app/core/bootstrap.py), which:

- **creates** a superuser with `SUPERUSER_EMAIL` / `SUPERUSER_PASSWORD` if no user has that email, or
- if the user already exists, makes sure it is still **active and a superuser**, but **leaves the password alone**.

The second rule means a password you change in the app isn't overwritten on the next restart. It also means **editing `SUPERUSER_PASSWORD` in `.env` after the first start has no effect** on the existing account.

Superusers can't deactivate or demote themselves (a guard against locking everyone out), but they can promote other users to superuser.

### Resetting a password

From the command line (prompts for the new password, then logs the user out everywhere):

```bash
docker compose exec api python -m app.cli reset-password admin@example.com
```

or `make reset-password email=admin@example.com`.

A superuser can also set a new password for any user through the API (`PATCH /api/users/{id}` with `{"password": "…"}`).

### Creating a user from the command line

```bash
docker compose exec api python -m app.cli create-user someone@example.com --name "Some One"
```

Add `--superuser` to make them a superuser.

## Production checklist

- Use a long, random `SUPERUSER_PASSWORD`, and change it after first login.
- Serve the site over HTTPS and set `SESSION_COOKIE_SECURE=true`.
- Use strong, unique database credentials.
- Consider adding rate limiting on `/api/auth/login` (e.g. at the reverse proxy) to slow down password guessing.
