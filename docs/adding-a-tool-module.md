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
from fastapi import APIRouter, Depends

from app.auth.dependencies import CurrentUser, require_user
from app.core.db import DbSession
from app.credentials.spec import CredentialScope, CredentialSpec
from app.modules.base import ToolModule, ToolStatus, status_for

# Every endpoint in this router requires a logged-in user.
router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/status", response_model=ToolStatus)
def status(user: CurrentUser, db: DbSession) -> ToolStatus:
    # Reports "configured" once every credential below is saved.
    return status_for(module, db, user)


module = ToolModule(
    id="slack",
    name="Slack",
    description="Create a channel per project team and invite its members.",
    router=router,
    credentials=[
        CredentialSpec(
            key="slack_bot_token",
            label="Slack bot token",
            description="Lets the workbench create channels in your Slack workspace.",
            scope=CredentialScope.SYSTEM,  # one shared bot for the whole app
            placeholder="xoxb-...",
        ),
    ],
)
```

The `credentials` list declares which API keys the module needs. Each one automatically appears in the UI for people to fill in: in **System settings** for `SYSTEM` scope, or on each user's **Account → API keys** tab for `USER` scope (superusers see their `USER` keys in System settings too). See [API keys and tokens](api-keys.md) for choosing a scope.

Register it in [`api/app/modules/__init__.py`](../api/app/modules/__init__.py):

```python
from app.modules.slack import module as slack

MODULES: list[ToolModule] = [
    github.module,
    linear.module,
    slack.module,
]
```

The router is now mounted at `/api/tools/slack/`. Open <http://localhost:8000/api/docs> and you should see a **slack** section with `GET /api/tools/slack/status`. As a superuser, open **System settings** and the *Slack bot token* is listed there, ready to be added.

## Step 2: Test it

Create `api/tests/test_slack.py`:

```python
def test_slack_status_requires_login(client):
    assert client.get("/api/tools/slack/status").status_code == 401


def test_slack_status_follows_system_token(client, make_user, login):
    make_user("admin@example.com", is_superuser=True)
    login("admin@example.com")
    assert client.get("/api/tools/slack/status").json()["configured"] is False

    client.put("/api/credentials/system/slack_bot_token", json={"value": "xoxb-test-token-1234"})
    assert client.get("/api/tools/slack/status").json()["configured"] is True
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
| `client.py` | **Integration adapter.** The only file that talks to the external API. Takes the token as an argument (fetched with `get_user_credential` / `get_system_credential`), and handles the base URL, pagination, rate limits, and retries. Returns plain Python objects. |
| `service.py` | **Business logic.** "Create a channel for every team in course X." Reads the course model from the database, calls `client.py`. |
| `schemas.py` | Request/response models for the endpoints. |
| `module.py` | Endpoints: validate input, call the service, return results. |

Guidelines:

- **Make bulk operations idempotent.** Running "create repos for all teams" twice should not create duplicates or fail; check what exists first and skip it. Instructors will re-run jobs after partial failures.
- **Support a dry run.** Before changing anything, an operation should be able to return a list of what it *would* do. A `dry_run: bool` parameter on the service function is a simple start.
- **Never log or return tokens.** Read them with the credentials service when needed; don't put them in responses or error messages.
- **Test without the network.** In tests, replace the client with a fake (e.g. using pytest's `monkeypatch`) so tests are fast and don't need real credentials.
- **Long operations belong in the job runner** (planned). Until it exists, keep each request short.

## Step 5 (optional): A button on every team card

If the module can make something per team (a repo, a channel, a project), give it a `team_service`. Every card in the dashboard's [Teams](teams.md) section then gets a button for it: dashed until the team has one, and clicking it calls your `create` function. Afterwards the button opens the link it returned.

```python
from sqlalchemy.orm import Session

from app.core.http import ExternalServiceError
from app.credentials.service import get_system_credential
from app.modules.base import CreatedResource, TeamService
from app.modules.slack import client
from app.teams.models import Team
from app.users.models import User


def _token(db: Session) -> str:
    token = get_system_credential(db, "slack_bot_token")
    if token is None:
        raise ExternalServiceError("Slack isn't set up yet.")
    return token


def _resource(channel: client.Channel, *, existed: bool) -> CreatedResource:
    return CreatedResource(
        url=channel.url,           # where the button goes
        external_id=channel.id,    # stable id, so one channel can't be linked to two teams
        label=f"#{channel.name}",  # for "Created the Slack channel #team-alpha."
        already_existed=existed,
    )


def find_team_channel(db: Session, user: User, team_name: str) -> CreatedResource | None:
    channel = client.find_channel(_token(db), team_name)  # your client.py; use names_match
    return _resource(channel, existed=True) if channel else None


def create_team_channel(db: Session, user: User, team: Team) -> CreatedResource:
    found = find_team_channel(db, user, team.name)
    if found is not None:
        return found
    return _resource(client.create_channel(_token(db), team.name), existed=False)


module = ToolModule(
    id="slack",
    ...,
    team_service=TeamService(
        resource_name="channel",
        summary="Creates a public channel named after the team. An existing one is linked instead.",
        create=create_team_channel,
        find=find_team_channel,
    ),
)
```

- `find` lets the **Add team** form fill in the team's link as the name is typed, and powers a card's **Find links**. It must never create anything. Pick the match with `app.core.naming.best_match`, so *Before Dawn* also finds `before-dawn` or `BeforeDawnArchitecturePatterns`, and two equally good candidates link neither.
- Provide `find`, `create`, or both. Leave `create` out for things the workbench should only find, never make (the Coolify module only finds each team's droplet, since servers cost money).
- `create` and `find` only run once every credential in the module's `credentials` list is saved; otherwise the form and the dialog tell the user what to add.
- Raise `ExternalServiceError` with a helpful message when the outside service refuses. It's shown to the user as-is, so never put a token in it.
- **Find before you create.** Look for an existing one with the team's name and return it with `already_existed=True`. Users will click after setting things up by hand.
- Make HTTP calls with `app.core.http.request_json` in your `client.py`. Tests replace it with a fake; see the `fake_http` fixture in `tests/test_teams.py`.
- The button's icon is the module's icon from `web/src/modules/registry.ts`. No other web changes are needed.

## Checklist

- [ ] `api/app/modules/<id>/module.py` exports `module`
- [ ] Added to `MODULES` in `api/app/modules/__init__.py`
- [ ] API keys the module needs are declared in its `credentials` list
- [ ] Tests in `api/tests/`
- [ ] UI in `web/src/modules/<id>/`
- [ ] Page in `web/src/app/(app)/tools/<id>/page.tsx`
- [ ] Entry in `web/src/modules/registry.ts` with the same `id` as the API module
- [ ] Optional: `team_service` for a button on every team card
- [ ] `make check` passes
