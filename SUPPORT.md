# Support

PersonalD is an early open-source project. Support is community-based.

## Before Opening An Issue

Please check:

- `README.md`
- `CONTRIBUTING.md`
- Existing open issues
- Your `~/.config/personald/schedule.yaml`
- Your daemon logs:

```bash
journalctl --user -u personald.service -n 100 --no-pager
```

## Helpful Details

When asking for help, include:

- PersonalD command you ran
- Expected result
- Actual result
- Python version
- Linux distribution
- Desktop environment or window manager
- Relevant logs with private details removed

Do not paste private schedules, browser history, work URLs, meeting links, or tokens.
