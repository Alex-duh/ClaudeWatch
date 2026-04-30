#!/bin/bash
# Double-click this (or run it once) to start the Claude Usage menu bar app.
# Sets up the venv on first run, then launches in the background.

set -e
cd "$(dirname "$0")"

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

# Install / update dependencies silently
pip install -q -r requirements.txt

# Kill any stale process on port 9999
lsof -ti:9999 | xargs kill -9 2>/dev/null || true

echo "Starting Claude Usage Tracker..."
python app.py
