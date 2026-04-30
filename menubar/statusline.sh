#!/usr/bin/env bash
# ClaudeWatch statusline for Claude Code.
# S: Anthropic orange  |  W: white  |  age: white

python3 - <<'EOF'
import json, os, datetime

try:
    with open(os.path.expanduser("~/.claude_usage.json")) as f:
        d = json.load(f)
    s       = d.get("sessionPct", "?")
    w       = d.get("weeklyPct",  "?")
    scraped = d.get("scrapedAt",  "")
except Exception:
    s = w = "?"
    scraped = ""

age_str = "·now"
if scraped:
    try:
        dt  = datetime.datetime.fromisoformat(scraped.replace("Z", "+00:00"))
        age = int((datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() // 60)
        age_str = f"·{age}m" if age > 0 else "·now"
    except Exception:
        pass

orange = "\033[38;5;166m"
white  = "\033[97m"
reset  = "\033[0m"

print(f"{orange}S:{s}%{reset} {white}W:{w}%  {age_str}{reset}", end="")
EOF
