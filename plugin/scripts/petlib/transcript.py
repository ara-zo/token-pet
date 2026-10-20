"""Incremental reader for Claude Code transcript JSONL files.

Facts this relies on (verified against real transcripts, 2026-10):
- one API response is written as several lines (one per content block), each
  repeating the same `message.id` and `message.usage` → dedupe by message.id
- at Stop time the last line may not be written yet → cursor by byte offset,
  partial trailing line is ignored and re-read next time
- subagent lines are marked `isSidechain: true`
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from typing import List, Tuple

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


def _parse_ts(s: str) -> dt.datetime:
    d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d.astimezone(clock.local_tz())


def read_new(path: str, offset: int, seen_ids: List[str]) -> Tuple[List[Usage], int, List[str]]:
    """Return (usages, new_offset, new_seen_ids). Never raises on bad lines."""
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
            if d.get("type") != "assistant" or d.get("isSidechain"):
                continue
            msg = d.get("message") or {}
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
            ))
    return usages, pos, seen[-SEEN_LIMIT:]
