# Project Course Management Workbench

A web app for instructors running practicum / project-based courses. It is one place to do the setup and monitoring work that otherwise takes hundreds of clicks across GitHub and Linear.

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

### Future tools

New tools plug into the workbench without changes to the core. Possible additions: Slack or Discord channel setup, grading or peer-evaluation exports, and LMS roster import.

## Architecture

The design is modular:

- **Core shell**: authentication, navigation, course and roster model, and shared UI components.
- **Course model**: the shared source of truth. It holds the course, its students, its teams, and its projects. Every tool reads from it and writes to it.
- **Tool modules**: each integration (GitHub, Linear, …) is a self-contained module. A module registers its own routes, UI pages, API client, and actions with the shell.
- **Integration adapters**: thin wrappers around each external API. They handle auth tokens, rate limits, and idempotent retries, so a bulk job can be safely run again.
- **Job runner**: runs long bulk operations in the background, with progress, logs, and a dry-run preview before any changes are made.

To add a tool, create a new module that uses the course model and registers with the shell.

## Status

Early planning.
