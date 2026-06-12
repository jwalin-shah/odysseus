# LaunchAgents

This directory holds macOS launchd plist files for Odysseus's
scheduled jobs. They are **committed to the repo but NOT installed**
on your system. To install one, copy it to `~/Library/LaunchAgents/`
and load it explicitly.

## Files

### `com.jwalinshah.agy-quota-scraper.plist`

Runs the Antigravity UI quota scraper in `--background` mode every
10 minutes. The scraper:

- **Does not** activate Antigravity
- **Does not** open Settings (no `Cmd+,` keystroke)
- **Does not** click on the Models tab
- **Does** `screencapture -l<window_id>` of the existing window
- Writes a JSON snapshot to `/tmp/agy_quota_screenshot*.png`
- The next 10-min `quota-status` run picks up the screenshots and
  OCRs them into the canonical `quota --json` output

**Caveats / requirements:**

- You must leave Antigravity open at the Settings → Models pane.
  If you close the app or navigate away, the screencap will catch
  the wrong view.
- macOS will prompt for Screen Recording permission the first
  time. Grant it to `/Users/jwalinshah/projects/odysseus/.venv/bin/python3`
  (the interpreter that actually runs the scraper).
- The 10-minute cadence is set by `StartInterval = 600`. Tune to
  taste.

**Install:**

```sh
cp launchd/com.jwalinshah.agy-quota-scraper.plist \
   ~/Library/LaunchAgents/

# Unload any prior copy first (idempotent install).
launchctl unload ~/Library/LaunchAgents/com.jwalinshah.agy-quota-scraper.plist 2>/dev/null
launchctl load   ~/Library/LaunchAgents/com.jwalinshah.agy-quota-scraper.plist
```

**Verify:**

```sh
launchctl list | grep agy-quota
# expect a line like:
#   PID  Status  Label
#   -    0       com.jwalinshah.agy-quota-scraper

tail -f ~/.quota-status/agy-errors.log
```

**Uninstall:**

```sh
launchctl unload ~/Library/LaunchAgents/com.jwalinshah.agy-quota-scraper.plist
rm ~/Library/LaunchAgents/com.jwalinshah.agy-quota-scraper.plist
```

## Manual run (no launchd)

```sh
# Foreground mode (drives the UI, screencaptures, OCRs):
.venv/bin/python3 src/quota_scraper.py

# Background mode (no UI interaction; assumes app is open at Models pane):
.venv/bin/python3 src/quota_scraper.py --background

# Background mode with explicit window id (avoid the osascript window-find):
.venv/bin/python3 src/quota_scraper.py --background --window-id 12345
```
