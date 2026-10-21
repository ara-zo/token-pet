"""Lazy time integration: hunger/mood decay, midnight rollover, daily form effects.

`apply(state, now)` is called by store.transaction() on every open, so the pet
ages correctly no matter which script touches it or how long nothing ran.
"""
from __future__ import annotations

import datetime as dt
import math
from typing import List

from . import clock, economy, evolve, schema, speech_lines

SESSION_TTL_HOURS = 7 * 24
RUNAWAY_HOURS = 7 * 24


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def decay(state: dict, start: dt.datetime, end: dt.datetime) -> None:
    """Integrate hunger/mood over [start, end]; the segment must not cross midnight."""
    h = clock.hours_between(start, end)
    if h <= 0:
        return
    form = state["form"]
    rate = economy.HUNGER_PER_HOUR * economy.hunger_rate(form)
    hunger = float(state["hunger"])
    hours_until_zero = hunger / rate if rate > 0 else math.inf
    if h <= hours_until_zero:
        zero_hours = 0.0
        hunger -= rate * h
    else:
        zero_hours = h - hours_until_zero
        hunger = 0.0
    mood = float(state["mood"])
    mood -= economy.MOOD_PER_HOUR * (h - zero_hours) + economy.MOOD_PER_HOUR_STARVING * zero_hours
    state["hunger"] = round(_clamp(hunger, 0, 100), 2)
    state["mood"] = round(_clamp(mood, economy.mood_floor(form), 100), 2)
    if zero_hours > 0:
        day = schema.today(state, start)
        day["hunger_zero_hours"] = round(day["hunger_zero_hours"] + zero_hours, 3)


def _pick_demand(state: dict):
    unowned = [k for k in economy.CATALOG if k not in state["items_owned"] and economy.for_sale(k)]
    unowned.sort(key=lambda k: economy.CATALOG[k].price)
    return unowned[0] if unowned else None


def close_day(state: dict, day: dict, now: dt.datetime) -> List[dict]:
    """Finalize `day` at midnight. Order matters: refusals → aggregates → streaks → money → new demand."""
    events: List[dict] = []
    form = state["form"]
    flags = state["flags"]
    sf = state["since_form"]

    # 1. unanswered demand counts as a refusal on the closed day
    if form in ("spender", "influencer") and flags.get("demand_item"):
        day["refusals"] += 1

    # 2. aggregate into since_form
    sf["days"] += 1
    for k_day, k_sf in (("tokens_out", "tokens_out"), ("cache_read", "cache_read"),
                        ("tokens_in", "tokens_in_total"), ("night_out", "night_out"),
                        ("dawn_feeds", "dawn_feeds"), ("day_feeds", "day_feeds"),
                        ("day_sessions", "day_sessions"), ("purchases", "purchases"),
                        ("refusals", "refusals")):
        sf[k_sf] += day[k_day]

    # 3. streaks
    day["zero_balance"] = state["coins"] <= 0
    if day["zero_balance"]:
        sf["zero_balance_days"] += 1
    sf["streak_50k"] = sf["streak_50k"] + 1 if day["tokens_out"] >= evolve.BURNOUT_DAILY_OUT else 0
    sf["feed_streak"] = sf["feed_streak"] + 1 if day["feeds"] >= 1 else 0
    sf["balance_ok_streak"] = sf["balance_ok_streak"] + 1 if state["coins"] >= 500 else 0
    if form == "thug":
        flags["thug_days"] = flags["thug_days"] + 1 if day["feeds"] == 0 else 0
    if form == "burnout" and day["tokens_out"] == 0:
        flags["rest_day_seen"] = True

    # 4. money effects
    if form in economy.DAILY_INTEREST and state["coins"] > 0:
        rate = economy.DAILY_INTEREST[form] + economy.bg_bonus(economy.BG_INTEREST_BONUS, state)
        gain = int(state["coins"] * rate)
        if gain:
            state["coins"] += gain
            events.append(schema.push_event(state, now, "interest", f"이자 +{gain}"))
    if form in economy.DAILY_EXTORTION and state["coins"] > 0:
        loss = int(state["coins"] * economy.DAILY_EXTORTION[form])
        if loss:
            state["coins"] -= loss
            events.append(schema.push_event(state, now, "extort", f"{economy.FORMS[form].ko}가 {loss}코인을 삥뜯어 갔다"))
    if form == "loanshark" and flags["debt"] > 0:
        flags["debt"] += math.ceil(flags["debt"] * economy.LOANSHARK_INTEREST)
        pay = min(state["coins"], flags["debt"])
        state["coins"] -= pay
        flags["debt"] -= pay
        if pay:
            events.append(schema.push_event(state, now, "debt", f"외상 이자로 {pay}코인 차감 (남은 외상 {flags['debt']})"))
    if form == "broke":
        sellable = [k for k in state["items_owned"] if k in economy.CATALOG and economy.for_sale(k)]
        if sellable:
            item = max(sellable, key=lambda k: economy.CATALOG[k].price)
            got = int(economy.CATALOG[item].price * economy.BROKE_SELL_RATIO)
            state["items_owned"].remove(item)
            for slot, eq in list(state["equipped"].items()):
                if eq == item:
                    del state["equipped"][slot]
            state["coins"] += got
            state["mood"] = round(_clamp(state["mood"] - economy.BROKE_MOOD_HIT, 0, 100), 2)
            events.append(schema.push_event(state, now, "sold", speech_lines.EVENTS["sold"].format(
                item=clock.josa(economy.CATALOG[item].name, "이/가"), coins=got)))

    mood_bonus = economy.bg_bonus(economy.BG_MOOD_BONUS, state)
    if mood_bonus:
        state["mood"] = round(_clamp(state["mood"] + mood_bonus, 0, 100), 2)

    # 5. new demand for the new day
    if form in ("spender", "influencer"):
        want = _pick_demand(state)
        flags["demand_item"] = want
        flags["demand_since"] = clock.fmt(now) if want else None
        if want:
            events.append(schema.push_event(state, now, "demand", f"신상 {economy.CATALOG[want].name} 사줘!", item=want))
    return events


def apply(state: dict, now: dt.datetime) -> List[dict]:
    events: List[dict] = []
    last = clock.parse(state["last_tick_at"])
    if now < last:
        state["last_tick_at"] = clock.fmt(now)
        return events
    cursor = last
    for midnight in clock.midnights_between(last, now):
        decay(state, cursor, midnight)
        closed = schema.today(state, cursor)
        events += close_day(state, closed, midnight)
        schema.today(state, midnight)
        cursor = midnight
    decay(state, cursor, now)
    schema.today(state, now)

    day = schema.today(state, now)
    gap = clock.hours_between(clock.parse(state["last_fed_at"]), now)
    if gap > day["max_gap_hours"]:
        day["max_gap_hours"] = round(gap, 2)

    for sid, info in list(state["sessions"].items()):
        try:
            age = clock.hours_between(clock.parse(info["updated_at"]), now)
        except (KeyError, ValueError):
            age = SESSION_TTL_HOURS + 1
        if age > SESSION_TTL_HOURS:
            del state["sessions"][sid]

    state["last_tick_at"] = clock.fmt(now)
    from . import evolve
    events += evolve.check(state, now)
    state["forecast"] = evolve.forecast(state)
    from . import species
    events += species.check(state, now)
    return events
