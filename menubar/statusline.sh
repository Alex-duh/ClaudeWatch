#!/usr/bin/env bash
# ClaudeWatch statusline for Claude Code.
# Orange S (session), white W (weekly). Shows data age when stale (>3 min).

python3 - <<'EOF'
import json, os, datetime

f = os.path.expanduser("~/.claude_usage.json")
try:
    with open(f) as fp:
        d = json.load(fp)
    s       = d.get("sessionPct", "?")
    w       = d.get("weeklyPct",  "?")
    scraped = d.get("scrapedAt",  "")
except Exception:
    s = w = "?"
    scraped = ""

# Age indicator — show minutes since last scrape if >3 min old
age_str = ""
if scraped:
    try:
        dt  = datetime.datetime.fromisoformat(scraped.replace("Z", "+00:00"))
        age = int((datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() // 60)
        if age >= 3:
            age_str = f" ·{age}m"
    except Exception:
        pass

orange = "\033[38;5;208m"
white  = "\033[97m"
dim    = "\033[2m"
reset  = "\033[0m"

print(f"{orange}S:{s}%{reset} {white}W:{w}%{reset}{dim}{age_str}{reset}", end="")
EOF
