# Contributing

Thanks for working on the Course Management Workbench. This page covers how changes get from your branch into `main`. For day-to-day commands, see [docs/development-workflow.md](docs/development-workflow.md).

## Workflow

1. Branch from an up-to-date `main`: `git checkout -b feature/short-description` (or `fix/…`, `docs/…`).
2. Make focused commits. One pull request should do one thing; split large features into a series of smaller PRs.
3. Run `make check` (lint, type checks, tests) before pushing.
4. Push and open a pull request against `main`.
5. CI must be green and at least one reviewer must approve before merging.

## Pull request checklist

Copy this into your PR description and tick what applies:

```markdown
## What and why
<!-- What does this change, and why is it needed? Link the issue if there is one. -->

## How I tested it
<!-- Commands you ran, pages you clicked through. Screenshots for UI changes. -->

## Checklist
- [ ] `make check` passes locally
- [ ] New/changed API endpoints have tests (success + not-allowed cases)
- [ ] Permissions are enforced in the API, not only hidden in the UI
- [ ] Model changes come with a reviewed Alembic migration
- [ ] New server settings are added to `.env.example`; new third-party keys are declared as `CredentialSpec`s (never commit real secrets)
- [ ] Docs updated if behavior or setup changed
```

## Conventions

**Python (api/)**

- Type-hint everything; `mypy --strict` runs in CI.
- Keep HTTP code in `router.py`/`module.py` and logic in `service.py` so it can be reused and tested.
- Formatting and import order are handled by `ruff format` / `ruff check --fix` (`make format`).

**TypeScript (web/)**

- Use Mantine components before writing custom CSS. Browse <https://mantine.dev>.
- Call the API only through `src/lib/api.ts`, and add response types to `src/lib/types.ts`.
- Formatting is handled by Prettier (`make format`).

**Commits**

- Write messages in the imperative mood that explain the change: "Add roster CSV upload", not "stuff" or "fixed it".

**Secrets**

- Never commit `.env`, API tokens, or passwords. If you accidentally do, tell the team right away so the secret can be revoked. Deleting it in a later commit does not remove it from git history.
