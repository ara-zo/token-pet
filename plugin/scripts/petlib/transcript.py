"""Incremental reader for Claude Code transcript JSONL files.

Facts this relies on (verified against real transcripts, 2026-10):
- one API response is written as several lines (one per content block), each
  repeating the same `message.id` and `message.usage` → dedupe by message.id
- at Stop time the last line may not be written yet → cursor by byte offset,
  partial trailing line is ignored and re-read next time
- subagent lines are marked `isSidechain: true`; each subagent also has its own file in
  `<session>/subagents/agent-*.jsonl` (hooks doc, SubagentStop `agent_transcript_path`),
  where every line is a sidechain line
- every line carries the session's `cwd`; Claude Code writes the session's title as
  `{"type": "ai-title", "aiTitle": ...}` lines, repeated (and sometimes reworded) as it goes
- the Bash tool's commands are `tool_use` blocks; a block sits on its own line, often not the
  first line of its response, so commands are read on every line, before the message.id dedupe
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from . import clock

SEEN_LIMIT = 200


@dataclass
class Usage:
    message_id: str
    ts: dt.datetime
    output: int
    input: int
    cache_read: int
    cache_creation: int
    cwd: str = ""


@dataclass
class Act:
    """A command Claude ran that the diary counts: "commit", "test" or "pr"."""
    kind: str
    ts: dt.datetime
    cwd: str = ""


_HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\b", re.S)
_SPLIT = re.compile(r"&&|\|\||[;|\n]")
_LEAD = re.compile(r"^(?:\(\s*|\w+=\S*\s+|(?:time|env|sudo|npx|bunx|uv run|poetry run|pipenv run)\s+)+")
_TEST = re.compile(r"^(?:\S*/)?(?:pytest|py\.test|vitest|jest|python3?(?:\.\d+)? -m (?:pytest|unittest)"
                   r"|(?:npm|pnpm|yarn|bun)(?: run)? test|cargo (?:test|nextest)|go test|mvn\S* (?:\S+ )*test"
                   r"|(?:\./)?gradlew?\S* (?:\S+ )*(?::?\S*:)?test)\b")


def command_acts(command: str) -> List[str]:
    """What a shell command did, one entry per counted step: `git add . && git commit -m x` → ["commit"].

    Steps are matched at their start, so `grep 'git commit' log` counts nothing."""
    kinds = []
    for seg in _SPLIT.split(_HEREDOC.sub("", command or "")):
        seg = _LEAD.sub("", seg.strip())
        if re.match(r"git (?:-C \S+ )?commit\b", seg):
            if "--amend" not in seg:
                kinds.append("commit")
        elif re.match(r"gh pr create\b", seg):
            kinds.append("pr")
        elif _TEST.match(seg):
            kinds.append("test")
    return kinds


def _parse_ts(s: str) -> dt.datetime:
    d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d.astimezone(clock.local_tz())


def read_new(path: str, offset: int, seen_ids: List[str], include_sidechain: bool = False,
             meta: Optional[dict] = None) -> Tuple[List[Usage], int, List[str]]:
    """Return (usages, new_offset, new_seen_ids). Never raises on bad lines.

    The main transcript skips sidechain lines; a subagent's own file is read with
    include_sidechain=True. When `meta` is given it also collects, from the same lines,
    `meta["title"]` (the newest session title) and `meta["acts"]` (counted commands, see Act).
    """
    seen = list(seen_ids)
    seen_set = set(seen)
    usages: List[Usage] = []
    try:
        f = open(path, "rb")
    except OSError:
        return usages, offset, seen
    with f:
        f.seek(offset)
        pos = offset
        while True:
            raw = f.readline()
            if not raw:
                break
            if not raw.endswith(b"\n"):
                break                       # partial line: leave offset before it
            pos += len(raw)
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            if meta is not None and d.get("type") == "ai-title" and d.get("aiTitle"):
                meta["title"] = str(d["aiTitle"])
            if d.get("type") != "assistant" or (d.get("isSidechain") and not include_sidechain):
                continue
            msg = d.get("message") or {}
            if meta is not None and isinstance(msg.get("content"), list):
                _collect_acts(d, msg["content"], meta)
            mid = msg.get("id")
            usage = msg.get("usage")
            if not mid or not usage or mid in seen_set:
                continue
            seen_set.add(mid)
            seen.append(mid)
            try:
                ts = _parse_ts(d["timestamp"])
            except (KeyError, ValueError):
                ts = clock.now()
            usages.append(Usage(
                message_id=mid, ts=ts,
                output=int(usage.get("output_tokens") or 0),
                input=int(usage.get("input_tokens") or 0),
                cache_read=int(usage.get("cache_read_input_tokens") or 0),
                cache_creation=int(usage.get("cache_creation_input_tokens") or 0),
                cwd=str(d.get("cwd") or ""),
            ))
    return usages, pos, seen[-SEEN_LIMIT:]


def _collect_acts(d: dict, content: list, meta: dict) -> None:
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use" or block.get("name") != "Bash":
            continue
        kinds = command_acts(str((block.get("input") or {}).get("command") or ""))
        if not kinds:
            continue
        try:
            ts = _parse_ts(d["timestamp"])
        except (KeyError, ValueError):
            ts = clock.now()
        meta.setdefault("acts", []).extend(Act(k, ts, str(d.get("cwd") or "")) for k in kinds)


def subagent_files(main_path: str) -> List[str]:
    """Subagent transcripts that belong to the session whose transcript is main_path."""
    import os
    folder = os.path.join(os.path.splitext(main_path)[0], "subagents")
    try:
        names = sorted(n for n in os.listdir(folder) if n.endswith(".jsonl"))
    except OSError:
        return []
    return [os.path.join(folder, n) for n in names]
