#!/usr/bin/env python3
"""ClaudeWatch — macOS menu bar app, minimal mono."""

import json
import os
import threading
from datetime import datetime

import rumps
from flask import Flask, request, jsonify

DATA_FILE    = os.path.expanduser("~/.claude_usage.json")
HISTORY_FILE = os.path.expanduser("~/.claude_usage_history.json")
MAX_HISTORY  = 200
PORT         = 9999
SPARK_CHARS  = "▁▂▃▄▅▆▇█"

# ---------------------------------------------------------------------------
# Colours — mono only
#   c_pri  : session filled dots + sparkline + title S:%
#   c_sec  : weekly  filled dots + sparkline + title W:%
#   c_unf  : empty dots
#   c_sep  : │ separators
# ---------------------------------------------------------------------------

try:
    from AppKit import (
        NSAttributedString, NSMutableAttributedString,
        NSForegroundColorAttributeName, NSColor,
    )
    from Foundation import NSMakeRange
    _HAS_APPKIT = True

    # Adaptive system colors — pure white in dark mode, pure black in light mode
    C_PRI = NSColor.labelColor()              # filled blocks (used)
    C_SEC = NSColor.labelColor()              # weekly filled (same)
    C_UNF = NSColor.tertiaryLabelColor()      # unfilled blocks (remaining)
    C_SEP = NSColor.quaternaryLabelColor()    # │ separators

except ImportError:
    _HAS_APPKIT = False
    C_PRI = C_SEC = C_UNF = C_SEP = None


def _set_segments(target, segments: list) -> None:
    """Apply [(text, NSColor|None), …] to a MenuItem or App (status bar)."""
    full = "".join(t for t, _ in segments)
    if not _HAS_APPKIT:
        if isinstance(target, rumps.App): target.title = full
        else: target.title = full
        return
    try:
        astr = NSMutableAttributedString.alloc().initWithString_(full)
        pos  = 0
        for text, color in segments:
            if color is not None:
                astr.addAttribute_value_range_(
                    NSForegroundColorAttributeName, color, NSMakeRange(pos, len(text))
                )
            pos += len(text)
        if isinstance(target, rumps.App):
            target._status_item.button().setAttributedTitle_(astr)
        else:
            target._menuitem.setAttributedTitle_(astr)
    except Exception:
        if isinstance(target, rumps.App): target.title = full
        else: target.title = full


def _bar_segs(pct: int, c_filled, c_unfilled, c_sep, n: int = 8):
    """Solid-block progress bar: █ white filled, ▒ grey unfilled, │ separators."""
    filled = round(pct / 100 * n)
    segs   = []
    for i in range(n):
        if i > 0:
            segs.append(("│", c_sep))
        segs.append(("█" if i < filled else "▒",
                      c_filled if i < filled else c_unfilled))
    return segs


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_usage: dict = {
    "sessionPct": None, "sessionReset": None,
    "weeklyPct":  None, "weeklyReset":  None,
    "scrapedAt":  None,
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
    if data.get("sessionPct") is None and data.get("weeklyPct") is None:
        return
    entry = {"s": data.get("sessionPct"), "w": data.get("weeklyPct"), "ts": data.get("scrapedAt")}
    try:
        history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE) as f:
                history = json.load(f)
        history.append(entry)
        with open(HISTORY_FILE, "w") as f:
            json.dump(history[-MAX_HISTORY:], f)
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
# Display helpers
# ---------------------------------------------------------------------------

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
    diff = vals[-1] - vals[max(0, len(vals) - 20)]
    if diff < -30: return "↺ reset"
    if diff > 2:   return f"↑ +{diff}%"
    if diff < -2:  return f"↓ {diff}%"
    return "→ steady"


def _fmt_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%b %d %H:%M")
    except ValueError:
        return iso


# ---------------------------------------------------------------------------
# Menu bar app
# ---------------------------------------------------------------------------

class ClaudeWatchApp(rumps.App):
    def __init__(self):
        super().__init__("Claude", quit_button=None)

        _noop = lambda _: None

        self._item_session_pct   = rumps.MenuItem("Session:  —",          callback=_noop)
        self._item_session_reset = rumps.MenuItem("  ↺ resets  —",        callback=_noop)
        self._item_session_graph = rumps.MenuItem("  session history",     callback=_noop)
        self._item_weekly_pct    = rumps.MenuItem("Weekly:   —",           callback=_noop)
        self._item_weekly_reset  = rumps.MenuItem("  ↺ weekly resets  —",  callback=_noop)
        self._item_weekly_graph  = rumps.MenuItem("  weekly history",      callback=_noop)
        self._item_updated       = rumps.MenuItem("Last updated:  —",      callback=_noop)

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

    def _refresh_ui(self, _sender) -> None:
        u       = _get_usage()
        s_pct   = u.get("sessionPct")
        s_reset = u.get("sessionReset")
        w_pct   = u.get("weeklyPct")
        w_reset = u.get("weeklyReset")
        scraped = u.get("scrapedAt")

        history = _get_history()
        s_vals  = [h.get("s") for h in history]
        w_vals  = [h.get("w") for h in history]

        # --- Status bar ---
        parts = []
        if s_pct is not None: parts.append(f"S:{s_pct}%")
        if w_pct is not None: parts.append(f"W:{w_pct}%")
        title = "Claude " + ("  ".join(parts) if parts else "—")
        _set_segments(self, [(title, C_PRI)])

        # --- Session bar ---
        if s_pct is not None:
            _set_segments(self._item_session_pct,
                [("Session:  ", None)]
                + _bar_segs(s_pct, C_PRI, C_UNF, C_SEP)
                + [(f"  {s_pct}%", C_PRI)]
            )
        else:
            _set_segments(self._item_session_pct, [("Session:  —", None)])

        _set_segments(self._item_session_reset, [
            (f"  ↺ resets  {s_reset}" if s_reset else "  ↺ resets  —", None)
        ])

        spark_s = _sparkline(s_vals)
        _set_segments(self._item_session_graph,
            [("  ", None), (spark_s, C_PRI), (f"  {_trend_label(s_vals)}", None)]
            if spark_s else [("  no history yet", None)]
        )

        # --- Weekly bar ---
        if w_pct is not None:
            _set_segments(self._item_weekly_pct,
                [("Weekly:   ", None)]
                + _bar_segs(w_pct, C_SEC, C_UNF, C_SEP)
                + [(f"  {w_pct}%", C_SEC)]
            )
        else:
            _set_segments(self._item_weekly_pct, [("Weekly:   —", None)])

        _set_segments(self._item_weekly_reset, [
            (f"  ↺ resets  {w_reset}" if w_reset else "  ↺ resets  —", None)
        ])

        spark_w = _sparkline(w_vals)
        _set_segments(self._item_weekly_graph,
            [("  ", None), (spark_w, C_SEC), (f"  {_trend_label(w_vals)}", None)]
            if spark_w else [("  no history yet", None)]
        )

        # --- Last updated ---
        _set_segments(self._item_updated, [
            (f"Last updated:  {_fmt_time(scraped)}" if scraped else "Last updated:  —", None)
        ])

    def _open_settings(self, _sender):
        import subprocess
        subprocess.Popen(["open", "https://claude.ai/settings/usage"])

    def _quit(self, _sender):
        import subprocess
        plist = os.path.expanduser("~/Library/LaunchAgents/com.claudetracker.menubar.plist")
        subprocess.call(["launchctl", "unload", plist])
        rumps.quit_application()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    flask_thread = threading.Thread(target=_run_flask, daemon=True)
    flask_thread.start()
    ClaudeWatchApp().run()
