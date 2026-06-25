# Roadmap

PersonalD is being built in layers. This roadmap is intentionally practical: contributors should be able to pick small tasks that move the project forward.

## Near Term

- Improve config validation and friendly error messages
- Add more tests for edge cases in schedule parsing and reminders
- Make notification sound behavior easier to preview from the CLI
- Improve browser extension setup docs for Firefox, Zen, and Chromium
- Add sample screenshots or terminal recordings
- Add GitHub Actions CI for tests

## Collaboration Ready Tasks

- Document common setup problems on Arch, Ubuntu, Fedora, and NixOS
- Add more example `rules.yaml` categories
- Add tests for malformed YAML configs
- Add a command that prints the resolved config paths
- Add a command that validates config without starting the daemon
- Improve `personalctl report week` formatting
- Add lightweight JSON schema documentation for `status.json`

## Later

- Minimal GUI for schedule, focus state, next task, and reports
- Optional packaged install flow
- Optional Quickshell widget examples
- More desktop environment adapters beyond Hyprland
- Signed/published browser extension
- Import from more calendar sources

## Non-Goals

- Remote user tracking
- Forced lockout productivity behavior
- Cloud-first scheduling
- A heavy all-in-one project management suite
