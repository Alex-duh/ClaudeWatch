#!/usr/bin/env bash
# ClaudeWatch statusline for Claude Code.
# Outputs coloured usage: orange S (session) and white W (weekly).
# No external dependencies — uses python3 which ships with macOS.

python3 - <<'EOF'
import json, os

f = os.path.expanduser("~/.claude_usage.json")
try:
    with open(f) as fp:
        d = json.load(fp)
    s = d.get("sessionPct", "?")
    w = d.get("weeklyPct", "?")
except Exception:
    s = w = "?"

orange = "\033[38;5;208m"   # Claude orange
white  = "\033[97m"          # bright white
reset  = "\033[0m"

print(f"{orange}S:{s}%{reset} {white}W:{w}%{reset}", end="")
EOF
