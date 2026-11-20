# Teams

The **Teams** section of the dashboard has one card per student project team. Each card holds the team's links: its GitHub repository, Linear team, and Coolify server, plus anything else the team uses (a Figma file, a Slack channel, a docs site, ...).

```
┌──────────────────────────────────────────────┐
│ Before Dawn                              ⋯   │
│ [GitHub ↗] [Linear +] [Coolify ↗] [Figma ↗]  │
└──────────────────────────────────────────────┘
```

## Adding a team

**Add team** opens one form with everything in it. Only the name is required.

1. **Type the team's name.** As you type, the workbench uses your API keys to look for the team's repository, Linear team, and server, and fills in the links it finds (see [how names are matched](#how-names-are-matched)). Searching never creates anything.
2. **Check each service's row.** It says what was found, or why it couldn't look (e.g. a missing API key, with what to add). You can type or paste a different link into any row, or clear it.
3. **Anything not found is ticked to be created** when you add the team ("Create a new repository when adding the team"), for services that create things (GitHub and Linear). Untick it to leave it for later; the team's card will show a dashed button for it.
4. **Other links** (optional): add any number of extra links, such as Figma or Slack, each with a name.

Clicking **Add team** saves the team and its links together, then creates whatever is ticked, one service at a time. If one of those fails (say GitHub refuses), the team is still added, you get a message saying what went wrong, and the dashed button on its card lets you try again.

Something already linked to a different team is shown with a warning and not filled in.

## The team cards

- **Solid button (↗):** opens the link in a new tab. Hover over it to see what it points to, e.g. `KhourySpecialProjects/BeforeDawnArchitecturePatterns` or `BeforeDawn · 167.99.6.42`.
- **Dashed button (+):** the team doesn't have one yet. Click it to create (GitHub, Linear) or find (Coolify) it. The dialog explains what will happen, and you can paste a link to an existing one instead.
- **⋯ menu:**
  - *Find links* links everything that already exists for the team, in every service, without creating anything. Use it for teams added before their repo/team/server existed.
  - *Rename*, *Add link* (any other service), *Edit links* (change or remove links), and *Delete team*.

Any logged-in user can add, rename, and delete teams. Deleting a team, or removing a link, only changes the workbench. **Nothing is ever deleted in GitHub, Linear, Coolify, or DigitalOcean.**

## What each button does

Each one acts **as you**, with your own API keys. If a key is missing, the dialog says which one and links to where to add it (see [API keys and tokens](api-keys.md)).

| Button | Links to | Creates, if missing | Needs |
| ------ | -------- | ------------------- | ----- |
| **GitHub** | The team's repository in the course organization. | A **private repository** named after the team (*Team Alpha* → `team-alpha`), with a README so it isn't empty. | Your *GitHub personal access token*, and the *GitHub organization* (shared, set once by a superuser). To create repos, your token needs admin rights on the organization; a fine-grained token needs the organization as resource owner with **Administration: read and write**. |
| **Linear** | The team's Linear team. | A **Linear team** with the same name. Linear picks its short key (the `TEA` in `TEA-12`). | Your *Linear personal API key*. |
| **Coolify** | The course's Coolify dashboard, noting the team's server (its DigitalOcean droplet and IP address). | Nothing. Servers cost money, so the workbench only finds them. | Your *DigitalOcean API token* (read access to droplets is enough), and the *Coolify dashboard address* (shared, e.g. `https://coolify.cs4535.cloud`). |

### Coolify and DigitalOcean

The course runs **one Coolify dashboard** (the `coolify-control-plane-droplet`). Each student team is its own **Team in Coolify**, with its own DigitalOcean droplet (e.g. `BeforeDawn`) added as that team's server.

The workbench finds a team's droplet in DigitalOcean by its name or a tag, and links the team to the Coolify dashboard. **Coolify can't open a particular team from a link.** The current team is picked in Coolify's own team menu, and a link to a server page only works when that server's team is already the current one. So after clicking the button, switch to the team in Coolify.

Not possible yet:

- **Creating the team in Coolify.** Coolify's API has no way to create teams.
- **Opening the team's server page directly.** Coolify's API keys belong to one Coolify team each, so finding each team's server page would need a key from every team. It would also need **API access** turned on in Coolify (*Settings → Advanced → API and MCP*); it's currently off.

## How names are matched

Case, spaces, and punctuation never matter, so *Before Dawn*, `before-dawn`, and `BeforeDawn` are the same name. For each service, the workbench picks, in order:

1. Something named exactly after the team.
2. Otherwise, the **only** thing whose name starts with the team's name: `BeforeDawnArchitecturePatterns` for *Before Dawn*.
3. Otherwise, the **only** thing whose name contains it: `cs4535-before-dawn`.

If two things are equally good, say `BeforeDawnFrontend` and `BeforeDawnBackend`, it picks **neither**, so the wrong thing is never linked; paste the right link instead. Names shorter than 4 letters are only matched exactly. For servers, a droplet's tags count as names too.

Each button also looks before creating, so clicking it after setting things up by hand links what's there rather than making a duplicate. Clicking a button twice, or two people clicking at once, never creates two.

## Adding more services

There are two ways:

1. **From the dashboard, for one team:** use *⋯ → Add link* with any name and address. These links don't create anything; they're shortcuts.
2. **In code, for every team:** any tool module can declare a `team_service`, with a `find` function, a `create` function, or both. Its button then appears on every team card, it's searched when adding a team, and it joins *Find links*. See [Adding a tool module → A button on every team card](adding-a-tool-module.md#step-5-optional-a-button-on-every-team-card).

## How it works

| Piece | Where |
| ----- | ----- |
| Tables `teams` and `team_links` | [`api/app/teams/models.py`](../api/app/teams/models.py) |
| Endpoints under `/api/teams` | [`api/app/teams/router.py`](../api/app/teams/router.py) |
| Logic: lookup, *Find links*, creating things | [`api/app/teams/service.py`](../api/app/teams/service.py) |
| Name matching | [`api/app/core/naming.py`](../api/app/core/naming.py) |
| The `TeamService` contract a module implements | [`api/app/modules/base.py`](../api/app/modules/base.py) |
| GitHub / Linear / DigitalOcean API calls | `api/app/modules/github/client.py`, `linear/client.py`, `coolify/digitalocean.py` |
| Dashboard section, card, and dialogs | [`web/src/components/teams/`](../web/src/components/teams/) |

- A link with a `service_id` (`"github"`, ...) belongs to a built-in service; a team can have at most one per service. Its `label` says what it points to. A link with no `service_id` is a custom link; a team can have any number.
- `external_id` stores the thing's id in the outside service (repo id, Linear team id, droplet id) when the workbench found or created it. That's how it notices one repo being linked to two teams.
- Team names are unique, ignoring case.

### Endpoints

| Method & path | What |
| ------------- | ---- |
| `GET /api/teams` | All teams, with their links |
| `GET /api/teams/lookup?name=Team%20Alpha` | What each service already has for that name, and whether the name is taken. Creates nothing. |
| `POST /api/teams` | Create one, optionally with its links: `{"name": "Team Alpha", "links": [{"service_id": "github", "url": "...", "external_id": "...", "label": "org/repo"}, {"label": "Figma", "url": "..."}]}`. All or nothing. |
| `PATCH /api/teams/{id}` | Rename: `{"name": "..."}` |
| `DELETE /api/teams/{id}` | Delete it and its links |
| `POST /api/teams/{id}/links` | Add a custom link `{"label", "url"}`, or link an existing repo/... `{"service_id": "github", "url"}` |
| `PATCH /api/teams/{id}/links/{link_id}` | Change a link's `label` or `url` |
| `DELETE /api/teams/{id}/links/{link_id}` | Remove a link |
| `GET /api/teams/services` | The services that put a button on team cards, whether each can create things, and whether you have the keys for each |
| `POST /api/teams/{id}/connect` | *Find links*: link whatever already exists in each service. Creates nothing. |
| `POST /api/teams/{id}/services/{service_id}` | The dashed button: create (or find) the team's repo/team/server and link it |
