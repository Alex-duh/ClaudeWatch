#!/usr/bin/env python3
"""
Claude Pro Usage — macOS menu bar app.

Runs a Flask server on localhost:9999 to receive data from the Chrome extension,
and displays current Claude Pro usage in the menu bar via rumps.
"""

import json
import os
import threading
from datetime import datetime

import rumps
from flask import Flask, request, jsonify

DATA_FILE = os.path.expanduser("~/.claude_usage.json")
PORT = 9999

# ---------------------------------------------------------------------------
# Shared state (written by Flask thread, read by rumps thread)
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_usage: dict = {
    "sessionPct": None,
    "sessionReset": None,
    "weeklyPct": None,
    "weeklyReset": None,
    "scrapedAt": None,
}


def _load_persisted() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save(data: dict) -> None:
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def _update_usage(incoming: dict) -> None:
    with _lock:
        for key in ("sessionPct", "sessionReset", "weeklyPct", "weeklyReset", "scrapedAt"):
            if incoming.get(key) is not None:
                _usage[key] = incoming[key]
        _save(dict(_usage))


def _get_usage() -> dict:
    with _lock:
        return dict(_usage)


# ---------------------------------------------------------------------------
# Flask server (background thread)
# ---------------------------------------------------------------------------

flask_app = Flask(__name__)


@flask_app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    return response


@flask_app.route("/usage", methods=["OPTIONS"])
def usage_preflight():
    return "", 204


@flask_app.post("/usage")
def receive_usage():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "no JSON body"}), 400
    _update_usage(data)
    return jsonify({"status": "ok"}), 200


@flask_app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


def _run_flask():
    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    try:
        flask_app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
    except OSError as e:
        print(f"[ClaudeTracker] Flask failed to start: {e}")
        print(f"[ClaudeTracker] Run: lsof -ti:{PORT} | xargs kill -9")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pct_bar(pct: int, width: int = 10) -> str:
    filled = round(pct / 100 * width)
    return "█" * filled + "▒" * (width - filled)


def _fmt_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%b %d %H:%M")
    except ValueError:
        return iso


# ---------------------------------------------------------------------------
# rumps menu bar app
# ---------------------------------------------------------------------------

class ClaudeUsageApp(rumps.App):
    def __init__(self):
        super().__init__("Claude")

        # No-op callbacks make items render as solid white instead of greyed-out.
        # rumps calls setEnabled_(False) on any MenuItem that has no callback.
        _noop = lambda _: None
        self._item_session_pct   = rumps.MenuItem("Session:  —",      callback=_noop)
        self._item_session_reset = rumps.MenuItem("  ↺ resets  —",    callback=_noop)
        self._item_weekly_pct    = rumps.MenuItem("Weekly:   —",       callback=_noop)
        self._item_weekly_reset  = rumps.MenuItem("  ↺ resets  —",    callback=_noop)
        self._item_updated       = rumps.MenuItem("Last updated:  —",  callback=_noop)

        self.menu = [
            self._item_session_pct,
            self._item_session_reset,
            None,
            self._item_weekly_pct,
            self._item_weekly_reset,
            None,
            self._item_updated,
            None,
            rumps.MenuItem("Open Settings", callback=self._open_settings),
        ]

        saved = _load_persisted()
        if saved:
            _update_usage(saved)

        self._timer = rumps.Timer(self._refresh_ui, 30)
        self._timer.start()
        self._refresh_ui(None)

    def _refresh_ui(self, _sender):
        u = _get_usage()
        s_pct   = u.get("sessionPct")
        s_reset = u.get("sessionReset")
        w_pct   = u.get("weeklyPct")
        w_reset = u.get("weeklyReset")
        scraped = u.get("scrapedAt")

        # --- Title bar: "Claude S:71% W:14%" ---
        parts = []
        if s_pct is not None: parts.append(f"S:{s_pct}%")
        if w_pct is not None: parts.append(f"W:{w_pct}%")
        self.title = "Claude " + ("  ".join(parts) if parts else "—")

        # --- Session row ---
        if s_pct is not None:
            bar = _pct_bar(s_pct)
            self._item_session_pct.title   = f"Session:  {bar}  {s_pct}%"
        else:
            self._item_session_pct.title   = "Session:  —"
        self._item_session_reset.title = f"  ↺ resets  {s_reset}" if s_reset else "  ↺ resets  —"

        # --- Weekly row ---
        if w_pct is not None:
            bar = _pct_bar(w_pct)
            self._item_weekly_pct.title    = f"Weekly:   {bar}  {w_pct}%"
        else:
            self._item_weekly_pct.title    = "Weekly:   —"
        self._item_weekly_reset.title  = f"  ↺ resets  {w_reset}" if w_reset else "  ↺ resets  —"

        # --- Last updated ---
        self._item_updated.title = f"Last updated:  {_fmt_time(scraped) if scraped else '—'}"

    def _open_settings(self, _sender):
        import subprocess
        subprocess.Popen(["open", "https://claude.ai/settings/usage"])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    flask_thread = threading.Thread(target=_run_flask, daemon=True)
    flask_thread.start()
    ClaudeUsageApp().run()
