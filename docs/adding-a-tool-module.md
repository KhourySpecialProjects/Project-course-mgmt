# Adding a tool module

A **tool module** is one integration, like GitHub or Linear. Each module is self-contained: its API endpoints, external-API client, and UI pages live in their own folders, and the core app only needs one line in a registry to pick it up.

This guide builds a small example module called **Slack** end to end. Follow the same steps for real modules, or use them to flesh out the existing `github` and `linear` placeholders.

## What you'll create

```
api/app/modules/slack/
├── __init__.py          (one-line docstring)
└── module.py            Router + endpoints + ToolModule definition

web/src/modules/slack/
└── SlackToolPage.tsx    The module's UI

web/src/app/(app)/tools/slack/
└── page.tsx             Thin page file that renders SlackToolPage
```

Plus one line each in the two registries.

## Step 1: The API module

Create `api/app/modules/slack/__init__.py`:

```python
"""Slack tool module: channel setup for project teams."""
```

Create `api/app/modules/slack/module.py`. Start by copying `api/app/modules/github/module.py`, then adapt it:

```python
import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import require_user
from app.modules.base import ToolModule

# Every endpoint in this router requires a logged-in user.
router = APIRouter(dependencies=[Depends(require_user)])


def is_configured() -> bool:
    return bool(os.environ.get("SLACK_BOT_TOKEN"))


class SlackStatus(BaseModel):
    configured: bool
    message: str


@router.get("/status", response_model=SlackStatus)
def status() -> SlackStatus:
    if is_configured():
        return SlackStatus(configured=True, message="Slack token found.")
    return SlackStatus(configured=False, message="Set SLACK_BOT_TOKEN in .env.")


module = ToolModule(
    id="slack",
    name="Slack",
    description="Create a channel per project team and invite its members.",
    router=router,
    is_configured=is_configured,
)
```

Register it in [`api/app/modules/__init__.py`](../api/app/modules/__init__.py):

```python
from app.modules.slack import module as slack

MODULES: list[ToolModule] = [
    github.module,
    linear.module,
    slack.module,
]
```

The router is now mounted at `/api/tools/slack/`. Open <http://localhost:8000/api/docs> and you should see a **slack** section with `GET /api/tools/slack/status`.

Add the new setting to [`.env.example`](../.env.example) (with an empty value) so teammates know it exists. Then add it to your own `.env` and restart the API container (`docker compose up -d api`), because environment variables are only read at start-up.

## Step 2: Test it

Create `api/tests/test_slack.py`:

```python
def test_slack_status_requires_login(client):
    assert client.get("/api/tools/slack/status").status_code == 401


def test_slack_status(client, make_user, login):
    make_user("someone@example.com")
    login("someone@example.com")
    r = client.get("/api/tools/slack/status")
    assert r.status_code == 200
    assert r.json()["configured"] in (True, False)
```

Then update the expected set of ids in `test_tools_listing` in `tests/test_bootstrap_and_tools.py`, and run `make test`.

## Step 3: The UI

Create `web/src/modules/slack/SlackToolPage.tsx`. While a module is still a placeholder, the shared `ToolPlaceholder` component does the work:

```tsx
"use client";

import { ToolPlaceholder } from "@/components/ToolPlaceholder";

export function SlackToolPage() {
  return (
    <ToolPlaceholder
      toolId="slack"
      title="Slack"
      intro="Create a Slack channel for each project team."
      planned={["Create one channel per team", "Invite team members to their channel"]}
    />
  );
}
```

Create the page at `web/src/app/(app)/tools/slack/page.tsx`. Because it's inside `(app)/`, it's automatically login-protected and gets the sidebar:

```tsx
import { SlackToolPage } from "@/modules/slack/SlackToolPage";

export default function Page() {
  return <SlackToolPage />;
}
```

Register it in [`web/src/modules/registry.ts`](../web/src/modules/registry.ts). Pick an icon at <https://tabler.io/icons> (the React component name is `Icon` + the name in PascalCase):

```ts
import { IconBrandGithub, IconBrandSlack, IconLayoutKanban, type Icon } from "@tabler/icons-react";

export const toolModules: ToolModuleEntry[] = [
  { id: "github", name: "GitHub", href: "/tools/github", icon: IconBrandGithub },
  { id: "linear", name: "Linear", href: "/tools/linear", icon: IconLayoutKanban },
  { id: "slack", name: "Slack", href: "/tools/slack", icon: IconBrandSlack },
];
```

Refresh the browser. **Slack** appears in the sidebar and on the dashboard with a *Not configured* badge.

## Step 4: Real functionality

When the module does real work, keep the same layering used in the rest of the API:

| File | Responsibility |
| ---- | -------------- |
| `client.py` | **Integration adapter.** The only file that talks to the external API. Handles the token, base URL, pagination, rate limits, and retries. Returns plain Python objects. |
| `service.py` | **Business logic.** "Create a channel for every team in course X." Reads the course model from the database, calls `client.py`. |
| `schemas.py` | Request/response models for the endpoints. |
| `module.py` | Endpoints: validate input, call the service, return results. |

Guidelines:

- **Make bulk operations idempotent.** Running "create repos for all teams" twice should not create duplicates or fail; check what exists first and skip it. Instructors will re-run jobs after partial failures.
- **Support a dry run.** Before changing anything, an operation should be able to return a list of what it *would* do. A `dry_run: bool` parameter on the service function is a simple start.
- **Never log or return tokens.** Read them from settings/environment; don't put them in responses or error messages.
- **Test without the network.** In tests, replace the client with a fake (e.g. using pytest's `monkeypatch`) so tests are fast and don't need real credentials.
- **Long operations belong in the job runner** (planned). Until it exists, keep each request short.

## Checklist

- [ ] `api/app/modules/<id>/module.py` exports `module`
- [ ] Added to `MODULES` in `api/app/modules/__init__.py`
- [ ] New settings documented in `.env.example`
- [ ] Tests in `api/tests/`
- [ ] UI in `web/src/modules/<id>/`
- [ ] Page in `web/src/app/(app)/tools/<id>/page.tsx`
- [ ] Entry in `web/src/modules/registry.ts` with the same `id` as the API module
- [ ] `make check` passes
