"""state.json shape, defaults and migration."""
from __future__ import annotations

import copy
import datetime as dt

from . import clock, economy

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
        "earned": 0, "spent": 0, "purchases": 0, "refusals": 0, "pats": 0,
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


def new_lifetime() -> dict:
    """Counters that survive /pet reset; the dex unlocks read them."""
    return {"tokens_out": 0, "night_out": 0, "pats": 0, "max_coins": 0, "evolutions": 0,
            "attend_streak": 0, "attend_streak_max": 0, "last_attend": None}


def new_state(now: dt.datetime, name: str = DEFAULT_NAME) -> dict:
    ts = clock.fmt(now)
    return {
        "version": VERSION,
        "name": name,
        "created_at": ts,
        "level": 1, "xp": 0, "coins": 0, "coin_carry": 0.0,
        "hunger": 80, "mood": 80,
        "form": "base", "form_since": ts,
        "items_owned": list(economy.STARTER_ITEMS), "equipped": {v: k for k, v in economy.STARTER_ITEMS.items()},
        "last_fed_at": ts, "last_tick_at": ts, "last_turn_at": None, "last_turn_earned": 0,
        "plugin_root": None,
        "speech": "",
        "events": [],
        "sessions": {},
        "daily_log": [new_day(clock.day_key(now))],
        "since_form": new_since_form(),
        "flags": new_flags(),
        "badges": [],
        "settings": {"widget": True, "widget_install_tried": None},
        "species": "mochi",
        "dex": ["mochi"],
        "lifetime": new_lifetime(),
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
    if "lifetime" not in state:                 # pets born before the dex: start from what the log still has
        life = new_lifetime()
        for day in state.get("daily_log", []):
            for k in ("tokens_out", "night_out", "pats"):
                life[k] += int(day.get(k, 0) or 0)
        life["max_coins"] = int(state.get("coins", 0))
        # attendance: the run of consecutive logged days with a session, ending at the newest one
        days = sorted(d["date"] for d in state.get("daily_log", []) if d.get("sessions", 0) > 0)
        run = 0
        for i, d in enumerate(days):
            prev = days[i - 1] if i else None
            consecutive = prev and (dt.date.fromisoformat(d) - dt.date.fromisoformat(prev)).days == 1
            run = run + 1 if consecutive else 1
            life["attend_streak_max"] = max(life["attend_streak_max"], run)
        if days:
            life["attend_streak"], life["last_attend"] = run, days[-1]
        state["lifetime"] = life
    _fill(state, base)
    _fill(state["lifetime"], new_lifetime())
    _fill(state["flags"], new_flags())
    _fill(state["since_form"], new_since_form())
    _fill(state["settings"], base["settings"])
    for item_id, slot in economy.STARTER_ITEMS.items():     # starters added after a pet was born
        if item_id not in state["items_owned"]:
            state["items_owned"].append(item_id)
            state["equipped"].setdefault(slot, item_id)
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
