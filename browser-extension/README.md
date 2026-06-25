# PersonalD Browser Bridge

This extension sends the active tab URL/title to the local PersonalD daemon.

## Zen / Firefox

Zen is Firefox-based, so use Firefox's temporary add-on loader:

1. Open `about:debugging#/runtime/this-firefox`
2. Click "Load Temporary Add-on"
3. Select `manifest.json` inside this `browser-extension/` directory
4. Keep the PersonalD daemon running

Temporary add-ons are removed when the browser restarts. For daily use before publishing/signing, reload it from `about:debugging`.

## Chromium / Chrome

Load it unpacked in Chromium/Chrome:

1. Open `chrome://extensions`
2. Enable Developer mode
3. Click "Load unpacked"
4. Select this `browser-extension/` directory

The daemon must be running:

```bash
personalctl daemon
```

The extension posts to:

```text
http://127.0.0.1:47833/browser/activity
```
