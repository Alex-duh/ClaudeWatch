#!/usr/bin/env python3
"""
ClaudeWatch — macOS menu bar app.

Runs a Flask server on localhost:9999 to receive usage data from the Chrome
extension. Displays session/weekly percentages, progress bars, sparkline
history graphs, and trend indicators in the menu bar via rumps.
"""

import json
import os
import threading
from datetime import datetime

import rumps
from flask import Flask, request, jsonify

DATA_FILE    = os.path.expanduser("~/.claude_usage.json")
HISTORY_FILE = os.path.expanduser("~/.claude_usage_history.json")
MAX_HISTORY  = 200   # ~10 hours at 3-min intervals
PORT         = 9999

SPARK_CHARS = "▁▂▃▄▅▆▇█"

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_usage: dict = {
    "sessionPct":   None,
    "sessionReset": None,
    "weeklyPct":    None,
    "weeklyReset":  None,
    "scrapedAt":    None,
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
    _append_history(incoming)


def _get_usage() -> dict:
    with _lock:
        return dict(_usage)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def _append_history(data: dict) -> None:
    s = data.get("sessionPct")
    w = data.get("weeklyPct")
    if s is None and w is None:
        return
    entry = {"s": s, "w": w, "ts": data.get("scrapedAt")}
    try:
        history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE) as f:
                history = json.load(f)
        history.append(entry)
        history = history[-MAX_HISTORY:]
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f)
    except (json.JSONDecodeError, OSError):
        pass


def _get_history() -> list:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return []


# ---------------------------------------------------------------------------
# Flask server
# ---------------------------------------------------------------------------

flask_app = Flask(__name__)


@flask_app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
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
        print(f"[ClaudeWatch] Flask failed to start: {e}")
        print(f"[ClaudeWatch] Run: lsof -ti:{PORT} | xargs kill -9")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pct_bar(pct: int, width: int = 10) -> str:
    filled = round(pct / 100 * width)
    return "█" * filled + "▒" * (width - filled)


def _sparkline(values: list, width: int = 14) -> str:
    vals = [v for v in values if v is not None]
    if not vals:
        return ""
    vals = vals[-width:]
    lo, hi = min(vals), max(vals)
    if lo == hi:
        return "▄" * len(vals)
    return "".join(
        SPARK_CHARS[round((v - lo) / (hi - lo) * (len(SPARK_CHARS) - 1))]
        for v in vals
    )


def _trend_label(values: list) -> str:
    vals = [v for v in values if v is not None]
    if len(vals) < 3:
        return "gathering data…"
    current = vals[-1]
    past    = vals[max(0, len(vals) - 20)]  # ~1 hour ago
    diff    = current - past
    if diff < -30:
        return "↺ reset"
    if diff > 2:
        return f"↑ +{diff}%"
    if diff < -2:
        return f"↓ {diff}%"
    return "→ steady"


def _fmt_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%b %d %H:%M")
    except ValueError:
        return iso


# ---------------------------------------------------------------------------
# Menu bar app
# ---------------------------------------------------------------------------

class ClaudeWatchApp(rumps.App):
    def __init__(self):
        # quit_button=None so we control Quit — needed to unload launchd first,
        # otherwise KeepAlive: true restarts the process immediately on exit.
        super().__init__("Claude", quit_button=None)

        _noop = lambda _: None  # gives items solid-white colour in the menu

        self._item_session_pct   = rumps.MenuItem("Session:  —",           callback=_noop)
        self._item_session_reset = rumps.MenuItem("  ↺ resets  —",         callback=_noop)
        self._item_session_graph = rumps.MenuItem("  session history",      callback=_noop)
        self._item_weekly_pct    = rumps.MenuItem("Weekly:   —",            callback=_noop)
        self._item_weekly_reset  = rumps.MenuItem("  ↺ weekly resets  —",   callback=_noop)
        self._item_weekly_graph  = rumps.MenuItem("  weekly history",       callback=_noop)
        self._item_updated       = rumps.MenuItem("Last updated:  —",       callback=_noop)

        self.menu = [
            self._item_session_pct,
            self._item_session_reset,
            self._item_session_graph,
            None,
            self._item_weekly_pct,
            self._item_weekly_reset,
            self._item_weekly_graph,
            None,
            self._item_updated,
            None,
            rumps.MenuItem("Open Settings", callback=self._open_settings),
            rumps.MenuItem("Quit",          callback=self._quit),
        ]

        saved = _load_persisted()
        if saved:
            _update_usage(saved)

        self._timer = rumps.Timer(self._refresh_ui, 30)
        self._timer.start()
        self._refresh_ui(None)

    def _refresh_ui(self, _sender):
        u       = _get_usage()
        s_pct   = u.get("sessionPct")
        s_reset = u.get("sessionReset")
        w_pct   = u.get("weeklyPct")
        w_reset = u.get("weeklyReset")
        scraped = u.get("scrapedAt")

        history = _get_history()
        s_vals  = [h.get("s") for h in history]
        w_vals  = [h.get("w") for h in history]

        # --- Title bar ---
        parts = []
        if s_pct is not None: parts.append(f"S:{s_pct}%")
        if w_pct is not None: parts.append(f"W:{w_pct}%")
        self.title = "Claude " + ("  ".join(parts) if parts else "—")

        # --- Session ---
        if s_pct is not None:
            self._item_session_pct.title = f"Session:  {_pct_bar(s_pct)}  {s_pct}%"
        else:
            self._item_session_pct.title = "Session:  —"

        self._item_session_reset.title = (
            f"  ↺ resets  {s_reset}" if s_reset else "  ↺ resets  —"
        )

        spark_s = _sparkline(s_vals)
        trend_s = _trend_label(s_vals)
        self._item_session_graph.title = (
            f"  {spark_s}  {trend_s}" if spark_s else "  no history yet"
        )

        # --- Weekly ---
        if w_pct is not None:
            self._item_weekly_pct.title = f"Weekly:   {_pct_bar(w_pct)}  {w_pct}%"
        else:
            self._item_weekly_pct.title = "Weekly:   —"

        self._item_weekly_reset.title = (
            f"  ↺ resets  {w_reset}" if w_reset else "  ↺ resets  —"
        )

        spark_w = _sparkline(w_vals)
        trend_w = _trend_label(w_vals)
        self._item_weekly_graph.title = (
            f"  {spark_w}  {trend_w}" if spark_w else "  no history yet"
        )

        # --- Last updated ---
        self._item_updated.title = (
            f"Last updated:  {_fmt_time(scraped)}" if scraped else "Last updated:  —"
        )

    def _open_settings(self, _sender):
        import subprocess
        subprocess.Popen(["open", "https://claude.ai/settings/usage"])

    def _quit(self, _sender):
        import subprocess
        plist = os.path.expanduser(
            "~/Library/LaunchAgents/com.claudetracker.menubar.plist"
        )
        subprocess.call(["launchctl", "unload", plist])
        rumps.quit_application()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    flask_thread = threading.Thread(target=_run_flask, daemon=True)
    flask_thread.start()
    ClaudeWatchApp().run()
