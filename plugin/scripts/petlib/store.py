"""Locked, atomic access to state.json. The only writer in the system."""
from __future__ import annotations

import datetime as dt
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from . import clock, schema

LOG_LINES = 50


def home() -> Path:
    p = Path(os.environ.get("PET_HOME") or Path.home() / ".claude" / "pet")
    p.mkdir(parents=True, exist_ok=True)
    return p


def state_path() -> Path:
    return home() / "state.json"


def load(now: Optional[dt.datetime] = None) -> dict:
    """Read-only load (no lock, no tick). Returns a fresh state if missing/corrupt."""
    now = now or clock.now()
    try:
        with open(state_path(), "r", encoding="utf-8") as f:
            return schema.migrate(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return schema.new_state(now)


def write(state: dict) -> None:
    path = state_path()
    fd, tmp = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


@contextmanager
def transaction(now: Optional[dt.datetime] = None, tick: bool = True) -> Iterator[dict]:
    """flock → load → (tick) → yield → write. Exceptions inside skip the write."""
    now = now or clock.now()
    lock_path = home() / ".lock"
    with open(lock_path, "a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            state = load(now)
            if tick:
                from . import tick as _tick  # lazy: tick imports economy/evolve
                _tick.apply(state, now)
            yield state
            write(state)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def log(msg: str) -> None:
    path = home() / "collect.log"
    stamp = clock.fmt(clock.now())
    try:
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    except OSError:
        lines = []
    lines.append(f"{stamp} {msg}")
    path.write_text("\n".join(lines[-LOG_LINES:]) + "\n", encoding="utf-8")
