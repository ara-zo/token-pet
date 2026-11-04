"""작업 알림: what each Claude Code session is doing, for the widget.

Hooks write one entry per session into state["alerts"]:
  UserPromptSubmit → "working"   (a prompt was sent)
  Notification     → "waiting"   (a permission prompt, or Claude waiting for an answer mid-turn)
  Stop             → "done"      (every turn, short ones too)
  SessionEnd       → removed
The widget shows one bubble (waiting > done) and a list; a click opens that session's terminal.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from typing import Dict, List, Optional

from . import clock

STALE = dt.timedelta(minutes=30)
STALE_WORKING = dt.timedelta(hours=6)   # a long agent run keeps working without hook writes
NAME_MAX = 10


def name_of(cwd: Optional[str]) -> str:
    base = os.path.basename((cwd or "").rstrip("/"))
    if not base:
        return "Claude Code"
    return base if len(base) <= NAME_MAX else base[: NAME_MAX - 1] + "…"


def _tty(ppid: int) -> Optional[str]:
    try:
        out = subprocess.run(["ps", "-o", "tty=", "-p", str(ppid)], capture_output=True, text=True, timeout=2).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not out or out.startswith("?"):
        return None
    return out if out.startswith("/dev/") else "/dev/" + out


def term_info(env: Dict[str, str], tty: Optional[str] = None) -> dict:
    """Where the session runs, so a click can bring it back: the app, plus a tab id when the terminal has one."""
    info = {
        "app": env.get("TERM_PROGRAM") or None,
        "bundle": env.get("__CFBundleIdentifier") or None,
        "tty": tty,
    }
    if env.get("ORCA_TERMINAL_HANDLE"):
        info["orca"] = env["ORCA_TERMINAL_HANDLE"]
        bin_dir = env.get("ORCA_CLI_BIN_DIR")
        if bin_dir:
            info["orca_bin"] = os.path.join(bin_dir, "orca")
    if env.get("HERDR_PANE_ID"):           # herdr inside a terminal app: TERM_PROGRAM is herdr, the bundle is the app
        info["herdr"] = env["HERDR_PANE_ID"]
        info["herdr_bin"] = env.get("HERDR_BIN_PATH")
        info["herdr_sock"] = env.get("HERDR_SOCKET_PATH")
    if env.get("ITERM_SESSION_ID"):
        info["iterm"] = env["ITERM_SESSION_ID"].split(":", 1)[-1]
    return {k: v for k, v in info.items() if v}


def kind_of(message: str) -> str:
    return "permission" if "permission" in (message or "").lower() else "input"


def prune(state: dict, now: dt.datetime) -> None:
    alerts = state.setdefault("alerts", {})
    for sid, a in list(alerts.items()):
        try:
            old = now - clock.parse(a["updated_at"]) > (STALE_WORKING if a.get("state") == "working" else STALE)
        except (KeyError, ValueError, TypeError):
            old = True
        if old:
            del alerts[sid]


def record(state: dict, event: str, data: dict, now: dt.datetime, term: Optional[dict] = None) -> Optional[dict]:
    """Apply one hook event. Returns the session's entry, or None when it was cleared."""
    alerts = state.setdefault("alerts", {})
    prune(state, now)
    sid = data.get("session_id")
    if not sid:
        return None
    if not state.get("settings", {}).get("alerts", True):
        alerts.pop(sid, None)
        return None
    cur = alerts.get(sid)
    ts = clock.fmt(now)
    if event == "end":
        alerts.pop(sid, None)
        return None
    if event == "prompt":
        cur = alerts[sid] = {
            "state": "working", "since": ts, "started_at": ts, "updated_at": ts,
            "cwd": data.get("cwd") or (cur or {}).get("cwd"),
            "name": name_of(data.get("cwd") or (cur or {}).get("cwd")),
            "term": term or (cur or {}).get("term") or {},
        }
        return cur
    if cur is None:
        return None                       # a session we never saw start (or already cleared)
    if event == "notify":
        if cur["state"] == "done":
            return cur                    # "waiting for your input" after a finished turn: already said 다 했어
        cur.update(state="waiting", kind=kind_of(data.get("message", "")), since=ts, updated_at=ts, seen=False)
        return cur
    if event == "stop":
        cur.update(state="done", since=ts, updated_at=ts, seen=False)
        cur.pop("kind", None)
        return cur
    return cur


def seen(state: dict, sid: str) -> bool:
    """The user clicked it: a finished session goes away, a waiting one stops ringing until it asks again."""
    alerts = state.setdefault("alerts", {})
    a = alerts.get(sid)
    if not a:
        return False
    if a["state"] == "done":
        del alerts[sid]
    else:
        a["seen"] = True
    return True


def open_commands(entry: dict) -> List[List[str]]:
    """Commands that bring the session's terminal to the front, most specific first."""
    t = entry.get("term") or {}
    cmds: List[List[str]] = []
    bundle = t.get("bundle")
    app = (t.get("app") or "").lower()
    cwd = entry.get("cwd")
    if bundle:
        cmds.append(["open", "-b", bundle])
    if t.get("orca"):
        cmds.append([t.get("orca_bin") or "orca", "terminal", "switch", "--terminal", t["orca"]])
    elif t.get("herdr"):
        cmds.append([t.get("herdr_bin") or "herdr", "agent", "focus", t["herdr"]])
    elif t.get("iterm") and (app.startswith("iterm") or (bundle or "").startswith("com.googlecode.iterm2")):
        cmds.append(["osascript", "-e", _ITERM.replace("{id}", t["iterm"])])
    elif t.get("tty") and (app == "apple_terminal" or bundle == "com.apple.Terminal"):
        cmds.append(["osascript", "-e", _TERMINAL.replace("{tty}", t["tty"])])
    elif cwd and (app == "vscode" or "jetbrains" in (bundle or "") or "jetbrains" in app):
        cmds = [["open", "-b", bundle, cwd]] if bundle else [["open", cwd]]
    return cmds


_ITERM = '''tell application "iTerm2"
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        if unique id of s is "{id}" then
          select w
          select t
          select s
          activate
          return
        end if
      end repeat
    end repeat
  end repeat
end tell'''

_TERMINAL = '''tell application "Terminal"
  repeat with w in windows
    repeat with t in tabs of w
      if tty of t is "{tty}" then
        set selected of t to true
        set index of w to 1
        activate
        return
      end if
    end repeat
  end repeat
end tell'''


def _herdr_env(t: dict) -> Optional[dict]:
    return dict(os.environ, HERDR_SOCKET_PATH=t["herdr_sock"]) if t.get("herdr_sock") else None


def _herdr_pane(t: dict, sid: Optional[str]) -> Optional[str]:
    """The pane now hosting this Claude session; panes moved between workspaces get new ids."""
    if not sid:
        return None
    try:
        out = subprocess.run([t.get("herdr_bin") or "herdr", "agent", "list"], capture_output=True, text=True,
                             timeout=3, env=_herdr_env(t)).stdout
        for a in json.loads(out)["result"]["agents"]:
            if (a.get("agent_session") or {}).get("value") == sid:
                return a.get("pane_id")
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        pass
    return None


def open_session(entry: dict, sid: Optional[str] = None) -> bool:
    t = entry.get("term") or {}
    env = None
    if t.get("herdr"):
        pane = _herdr_pane(t, sid)
        if pane:
            entry = dict(entry, term=dict(t, herdr=pane))
        env = _herdr_env(t)
    ok = False
    for cmd in open_commands(entry):
        try:
            ok = subprocess.run(cmd, capture_output=True, timeout=5, env=env).returncode == 0 or ok
        except (OSError, subprocess.SubprocessError):
            pass
    return ok
