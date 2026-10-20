"""state.json shape, defaults and migration."""
from __future__ import annotations

import copy
import datetime as dt

from . import clock

VERSION = 1
DEFAULT_NAME = "모찌"
DAILY_LOG_DAYS = 14
EVENT_LIMIT = 20


def new_day(date: str) -> dict:
    return {
        "date": date,
        "feeds": 0, "dawn_feeds": 0, "day_feeds": 0,
        "sessions": 0, "day_sessions": 0,
        "tokens_in": 0, "tokens_out": 0, "cache_read": 0, "night_out": 0,
        "earned": 0, "spent": 0, "purchases": 0, "refusals": 0,
        "hunger_zero_hours": 0.0, "max_gap_hours": 0.0, "zero_balance": False,
    }


def new_since_form() -> dict:
    return {
        "days": 0, "tokens_out": 0, "cache_read": 0, "tokens_in_total": 0,
        "night_out": 0, "dawn_feeds": 0, "day_feeds": 0, "day_sessions": 0,
        "purchases": 0, "refusals": 0, "zero_balance_days": 0,
        "streak_50k": 0, "feed_streak": 0, "balance_ok_streak": 0,
    }


def new_flags() -> dict:
    return {
        "debt": 0, "demand_item": None, "demand_since": None,
        "burnout_until": None, "find_days": [], "boss_hijack": False,
        "thug_days": 0, "rest_day_seen": False,
    }


def new_state(now: dt.datetime, name: str = DEFAULT_NAME) -> dict:
    ts = clock.fmt(now)
    return {
        "version": VERSION,
        "name": name,
        "created_at": ts,
        "level": 1, "xp": 0, "coins": 0, "coin_carry": 0.0,
        "hunger": 80, "mood": 80,
        "form": "base", "form_since": ts,
        "items_owned": ["party_hat"], "equipped": {"head": "party_hat"},
        "last_fed_at": ts, "last_tick_at": ts, "last_turn_at": None, "last_turn_earned": 0,
        "plugin_root": None,
        "speech": "",
        "events": [],
        "sessions": {},
        "daily_log": [new_day(clock.day_key(now))],
        "since_form": new_since_form(),
        "flags": new_flags(),
        "badges": [],
    }


def _fill(target: dict, defaults: dict) -> dict:
    for k, v in defaults.items():
        if k not in target:
            target[k] = copy.deepcopy(v)
    return target


def migrate(state: dict) -> dict:
    """Fill missing keys with defaults. Never drops user data."""
    base = new_state(clock.now())
    base["daily_log"] = []
    _fill(state, base)
    _fill(state["flags"], new_flags())
    _fill(state["since_form"], new_since_form())
    for day in state["daily_log"]:
        _fill(day, new_day(day.get("date", "")))
    state["version"] = VERSION
    return state


def today(state: dict, now: dt.datetime) -> dict:
    key = clock.day_key(now)
    log = state["daily_log"]
    if log and log[-1]["date"] == key:
        return log[-1]
    day = new_day(key)
    log.append(day)
    del log[:-DAILY_LOG_DAYS]
    return day


def push_event(state: dict, now: dt.datetime, type_: str, text: str, **extra) -> dict:
    ev = {"at": clock.fmt(now), "type": type_, "text": text, "delivered": False}
    ev.update(extra)
    state["events"].append(ev)
    del state["events"][:-EVENT_LIMIT]
    return ev
