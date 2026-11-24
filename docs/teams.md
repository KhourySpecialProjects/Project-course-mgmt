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

- **Solid button (↗):** opens the link in a new tab. Hover over it to see what it points to, e.g. `KhourySpecialProjects/BeforeDawnArchitecturePatterns` or `BeforeDawn · 167.99.6.42`. The **Coolify** button opens the team's [Coolify panel](#the-team-coolify-panel) instead.
- **Dashed button (+):** the team doesn't have one yet. Click it to create (GitHub, Linear) or find (Coolify) it. The dialog explains what will happen, and you can paste a link to an existing one instead.
- **⋯ menu:**
  - *Open Coolify panel*: see below.
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

Creating the team in Coolify isn't possible from the workbench: Coolify's API has no way to create teams.

## The team Coolify panel

Each team has a page (`/teams/<id>/coolify`, from the card's Coolify button or *⋯ → Open Coolify panel*) for doing in Coolify what you'd otherwise do there or through Coolify's MCP, without switching teams.

**Connecting a team (automatic).** Coolify API tokens only see their own team, so each team needs its own token, and Coolify's API has no way to create tokens. The workbench makes them itself:

1. Once, for the whole Coolify: turn on **Settings → Advanced → API and MCP → API access**.
2. Once, for you: add a **Coolify admin token** in your API keys (System settings → *Your API keys*). It must come from your main Coolify team, the one that owns the Coolify server, and have the **root** permission.

After that, every team connects itself: when its Coolify panel opens, when the Security page opens, and right after a team (or its Coolify link) is added. With the admin token, the workbench reads Coolify's SSH key for its own server, logs in to the Coolify server (the dashboard's address, as root), and runs Coolify's own token code (`createToken`, the same as its token page) for the team's Coolify team. The Coolify team is matched by the team's droplet IP, then by name, never the main team. The new token is called **course-workbench**, belongs to an owner or admin of that Coolify team, has **read, read:sensitive, write, and deploy**, and is stored encrypted. Connecting again replaces it.

If a team can't be matched, or you'd rather not use an admin token, paste a token by hand on the team's panel: in Coolify, switch to the team, open **Keys & Tokens → API tokens**, and create one with those four permissions.

**What you can do**

| Area | Actions |
| ---- | ------- |
| Apps, databases, services | See status and where each runs (project / environment). **Redeploy** (apps: a fresh build without cache, pulling newer base images; services: pull the latest images), **restart**, **stop**, **start**. |
| Apps | **Logs** (last 500 lines), **deployments** with each one's log (and cancel a running one), **environment variables** (view, add, change, delete; locked values stay hidden). Redeploy afterwards for changes to take effect. |
| Security | Each resource's verdict from Coolify's image scans (*Update now*, *Update available*, *No fix yet*, *OK*) with critical/high/medium counts and known-exploited flags, and the full list of findings (package, version, fixed-in version, advisory). *Update now* on an app redeploys it, which is usually what fixes it. Problems in the team's own code or dependencies have to be fixed in their repository. |
| Anything else | **Advanced: Coolify API** at the bottom of the panel calls any route of the team's Coolify API with its token, the same routes Coolify's MCP uses: backups, rollbacks, scheduled tasks, domains, and so on, with examples that fill in the team's real ids. Reading is open to any logged-in user; anything other than GET needs a superuser and asks first. |
| Servers | **Auto image scans** on/off (Coolify then scans after each deploy and daily). **Check for updates** and **Install security updates** (or all updates) for the server's system packages. **Scan containers now** runs Grype, the scanner Coolify uses, on every running image. **Docker cleanup** frees disk space. |

Server updates and *Scan containers now* aren't available through Coolify's API, so the workbench logs in to the team's server over SSH **with the key Coolify keeps for it**. The key is read through the team's token (which is why that needs read:sensitive) and never stored. These run in the background and the page follows their progress. Only apt-based servers (Ubuntu/Debian) can be updated. If Docker is updated, the team's containers restart briefly. **Servers are never rebooted automatically**; the panel shows when one needs a reboot.

## Students and the team page

Click a team's name (on its card) to open **its page**, `/teams/<id>`, with three tabs:

- **Overview:** its links, its status line, and its **students**.
- **Updates:** its recent GitHub and Linear work (see below).
- **Coolify:** its Coolify panel.

**Students** have a name (required), email, GitHub username, and an optional role (e.g. "PM"). Add them one at a time, or **Paste a list**: one student per line, in the order *name, email, GitHub username, role*, separated by commas or tabs, so columns copied from a spreadsheet paste straight in. Emails, `@usernames`, and github.com links are recognized wherever they are. The same email or GitHub username can't be on a team twice; skipped lines are listed with the reason. The **Add team** form takes the same list. Team cards show students' initials.

A student's GitHub username ties their commits and pull requests to them: the Updates page's **By student** table shows each one's last commit, recent commits, and open pull requests, and names anyone committing who isn't on the list.

## Needs attention

The top of the dashboard lists what's broken or urgent across every connected team, most urgent first, each linking to the team's Coolify panel:

- **Urgent:** a production app that's stopped; an app Coolify marks *Update now* or that has a **known-exploited** vulnerability (CISA KEV); a server that isn't reachable.
- **Check:** other stopped or unhealthy apps; a server with security updates waiting (from its last update check) or needing a reboot.
- **Setup:** a team that isn't connected to Coolify, or whose Coolify can't be read.

Each team card also shows a status line: how many of its apps are running, the worst security verdict, and links to its **project repositories** (the ones its Coolify apps deploy from).

These come from one read of every team's Coolify (`GET /api/tools/coolify/summary`), done in parallel and kept for a minute so the dashboard stays fast.

## Updates and Team activity

To check on teams' work without leaving the dashboard:

- **A team's Updates page** (*⋯ → Updates* on its card, `/teams/<id>/updates`): for each of its GitHub repositories, the latest commits, open and recently merged pull requests, and open issues; and its Linear team's most recently updated issues with progress (done this week, in progress, to do). The repositories are the one linked on the card **plus every repository its Coolify apps deploy from**, so the team's real project shows up even if the card links a different repo.
- **Team activity** (sidebar, `/activity`): every team in one table, with last commit, open and merged-this-week pull requests, and Linear progress. Teams that haven't committed in a week are marked, and *Can't see* lists what your keys can't read.

Both only read, and use your own keys:

- **GitHub:** private repositories need a token that can read them. Create a fine-grained token with the course organization as **resource owner** and **Contents, Pull requests, Issues: read** (the organization may need to approve it). A token without access gets "doesn't exist" from GitHub for private repos.
- **Linear:** an API key belongs to **one workspace**. Create it while in the workspace the course uses, and make sure you can see the teams (private teams are only visible to their members and admins).

Change either key on the tool's page (**Tools → GitHub / Linear → API keys → Replace**).

## The Security page

**Tools → Coolify** shows every connected team at once: all deployed apps, most urgent first, with their security verdict and what to do (with **Redeploy** for *Update now* / *Update available*), and every team server with its system-update status (with **Check** and **Install security updates**, and **Check all servers for updates** to look on every server at once; checking never installs anything). Teams without a Coolify token are listed with a link to connect them.

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
