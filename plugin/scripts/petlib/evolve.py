"""Evolution judgement. Pure functions over state; see design §8."""
from __future__ import annotations

import datetime as dt
from typing import List

from . import clock, economy, schema

# v1 catalog has 7 items, so the spec's 8/15 thresholds are unreachable.
# Scaled down until the catalog grows (documented in README 미정).
SPENDER_ITEMS = 4
INFLUENCER_ITEMS = 6

THUG_ZERO_HOURS = 48
OWL_NIGHT_RATIO = 0.6
MISER_COINS = 2000
MISER_MAX_FEEDS = 7
SPENDER_SPEND_RATIO = 0.8
SCHOLAR_CACHE_RATIO = 0.7
BURNOUT_STREAK = 5
RICH_COINS = 10000
HUNTER_DAWN_FEEDS = 3
VAMPIRE_NIGHT_RATIO = 0.9
BROKE_ZERO_DAYS = 5
BROKE_REFUSALS = 5
INFLUENCER_MAX_REFUSALS = 3
REHAB_FEED_STREAK = 3
THUG_RUNAWAY_DAYS = 3
RUNAWAY_HOURS = 7 * 24
VAMPIRE_RECOVER_DAY_FEEDS = 3
BROKE_RECOVER_STREAK = 3


def window(state: dict, days: int = 7) -> dict:
    keys = ("feeds", "hunger_zero_hours", "tokens_out", "night_out", "purchases", "spent", "earned")
    out = {k: 0 for k in keys}
    for day in state["daily_log"][-days:]:
        for k in keys:
            out[k] += day.get(k, 0)
    return out


def judge_first(state: dict) -> str:
    w = window(state)
    if w["hunger_zero_hours"] >= THUG_ZERO_HOURS:
        return "thug"
    if w["tokens_out"] > 0 and w["night_out"] / w["tokens_out"] >= OWL_NIGHT_RATIO:
        return "owl"
    if state["coins"] >= MISER_COINS and w["purchases"] == 0 and w["feeds"] <= MISER_MAX_FEEDS:
        return "miser"
    if w["earned"] > 0 and w["spent"] >= SPENDER_SPEND_RATIO * w["earned"] \
            and len(state["items_owned"]) >= SPENDER_ITEMS:
        return "spender"
    return "model"


def judge_second(state: dict) -> str:
    form = state["form"]
    sf = state["since_form"]
    items = len(state["items_owned"])
    if form == "model":
        if sf["streak_50k"] >= BURNOUT_STREAK:
            return "burnout"
        if sf["tokens_in_total"] > 0 and sf["cache_read"] / sf["tokens_in_total"] >= SCHOLAR_CACHE_RATIO:
            return "scholar"
    elif form == "miser":
        if state["coins"] >= RICH_COINS:
            return "tycoon" if sf["purchases"] >= 1 else "loanshark"
    elif form == "owl":
        if sf["tokens_out"] > 0 and sf["night_out"] / sf["tokens_out"] >= VAMPIRE_NIGHT_RATIO \
                and sf["day_feeds"] == 0:
            return "vampire"
        if sf["dawn_feeds"] >= HUNTER_DAWN_FEEDS:
            return "hunter"
    elif form == "spender":
        if sf["zero_balance_days"] >= BROKE_ZERO_DAYS and sf["refusals"] >= BROKE_REFUSALS:
            return "broke"
        if items >= INFLUENCER_ITEMS and sf["refusals"] <= INFLUENCER_MAX_REFUSALS:
            return "influencer"
    elif form == "thug":
        return "boss"
    return form


def set_form(state: dict, form: str, now: dt.datetime, reason: str) -> dict:
    old = state["form"]
    state["form"] = form
    state["form_since"] = clock.fmt(now)
    state["since_form"] = schema.new_since_form()
    flags = state["flags"]
    flags["thug_days"] = 0
    flags["rest_day_seen"] = False
    flags["burnout_until"] = clock.fmt(now + dt.timedelta(days=economy.BURNOUT_DAYS)) if form == "burnout" else None
    flags["boss_hijack"] = form == "boss"
    if form not in ("spender", "influencer"):
        flags["demand_item"] = None
        flags["demand_since"] = None
    if form != "runaway":
        flags["find_days"] = []
    name = economy.FORMS[form].ko
    text = f"{clock.josa(state['name'], '이/가')} {clock.josa(name, '으로/로')} 진화했다! ({reason})"
    return schema.push_event(state, now, "evolve", text, form=form, old_form=old)


def _add_badge(state: dict, badge: str) -> None:
    if badge not in state["badges"]:
        state["badges"].append(badge)


def burnout_active(state: dict, now: dt.datetime) -> bool:
    until = state["flags"].get("burnout_until")
    return state["form"] == "burnout" and bool(until) and now < clock.parse(until)


def check(state: dict, now: dt.datetime) -> List[dict]:
    events: List[dict] = []
    form = state["form"]
    level = state["level"]
    flags = state["flags"]
    sf = state["since_form"]
    if form in ("runaway", "boss"):
        return events

    if level >= economy.FIRST_EVOLUTION_LEVEL:
        w = window(state)
        if form != "thug" and w["hunger_zero_hours"] >= THUG_ZERO_HOURS:
            events.append(set_form(state, "thug", now, "배고픔 0으로 48시간 방치"))
            return events
        if form == "thug":
            if flags["thug_days"] >= THUG_RUNAWAY_DAYS:
                state["coins"] //= 2
                events.append(set_form(state, "runaway", now, "불량배 상태로 3일 방치"))
                events.append(schema.push_event(state, now, "runaway", f"{clock.josa(state['name'], '이/가')} 코인 절반을 들고 가출했다… /pet find"))
                return events
            if sf["feed_streak"] >= REHAB_FEED_STREAK:
                _add_badge(state, "rehab")
                state["form"] = "base"
                events.append(schema.push_event(state, now, "rehab", f"{clock.josa(state['name'], '이/가')} 갱생했다!"))
                form = "base"
        elif clock.hours_between(clock.parse(state["last_fed_at"]), now) >= RUNAWAY_HOURS:
            state["coins"] //= 2
            events.append(set_form(state, "runaway", now, "7일 방치"))
            events.append(schema.push_event(state, now, "runaway", f"{clock.josa(state['name'], '이/가')} 코인 절반을 들고 가출했다… /pet find"))
            return events

    if form == "base" and level >= economy.FIRST_EVOLUTION_LEVEL:
        events.append(set_form(state, judge_first(state), now, "Lv.5 도달, 지난 7일 생활 기록"))
        form = state["form"]

    # recoveries from fallen forms (checked before second-tier judgement)
    if form == "burnout" and not burnout_active(state, now) and flags["rest_day_seen"]:
        events.append(set_form(state, "model", now, "하루 푹 쉬고 회복"))
        form = "model"
    elif form == "vampire" and sf["day_feeds"] >= VAMPIRE_RECOVER_DAY_FEEDS:
        events.append(set_form(state, "owl", now, "낮 급식 3회로 복귀"))
        form = "owl"
    elif form == "loanshark" and sf["purchases"] >= 1:
        events.append(set_form(state, "tycoon", now, "드디어 지갑을 열었다"))
        form = "tycoon"
    elif form == "broke" and sf["balance_ok_streak"] >= BROKE_RECOVER_STREAK:
        events.append(set_form(state, "spender", now, "3일 연속 잔액 500 유지"))
        form = "spender"

    if level >= economy.SECOND_EVOLUTION_LEVEL and form in economy.FIRST_TIER:
        new = judge_second(state)
        if new != form:
            events.append(set_form(state, new, now, "Lv.10 도달, Lv.5 이후 생활 기록"))
    return events
