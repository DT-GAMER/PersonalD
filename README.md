# PersonalD

PersonalD is a local Linux daemon for planning, focus, reminders, browser activity, and lightweight time awareness.

It was built for a busy work-and-study workflow: keep the schedule close, show what is next, send timely reminders, watch for focus drift, and stay useful without locking the user out of their own machine.

## Features

- YAML-based weekly schedule, one-off events, deadlines, and study targets
- Desktop notifications with optional attention sound
- Gentle focus sessions with drift reminders
- Hyprland active-window activity tracking
- Local browser bridge for active tab context
- Daily plan generation and editing
- Local calendar import from `.ics` files
- Daily and weekly activity reports
- JSON status output for bars, widgets, and shells
- Optional Quickshell integration

PersonalD is not a strict blocker. It does not force pages open, lock apps, or prevent you from closing anything. It is designed to nudge, remind, and reflect your day back to you.

## Project Status

PersonalD is early, usable, and evolving. The core CLI, daemon, schedule reminders, focus sessions, browser bridge, reports, and local storage are working, but the project is still pre-1.0.

Contributors are welcome. Good starting points are documentation, tests, config validation, desktop compatibility, browser bridge improvements, and small CLI quality-of-life fixes.

## Requirements

- Linux
- Python 3.11+
- `notify-send` for desktop notifications
- `hyprctl` for Hyprland activity tracking and environment actions
- `paplay`, `pw-play`, `aplay`, `ffplay`, `mpv`, or `canberra-gtk-play` for notification sounds

Hyprland is recommended for the activity and environment features. Schedule, reminders, planning, browser bridge, calendar import, and reports can still work without Quickshell.

## Install

Clone the repo:

```bash
git clone https://github.com/DT-GAMER/PersonalD.git
cd PersonalD
```

Install the command locally with `pipx`:

```bash
pipx install -e .
```

On Arch-based systems, install `pipx` first if needed:

```bash
sudo pacman -S python-pipx
pipx ensurepath
```

Make sure `~/.local/bin` is in your `PATH`, then check:

```bash
personalctl --help
```

For development without installing:

```bash
./personalctl --help
```

You can also use a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Configure

PersonalD reads its main schedule from:

```text
~/.config/personald/schedule.yaml
```

Start from the example:

```bash
mkdir -p ~/.config/personald
cp config-examples/schedule.yaml ~/.config/personald/schedule.yaml
cp config-examples/rules.yaml ~/.config/personald/rules.yaml
```

Edit the schedule:

```bash
$EDITOR ~/.config/personald/schedule.yaml
```

Preview your day:

```bash
personalctl today
personalctl status
personalctl next
personalctl reminders
```

## Run The Daemon

Check once without sending real desktop notifications:

```bash
personalctl daemon --once --dry-run
```

Run it manually:

```bash
personalctl daemon
```

Install the user service:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/personald.service ~/.config/systemd/user/personald.service
systemctl --user daemon-reload
systemctl --user enable --now personald.service
```

View logs:

```bash
journalctl --user -u personald.service -f
```

Restart after config changes:

```bash
systemctl --user restart personald.service
```

## Notification Sound

Notification sound is configured inside `notifications.sound`:

```yaml
notifications:
  enabled: true
  poll_seconds: 60
  sound:
    enabled: true
    file: /usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga
    repeat: 2
```

Set `enabled: false` to disable sound, or change `file` to a custom `.oga`, `.ogg`, or `.wav`.

## Common Commands

```bash
personalctl status
personalctl today
personalctl next
personalctl schedule
personalctl reminders

personalctl activity now
personalctl activity track --once
personalctl activity summary

personalctl focus list
personalctl focus start mba_study --minutes 50
personalctl focus pause
personalctl focus resume
personalctl focus stop
personalctl focus status

personalctl plan today
personalctl plan accept
personalctl plan add "Read chapter 4" --at 20:00 --minutes 45 --type study
personalctl plan done s1
personalctl plan skip current
personalctl plan move current --to 21:00

personalctl browser latest
personalctl calendar import ~/Downloads/school.ics --name school
personalctl calendar upcoming

personalctl env list
personalctl env start mba_study --dry-run

personalctl report today
personalctl report week

personalctl ui status
personalctl ui write-status
```

## Browser Bridge

PersonalD listens locally on:

```text
http://127.0.0.1:47833
```

The extension in `browser-extension/` sends active tab URL and title events to the daemon.

For Zen/Firefox:

1. Open `about:debugging#/runtime/this-firefox`
2. Click `Load Temporary Add-on`
3. Select `browser-extension/manifest.json`
4. Keep `personalctl daemon` running

For Chromium/Chrome:

1. Open `chrome://extensions`
2. Enable Developer Mode
3. Click `Load unpacked`
4. Select `browser-extension/`

## Quickshell Integration

PersonalD does not require Quickshell.

For shells, bars, or widgets, PersonalD writes status JSON to:

```text
~/.local/state/personald/status.json
```

Generate it manually:

```bash
personalctl ui write-status
```

The daemon also refreshes this file while running. A Quickshell rice can read the JSON and display the current block, next block, focus state, and activity context.

## Privacy

PersonalD stores data locally by default:

```text
~/.config/personald/
~/.local/state/personald/
```

The browser bridge posts to `127.0.0.1` only. It does not send activity to a remote server.

Do not commit your real `~/.config/personald/schedule.yaml` if it contains private class, work, or meeting details. Use `config-examples/schedule.yaml` as the public template.

## Contributing

PersonalD welcomes thoughtful contributions.

Start here:

- [Contributing guide](CONTRIBUTING.md)
- [Roadmap](ROADMAP.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md)
- [Support guide](SUPPORT.md)

Good first contributions include:

- Fixing unclear docs
- Adding tests for edge cases
- Improving config examples
- Improving error messages
- Adding platform notes for different Linux distributions
- Helping make optional integrations cleaner

## Hacktoberfest

PersonalD can be prepared for Hacktoberfest by:

- Adding the `hacktoberfest` topic to the GitHub repository
- Labeling selected issues with `hacktoberfest`
- Keeping beginner issues small, useful, and well-scoped
- Reviewing PRs promptly and kindly

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a Hacktoberfest PR. Low-effort spam PRs will be closed, but meaningful docs, tests, bug fixes, and examples are welcome.

## Test

```bash
python -m unittest discover tests
```
