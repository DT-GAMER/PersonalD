# Security Policy

PersonalD is local-first software that can observe schedules, active windows, and browser tab metadata. Please treat privacy and local data safety as core parts of the project.

## Supported Versions

PersonalD is pre-1.0. Security fixes should target the latest `main` branch unless a release branch exists.

## Reporting A Vulnerability

If you find a vulnerability, please do not publish sensitive details immediately.

Open a GitHub issue only if the report can be described safely without exposing private user data or an exploit path. Otherwise, contact a maintainer privately. Maintainer contact details should be added here before the project is widely promoted.

## Sensitive Areas

Please be extra careful with changes involving:

- Browser bridge endpoints
- Activity tracking
- Schedule and calendar files
- Local SQLite storage
- Shell command execution
- Environment actions that open apps, URLs, or close windows

## Project Safety Principles

- No remote telemetry by default
- No upload of schedules, browser activity, or window titles
- Keep the browser bridge bound to localhost unless explicitly redesigned
- Avoid destructive actions without clear user intent
- Prefer dry-run modes for actions that affect the desktop
