"""위젯에서 답하기: answer a session's permission prompt or question from the widget.

Facts this relies on (checked by driving a real Claude Code 2.1.283 session, 2026-11):
- the PermissionRequest hook fires for permission prompts and for AskUserQuestion, and the terminal shows
  its dialog while the hook runs: whichever answers first wins
- the hook allows with {"behavior": "allow"}, refuses with {"behavior": "deny"}, and answers a question with
  "allow" + updatedInput = the tool input plus "answers" {question text: option label or free text}
- answered in the terminal first, the hook is not stopped; the transcript stays still while the dialog
  waits, and once it is answered the tool's result (allowed, refused, or the answers) is written there.
  The hook input carries no tool_use id, so the hook looks for a result of a tool_use with the same
  name and input that wasn't already answered when it started

The hook writes the question into the session's alert entry ("ask"), the widget writes the reply next to
it (`pet.py alert answer`), and the hook, polling the file, hands the reply to Claude Code.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
import uuid
from typing import Callable, Optional

from . import alerts, clock, store, vacation

WAIT = 590.0                 # seconds; under the hook's timeout (600) so the hook always ends by itself
POLL = 0.4
TAIL = 256 * 1024            # bytes of transcript read for 「직전에 한 말」
SAID_MAX = 300

# commands the widget never allows: the card only sends you to the terminal
DANGER = [re.compile(p, re.I) for p in (
    r"\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r|\brm\s+--recursive",
    r"\bgit\s+push\b.*(\s-f\b|--force)",
    r"\bgit\s+reset\s+--hard",
    r"\bgit\s+clean\s+-[a-z]*f",
    r"\bdrop\s+(table|database|schema)\b",
    r"\btruncate\s+(table\s+)?\w",
    r"\bsudo\b",
    r"\bmkfs\b|\bdd\s+if=",
    r"\bchmod\s+-R\s+777\b",
)]


def is_danger(tool: str, tool_input: dict) -> bool:
    if tool != "Bash":
        return False
    cmd = str((tool_input or {}).get("command") or "")
    return any(p.search(cmd) for p in DANGER)


def last_said(path: Optional[str]) -> dict:
    """The last thing Claude said in the session, and the session's title, from the transcript's tail."""
    out: dict = {}
    if not path:
        return out
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - TAIL))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return out
    for line in reversed(lines):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if "title" not in out and d.get("type") == "ai-title" and d.get("aiTitle"):
            out["title"] = str(d["aiTitle"])
        if "said" not in out and d.get("type") == "assistant" and not d.get("isSidechain"):
            content = (d.get("message") or {}).get("content")
            texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"] \
                if isinstance(content, list) else []
            text = " ".join(t.strip() for t in texts if t.strip())
            if text:
                text = re.sub(r"\s+", " ", text)
                out["said"] = text if len(text) <= SAID_MAX else text[: SAID_MAX - 1] + "…"
        if "said" in out and "title" in out:
            break
    return out


def summary(tool: str, tool_input: dict) -> dict:
    """What the card shows for a permission prompt."""
    ti = tool_input or {}
    s = {"tool": tool}
    if ti.get("command"):
        s["command"] = str(ti["command"])
    if ti.get("description"):
        s["description"] = str(ti["description"])
    path = ti.get("file_path") or ti.get("notebook_path") or ti.get("path")
    if path:
        s["file"] = str(path)
    if ti.get("url"):
        s["url"] = str(ti["url"])
    return s


def questions_of(tool_input: dict) -> list:
    qs = []
    for q in (tool_input or {}).get("questions") or []:
        qs.append({
            "question": str(q.get("question") or ""),
            "header": str(q.get("header") or ""),
            "multi": bool(q.get("multiSelect")),
            "options": [{"label": str(o.get("label") or ""), "description": str(o.get("description") or ""),
                         "preview": bool(o.get("preview"))} for o in q.get("options") or []],
        })
    return qs


def build(data: dict, now: dt.datetime) -> dict:
    tool = str(data.get("tool_name") or "")
    ti = data.get("tool_input") or {}
    ask = {"id": uuid.uuid4().hex[:12], "at": clock.fmt(now), "mode": data.get("permission_mode")}
    if tool == "AskUserQuestion":
        qs = questions_of(ti)
        ask.update(kind="question", questions=qs)
        if not qs or any(q["multi"] or any(o["preview"] for o in q["options"]) for q in qs):
            ask["terminal"] = True            # multi-select and previews are answered in the terminal
    else:
        ask.update(kind="permission", **summary(tool, ti))
        if is_danger(tool, ti):
            ask["danger"] = True
            ask["terminal"] = True
    ask.update(last_said(data.get("transcript_path")))
    return ask


def wanted(state: dict) -> bool:
    st = state.get("settings") or {}
    return bool(st.get("alerts", True) and not vacation.active(state))


def offer(state: dict, data: dict, now: dt.datetime, term: Optional[dict] = None) -> Optional[dict]:
    """Put the question on the widget. Returns the ask, or None when the widget shouldn't ask."""
    sid = data.get("session_id")
    if not sid or not wanted(state):
        return None
    alerts.prune(state, now)
    entries = state.setdefault("alerts", {})
    ts = clock.fmt(now)
    cur = entries.get(sid)
    if cur is None:                           # a session started before the hooks were loaded
        cwd = data.get("cwd")
        cur = entries[sid] = {"started_at": ts, "cwd": cwd, "name": alerts.name_of(cwd), "term": term or {}}
    ask = build(data, now)
    cur.update(state="waiting", kind=ask["kind"], since=ts, updated_at=ts, seen=False, ask=ask)
    return ask


def current(state: dict, sid: str) -> Optional[dict]:
    return ((state.get("alerts") or {}).get(sid) or {}).get("ask")


def withdraw(state: dict, sid: str, ask_id: str, now: dt.datetime, working: bool) -> bool:
    """The question is gone (answered in the terminal, or the wait ran out): take it off the widget."""
    cur = (state.get("alerts") or {}).get(sid)
    if not cur or (cur.get("ask") or {}).get("id") != ask_id:
        return False
    cur.pop("ask", None)
    if working:                               # Claude Code went on with the turn
        cur.update(state="working", updated_at=clock.fmt(now), answered_at=clock.fmt(now))
        cur.pop("kind", None)
    return True


def reply(state: dict, sid: str, ask_id: str, answer: dict, now: dt.datetime) -> Optional[str]:
    """The widget's answer. Returns why it can't be taken, or None when it was."""
    ask = current(state, sid)
    if not ask or ask.get("id") != ask_id:
        return "그 질문은 이미 끝났어요"
    if ask.get("terminal"):
        return "이건 터미널에서 답해야 해요"
    if ask["kind"] == "permission":
        if answer.get("behavior") not in ("allow", "deny"):
            return "허용이나 거부만 보낼 수 있어요"
    else:
        answers = answer.get("answers")
        if not isinstance(answers, dict) or not answers:
            return "답이 비어 있어요"
        known = {q["question"] for q in ask.get("questions") or []}
        if any(k not in known or not str(v).strip() for k, v in answers.items()) or set(answers) != known:
            return "모든 질문에 답해야 해요"
        answer = {"answers": {k: str(v).strip() for k, v in answers.items()}}
    ask["reply"] = answer
    ask["replied_at"] = clock.fmt(now)
    return None


def decision(data: dict, answer: dict) -> dict:
    """The hook's output for Claude Code."""
    if answer.get("behavior") == "deny":
        d = {"behavior": "deny", "message": "위젯에서 거부했어요"}
    elif "answers" in answer:
        d = {"behavior": "allow", "updatedInput": dict(data.get("tool_input") or {}, answers=answer["answers"])}
    else:
        d = {"behavior": "allow"}
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": d}}


def _tool_results(path: Optional[str], tool: str, tool_input: dict) -> set:
    """Ids of tool_use blocks with this name and input that have a result, from the transcript's tail."""
    uses, results = set(), set()
    if not path:
        return set()
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - TAIL))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return set()
    for line in lines:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        content = (d.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use" and b.get("name") == tool and b.get("input") == tool_input:
                uses.add(b.get("id"))
            elif b.get("type") == "tool_result":
                results.add(b.get("tool_use_id"))
    return uses & results


def _size(path: Optional[str]) -> Optional[int]:
    try:
        return os.stat(path).st_size if path else None
    except OSError:
        return None


def wait(sid: str, ask_id: str, data: dict, now: Callable[[], dt.datetime] = clock.now,
         sleep: Callable[[float], None] = time.sleep, limit: Optional[float] = None) -> Optional[dict]:
    """Poll the state file for the widget's reply. None when the question went away or the time ran out;
    either way the ask is off the widget when this returns."""
    start = time.monotonic()
    limit = WAIT if limit is None else limit
    transcript = data.get("transcript_path")
    tool, tool_input = str(data.get("tool_name") or ""), data.get("tool_input") or {}
    answered_before = _tool_results(transcript, tool, tool_input)
    size0 = _size(transcript)
    while time.monotonic() - start < limit:
        sleep(POLL)
        ask = current(store.load(), sid)
        if not ask or ask.get("id") != ask_id:
            return None                       # replaced by a newer question, or the turn ended
        if ask.get("reply"):
            with store.transaction(now(), tick=False) as s:
                withdraw(s, sid, ask_id, now(), working=True)
            return ask["reply"]
        size = _size(transcript)
        if size != size0:                     # something was written: is it this tool's result?
            size0 = size
            if _tool_results(transcript, tool, tool_input) - answered_before:
                with store.transaction(now(), tick=False) as s:     # answered in the terminal
                    withdraw(s, sid, ask_id, now(), working=True)
                return None
    with store.transaction(now(), tick=False) as s:
        withdraw(s, sid, ask_id, now(), working=False)
    return None
