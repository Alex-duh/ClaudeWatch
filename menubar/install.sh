#!/bin/bash
# Installs the Claude Usage menu bar app as a login item.
# Run once — after this, the app starts automatically at login with no terminal.

set -e
cd "$(dirname "$0")"

echo "→ Setting up virtual environment..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

echo "→ Installing login item..."
PLIST_SRC="$(pwd)/com.claudetracker.menubar.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.claudetracker.menubar.plist"

cp "$PLIST_SRC" "$PLIST_DST"

# Unload first in case an old version is registered
launchctl bootout "gui/$(id -u)/com.claudetracker.menubar" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"

echo "→ Adding 'cw' alias to shell..."
ALIAS_LINE="alias cw='launchctl bootout gui/\$(id -u)/com.claudetracker.menubar 2>/dev/null; launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.claudetracker.menubar.plist'"
for RC in "$HOME/.zshrc" "$HOME/.bashrc"; do
  if [ -f "$RC" ] && ! grep -qF "alias cw=" "$RC"; then
    echo "" >> "$RC"
    echo "# ClaudeWatch — reopen menu bar app" >> "$RC"
    echo "$ALIAS_LINE" >> "$RC"
  fi
done
# Apply to current session
eval "$ALIAS_LINE"

echo ""
echo "✓ Done. ClaudeWatch is running and starts automatically at login."
echo "  Check the menu bar — you should see 'Claude' appear within a few seconds."
echo ""
echo "  Reopen after quitting:  cw   (or open a new terminal tab if it doesn't work yet)"
echo "  View logs:              tail -f /tmp/claudetracker.log"
echo "  Uninstall:              launchctl unload ~/Library/LaunchAgents/com.claudetracker.menubar.plist"
