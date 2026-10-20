"""Time helpers. Every datetime in petlib is timezone-aware local time."""
from __future__ import annotations

import datetime as dt
from typing import List


def local_tz() -> dt.tzinfo:
    tz = dt.datetime.now().astimezone().tzinfo
    return tz if tz is not None else dt.timezone.utc


def now() -> dt.datetime:
    return dt.datetime.now(local_tz())


def parse(s: str) -> dt.datetime:
    d = dt.datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=local_tz())
    return d


def fmt(d: dt.datetime) -> str:
    return d.isoformat(timespec="seconds")


def hours_between(a: dt.datetime, b: dt.datetime) -> float:
    return (b - a).total_seconds() / 3600.0


def period(d: dt.datetime) -> str:
    """night 22:00-04:00, dawn 04:00-08:00, day 08:00-22:00 (local)."""
    h = d.hour
    if h >= 22 or h < 4:
        return "night"
    if h < 8:
        return "dawn"
    return "day"


def day_key(d: dt.datetime) -> str:
    return d.strftime("%Y-%m-%d")


def start_of_day(d: dt.datetime) -> dt.datetime:
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def midnights_between(a: dt.datetime, b: dt.datetime) -> List[dt.datetime]:
    """Local midnights m with a < m <= b, ascending."""
    out = []
    m = start_of_day(a) + dt.timedelta(days=1)
    while m <= b:
        out.append(m)
        m += dt.timedelta(days=1)
    return out


def josa(word: str, pair: str) -> str:
    """Attach a Korean particle: josa("모찌", "이/가") → "모찌가", josa("콩", "이/가") → "콩이"."""
    with_batchim, without = pair.split("/")
    if not word:
        return word + without
    ch = word[-1]
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        has_batchim = (code - 0xAC00) % 28 != 0
    else:
        has_batchim = (ch.isdigit() and ch in "013678") or (ch.isalpha() and ch.lower() not in "aeiou")
    return word + (with_batchim if has_batchim else without)
