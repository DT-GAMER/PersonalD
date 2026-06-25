# Contributing To PersonalD

Thanks for wanting to help with PersonalD.

PersonalD is a local-first Linux productivity daemon. The project is still young, so thoughtful issues, docs, tests, small bug fixes, and integration ideas are all valuable.

## Ways To Contribute

- Improve documentation and examples
- Add tests for schedule, focus, browser, calendar, or report behavior
- Fix bugs in the CLI or daemon loop
- Improve Linux desktop compatibility beyond Hyprland
- Add safer config validation and better error messages
- Improve the browser bridge
- Build optional integrations for shells, bars, widgets, or GUIs

## Development Setup

Clone the repo:

```bash
git clone https://github.com/DT-GAMER/PersonalD.git
cd PersonalD
```

Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Copy example config:

```bash
mkdir -p ~/.config/personald
cp config-examples/schedule.yaml ~/.config/personald/schedule.yaml
cp config-examples/rules.yaml ~/.config/personald/rules.yaml
```

Run the CLI:

```bash
personalctl --help
personalctl today
personalctl daemon --once --dry-run
```

Run tests:

```bash
python -m unittest discover tests
```

## Pull Request Checklist

Before opening a PR:

- Keep the change focused and easy to review
- Add or update tests when behavior changes
- Update docs or examples if user-facing behavior changes
- Run `python -m unittest discover tests`
- Do not commit private schedules, local databases, state files, browser history, or machine-specific config

## Issue Labels

Useful labels for maintainers:

- `good first issue`: small, well-scoped tasks for new contributors
- `help wanted`: useful tasks where maintainers welcome outside help
- `bug`: confirmed broken behavior
- `docs`: documentation-only work
- `enhancement`: new or improved behavior

## Project Boundaries

PersonalD should stay local-first and user-controlled.

- Do not add remote telemetry
- Do not upload activity data to third-party services by default
- Do not make focus mode lock the user out of their system
- Prefer gentle reminders and transparent behavior
- Keep optional desktop-specific integrations separate from the core daemon

## Asking For Help

If you are stuck, open a draft PR or comment on the issue with:

- What you tried
- What happened
- What you expected
- Your OS, Python version, and desktop environment if relevant
