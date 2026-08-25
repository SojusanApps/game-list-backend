# AI Agent Instructions for GameList Backend

Welcome, AI coding agent! Follow these guidelines to ensure consistency and correctness in this repository.

## Environment & Tooling

- **Python Version:** 3.14+
- **Framework:** Django 6.0+ with Django REST Framework.
- **Package Management:** Use [`uv`](https://docs.astral.sh/uv). Never use `pip` implicitly. Run `uv sync --all-extras` to install and `uv run <command>` to execute.
- **Task Runner:** Utilize the project's `justfile`. Run `just --list` to see available commands.

## Code Quality & Style

- **Formatting:** Enforce strict PEP8 with a line length of 120. Code is checked by `black` and `ruff`. Type checking is done by `mypy --strict`.
- **Validation:** Always validate changes with `just check` before concluding your work.

## Testing & Coverage

- **Framework:** Use `pytest` via `just test` or `tox`. Target test coverage must remain >90%.
- **Dependencies:** Tests and local execution require an active PostgreSQL instance.
  - To test: Start the test DB with `just test_db` beforehand.
  - To run app locally: Start the app DB with `just app_db` first, then `just fresh_run` or `just run`.

## Working Methodology

- **Branches:** Base new features off the `devel` branch using the format `[bugfix|feature|hotfix]/[description]`. The `master` branch is strictly for stable production code.
- **Documentation:** Don't duplicate instructions. For detailed deploy and local install scenarios, direct users to the [README.md](./README.md).

## Agent skills

### Issue tracker

Issues live as local markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the default five-role label vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
