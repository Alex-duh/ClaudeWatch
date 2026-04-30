# Claude Pro Usage Tracker

A lightweight macOS menu bar app that shows your Claude Pro usage at a glance — no browser tab needed.

```
Claude S:71%  W:14%
  Session:  ███████░░░  71%
    ↺ resets  in 6 min
  ─────────────────────────
  Weekly:   █░░░░░░░░░  14%
    ↺ resets  Thu 12:00 AM
  ─────────────────────────
  Last updated:  Apr 30 14:22
  ─────────────────────────
  Open Settings
  Quit
```

**S** = current session usage · **W** = weekly usage

---

## How it works

A Chrome extension scrapes the usage data from `claude.ai/settings/usage` and POSTs it to a tiny Flask server running on your Mac. A `rumps`-based menu bar app reads that data and displays it in the status bar, updating every 3 minutes automatically.

```
claude.ai/settings/usage
        │
   content.js (DOM scrape)
        │
   POST /usage (JSON)
        │
   Flask :9999  ──▶  rumps menu bar
                           │
                   ~/.claude_usage.json  (persists across restarts)
```

---

## Requirements

- macOS 12+
- Python 3.9+
- Google Chrome
- A Claude Pro account

---

## Setup

### Part 1 — macOS Menu Bar App

```bash
cd menubar
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

`Claude —` appears in your menu bar immediately. Keep this terminal open, or see [Auto-start on login](#auto-start-on-login) below.

### Part 2 — Chrome Extension

1. Open Chrome and go to `chrome://extensions`
2. Enable **Developer mode** (toggle, top right)
3. Click **Load unpacked** and select the `extension/` folder in this project
4. Navigate to `claude.ai/settings/usage` — data appears in the menu bar within a few seconds

---

## Auto-start on login

So the app runs automatically without a terminal:

```bash
# Edit the paths below to match your username
cat > ~/Library/LaunchAgents/com.claudetracker.menubar.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.claudetracker.menubar</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/YOUR_USERNAME/Documents/Projects/UsageTracker/menubar/.venv/bin/python</string>
    <string>/Users/YOUR_USERNAME/Documents/Projects/UsageTracker/menubar/app.py</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/claudetracker.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/claudetracker.err</string>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.claudetracker.menubar.plist
```

To stop it: `launchctl unload ~/Library/LaunchAgents/com.claudetracker.menubar.plist`

---

## Update frequency

| Trigger | When |
|---|---|
| Manual | Navigate to `claude.ai/settings/usage` (fires instantly on page load) |
| Automatic | Every 3 minutes — the extension reloads the settings tab in the background |
| SPA navigation | Detected automatically if you navigate within claude.ai |

Data persists to `~/.claude_usage.json` and is restored on restart, so the last known values are always shown immediately.

---

## Project structure

```
UsageTracker/
├── extension/
│   ├── manifest.json      # Chrome MV3 manifest
│   ├── content.js         # Scrapes DOM, POSTs JSON to Flask
│   └── background.js      # Alarm-based scheduler (reloads settings tab every 3 min)
├── menubar/
│   ├── app.py             # Flask server + rumps menu bar app
│   └── requirements.txt   # rumps, flask
└── README.md
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Menu bar shows `Claude —` | Visit `claude.ai/settings/usage` manually to trigger first scrape |
| Data stopped updating | Check Chrome DevTools console on the settings page for `[ClaudeTracker]` errors |
| `[ClaudeTracker] Server unreachable` in console | Make sure `app.py` is running: `python app.py` |
| Port 9999 already in use | `lsof -ti:9999 \| xargs kill -9`, then restart `app.py` |
| Extension not loading | Confirm Developer mode is on and you selected the `extension/` subfolder |
| `ModuleNotFoundError` | Activate the venv first: `source .venv/bin/activate` |

---

## Contributing

Pull requests welcome. If Claude's UI changes and the scraper breaks, the fix is in `extension/content.js` — update the regex patterns in `parseUsage()` to match the new DOM text.
