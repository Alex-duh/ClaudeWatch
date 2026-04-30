# Claude Pro Usage Tracker

A macOS menu bar app that shows your Claude Pro session and weekly usage in real time — no browser tab required after setup.

```
Claude S:71%  W:14%
  ┌──────────────────────────────┐
  │ Session:  ███████▒▒▒  71%   │
  │   ↺ resets  in 6 min        │
  │ ─────────────────────────── │
  │ Weekly:   █▒▒▒▒▒▒▒▒▒  14%  │
  │   ↺ resets  Thu 12:00 AM    │
  │ ─────────────────────────── │
  │ Last updated:  Apr 30 14:22 │
  │ ─────────────────────────── │
  │ Open Settings               │
  │ Quit                        │
  └──────────────────────────────┘
```

**S** = current session · **W** = weekly across all models

---

## How it works

Two pieces work together:

1. **Chrome extension** — runs silently in the background, opens `claude.ai/settings/usage` every 3 minutes, scrapes your usage numbers, and sends them to your Mac over a local HTTP connection.

2. **Menu bar app** — a Python app that listens for that data and keeps your menu bar up to date. Remembers the last reading across restarts, so it always shows something immediately.

```
chrome.ai/settings/usage
        │
   content.js  (reads the page)
        │
   POST :9999  (local only, never leaves your machine)
        │
   Flask server  ──▶  rumps menu bar
                            │
                   ~/.claude_usage.json  (saved to disk)
```

---

## Requirements

- macOS 12 or later
- Python 3.9 or later (`python3 --version` to check)
- Google Chrome
- Claude Pro account

---

## Setup

There are two parts. Do them in any order, but you need both running for it to work.

---

### Part 1 — Menu bar app (one-time install)

This installs the app as a **login item** — it will start automatically every time you log in, with no terminal window needed.

```bash
cd menubar
bash install.sh
```

That's it. `Claude —` appears in your menu bar within a few seconds. After the next reboot it will start on its own before you open anything else.

> **To stop or uninstall:**
> ```bash
> launchctl unload ~/Library/LaunchAgents/com.claudetracker.menubar.plist
> ```

> **To restart after making code changes:**
> ```bash
> launchctl unload ~/Library/LaunchAgents/com.claudetracker.menubar.plist
> launchctl load ~/Library/LaunchAgents/com.claudetracker.menubar.plist
> ```

---

### Part 2 — Chrome extension

1. Open Chrome and go to **`chrome://extensions`**
2. Turn on **Developer mode** (toggle in the top-right corner)
3. Click **Load unpacked**
4. Select the **`extension/`** folder inside this project (not the root folder)
5. The extension is now active — no icon or popup, it works silently

---

### First data reading

Navigate to **`claude.ai/settings/usage`** once. The extension scrapes the page and sends the data immediately — your menu bar updates within a few seconds and shows real numbers.

After that, the extension automatically refreshes in the background every 3 minutes. You don't need to keep that tab open.

---

## Update schedule

| What triggers an update | When |
|---|---|
| You visit `claude.ai/settings/usage` | Instantly on page load |
| Background auto-refresh | Every 3 minutes (extension opens a silent background tab) |
| You navigate to `/settings/usage` within claude.ai | Detected automatically |

Your last known data is always saved to `~/.claude_usage.json`, so the menu bar shows real numbers immediately after a restart — even before the next scrape.

---

## Files

```
UsageTracker/
├── extension/
│   ├── manifest.json          # Chrome MV3 manifest
│   ├── content.js             # Scrapes the settings page, POSTs to Flask
│   └── background.js          # Opens/reloads settings tab every 3 min
│
├── menubar/
│   ├── app.py                 # Flask server + rumps menu bar app
│   ├── requirements.txt       # Python dependencies (rumps, flask)
│   ├── install.sh             # One-time setup: venv + login item registration
│   ├── start.sh               # Manual launch (for dev/testing without launchd)
│   └── com.claudetracker.menubar.plist   # launchd config (used by install.sh)
│
├── .gitignore
└── README.md
```

---

## Troubleshooting

**Menu bar shows `Claude —` and won't update**
→ Visit `claude.ai/settings/usage` manually to trigger the first scrape.
→ Check that the menu bar app is running: `launchctl list | grep claudetracker`

**`[ClaudeTracker] Server unreachable` in Chrome DevTools console**
→ The menu bar app isn't running. Re-run `install.sh` or load the plist manually:
```bash
launchctl load ~/Library/LaunchAgents/com.claudetracker.menubar.plist
```

**Port 9999 is already in use**
```bash
lsof -ti:9999 | xargs kill -9
launchctl load ~/Library/LaunchAgents/com.claudetracker.menubar.plist
```

**Extension not appearing after load**
→ Make sure Developer mode is on and you selected the `extension/` subfolder, not the project root.

**Scraper stops working after a Claude UI update**
→ Claude's settings page HTML changes occasionally. Open `extension/content.js` and update the regex patterns in `parseUsage()` to match whatever text the page now shows. The `[ClaudeTracker]` log lines in the DevTools console will show what the script found (or didn't).

**Checking logs**
```bash
tail -f /tmp/claudetracker.log   # stdout
tail -f /tmp/claudetracker.err   # errors
```
