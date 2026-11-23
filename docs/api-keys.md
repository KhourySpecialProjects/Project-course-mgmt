# API keys and tokens

The workbench talks to outside services (GitHub, Linear, Anthropic, …), and each needs a key or token. Those keys are entered **in the app**, not in `.env`, and stored **encrypted** in the database.

## Three kinds of keys

| Scope | Who manages it | Where in the app | Example | Why this scope |
| ----- | -------------- | ---------------- | ------- | -------------- |
| **Personal** (`user`) | Each user, for themselves | Account → **API keys** tab. Superusers: Admin → **System settings**, under *Your API keys* | GitHub personal access token, Linear personal API key, DigitalOcean API token | Actions in GitHub/Linear/DigitalOcean happen *as that person*, with their permissions, and show up under their name. |
| **System-wide** (`system`) | Superusers | Admin → **System settings**, under *Shared API keys* | Anthropic API key, Coolify dashboard address, GitHub organization | One value the app itself uses, shared by every user. |
| **Team** (`team`) | Any logged-in user | The team's page (e.g. its Coolify panel) | A team's Coolify API token | The outside service only issues keys per team (Coolify tokens see only their own Coolify team). |

Each tool's page (GitHub, Linear, Coolify) also has an **API keys** section with just that tool's keys, to add, replace, or remove them right there, including after the tool says *Configured*.

User menu → *API keys* goes to the right place for whoever is signed in. Superusers see every key they can manage on one page, System settings, and don't get an API keys tab on their Account page.

Personal keys are private: other users, including superusers, can't see or use them. System keys are visible only to superusers in the admin portal.

## How they're stored and shown

- **Encrypted at rest.** Values are encrypted with Fernet (AES plus tamper detection) before being saved ([`api/app/core/crypto.py`](../api/app/core/crypto.py)). The encryption key comes from the `APP_SECRET_KEY` environment variable, so a copy of the database alone isn't enough to read them.
- **Write-only.** Once saved, a key is never sent back to the browser. The UI shows only that it's set, its last 4 characters (e.g. `Ends in …wxyz`), and when it was updated. To change a key, replace it.
- **Whitespace is trimmed** on save, since pasted keys often carry a stray space or newline.

### `APP_SECRET_KEY`

- Local development: the default in `.env.example` is fine.
- Production: set a long random value and keep it secret. Generate one with:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
  The API refuses to start with `ENVIRONMENT=production` and the development default.
- **If it changes, every saved key becomes unreadable.** The app doesn't crash. Affected keys show a **Needs re-entry** badge and must be entered again. So back the value up wherever you keep production secrets.

## Using a key in code

```python
from app.credentials.service import get_system_credential, get_user_credential

@router.post("/repos")
def create_repos(body: CreateReposRequest, user: CurrentUser, db: DbSession) -> ...:
    token = get_user_credential(db, user, "github_token")
    if token is None:
        raise HTTPException(400, detail="Add your GitHub token on your Account page first.")
    ...

anthropic_key = get_system_credential(db, "anthropic_api_key")
```

Both functions return `None` when nothing is saved (or the value can't be decrypted), so always handle that case with a helpful message.

Rules:

- Never log a key, put it in an error message, or return it from an endpoint.
- Read keys when you need them; don't cache them in global variables.

## Declaring a new key

Keys can't be saved unless they're declared in code. That keeps the database tidy and lets the UI describe each key.

**For a tool module**, add a `CredentialSpec` to the module's `credentials` list in `api/app/modules/<id>/module.py`:

```python
from app.credentials.spec import CredentialScope, CredentialSpec

module = ToolModule(
    id="slack",
    ...,
    credentials=[
        CredentialSpec(
            key="slack_bot_token",              # stable id; never rename once in use
            label="Slack bot token",
            description="Lets the workbench create channels in your workspace.",
            scope=CredentialScope.SYSTEM,       # or CredentialScope.USER
            help_url=None,                      # optional link to where to create one
            placeholder="xoxb-...",
        ),
    ],
)
```

**For an app-wide key** that doesn't belong to a module, add it to `CORE_CREDENTIALS` in [`api/app/credentials/registry.py`](../api/app/credentials/registry.py).

That's all. The key appears on the Account page (user scope) or in System settings (system scope) automatically, and the module's status on the dashboard reports *Not configured* until it's set. No migration is needed, because all keys share one table.

### Choosing a scope

Ask: *"When this key is used, whose identity should the outside service see?"*

- A specific person's (their repos, their Linear workspace permissions, their name on created issues) → **user**.
- The application's (a shared AI key, an organization-wide bot) → **system**.

## API endpoints

| Method & path | Who | What |
| ------------- | --- | ---- |
| `GET /api/credentials/me` | logged in | Your personal keys and whether each is set |
| `PUT /api/credentials/me/{key}` | logged in | Save or replace one: `{"value": "..."}` |
| `DELETE /api/credentials/me/{key}` | logged in | Remove one |
| `GET /api/credentials/system` | superuser | System-wide keys and whether each is set |
| `PUT /api/credentials/system/{key}` | superuser | Save or replace one |
| `DELETE /api/credentials/system/{key}` | superuser | Remove one |

## Database

One table, `credentials` ([`api/app/credentials/models.py`](../api/app/credentials/models.py)). A row with a `user_id` is a personal key; a row with `user_id = NULL` is system-wide. A unique index (with `NULLS NOT DISTINCT`) allows at most one value per user per key, and one system value per key. Deleting a user deletes their personal keys.
