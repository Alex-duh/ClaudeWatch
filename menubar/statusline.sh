#!/usr/bin/env bash
# ClaudeWatch statusline for Claude Code.
# Reads colour scheme from ~/.claude_watch_settings.json and matches the menu bar theme.
# Shows data age when last scrape is >3 minutes old.

python3 - <<'EOF'
import json, os, datetime

# ---- load usage data ----
try:
    with open(os.path.expanduser("~/.claude_usage.json")) as f:
        d = json.load(f)
    s       = d.get("sessionPct", "?")
    w       = d.get("weeklyPct",  "?")
    scraped = d.get("scrapedAt",  "")
except Exception:
    s = w = "?"
    scraped = ""

# ---- staleness indicator ----
age_str = ""
if scraped:
    try:
        dt  = datetime.datetime.fromisoformat(scraped.replace("Z", "+00:00"))
        age = int((datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() // 60)
        if age >= 3:
            age_str = f" ·{age}m"
    except Exception:
        pass

# ---- colour scheme ----
try:
    with open(os.path.expanduser("~/.claude_watch_settings.json")) as f:
        scheme = json.load(f).get("colorScheme", "anthropic")
except Exception:
    scheme = "anthropic"

ANSI = {
    "anthropic": ("\033[38;5;208m", "\033[97m"),    # orange,      white
    "navy":      ("\033[38;5;39m",  "\033[97m"),    # dodger blue, white
    "forest":    ("\033[38;5;41m",  "\033[97m"),    # spring green, white
    "mono":      ("",               ""),
}
s_col, w_col = ANSI.get(scheme, ANSI["anthropic"])
dim   = "\033[2m"
reset = "\033[0m"

print(f"{s_col}S:{s}%{reset} {w_col}W:{w}%{reset}{dim}{age_str}{reset}", end="")
EOF
