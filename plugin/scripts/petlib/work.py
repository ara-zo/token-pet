"""Working tires the pet: output makes it hungry, a rushed hour costs mood, a moderate day lifts it."""
from __future__ import annotations

import datetime as dt

from . import economy, schema, speech_lines


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def apply_output(state: dict, ts: dt.datetime, output: int, now: dt.datetime) -> float:
    """One turn's output at `ts` (local time): hunger for the work, mood for the part past the hourly rush line.
    Returns the hunger it cost."""
    if output <= 0:
        return 0.0
    form = state["form"]
    before_hunger = state["hunger"]
    hunger = before_hunger - output * economy.WORK_HUNGER_PER_OUT * economy.hunger_rate(form)
    state["hunger"] = round(_clamp(hunger, 0, 100), 2)

    hour = ts.strftime("%Y-%m-%dT%H")
    wh = state.get("work_hour") or {}
    if wh.get("hour") != hour:
        wh = {"hour": hour, "out": 0, "tired": False}
    before = wh["out"]
    wh["out"] = before + output
    over = max(0, wh["out"] - economy.RUSH_OUT_PER_HOUR) - max(0, before - economy.RUSH_OUT_PER_HOUR)
    if over > 0:
        mood = state["mood"] - over * economy.RUSH_MOOD_PER_OUT
        state["mood"] = round(_clamp(mood, economy.mood_floor(form), 100), 2)
        if not wh["tired"]:                  # one bubble per rushed hour
            wh["tired"] = True
            schema.push_event(state, now, "tired", speech_lines.EVENTS["tired"])
    state["work_hour"] = wh
    return before_hunger - state["hunger"]


def close_day(state: dict, day: dict, now: dt.datetime) -> list:
    """Midnight: a day of moderate work lifts mood."""
    lo, hi = economy.GOOD_DAY_OUT
    if not lo <= day["tokens_out"] <= hi or state["form"] == "runaway":
        return []
    state["mood"] = round(_clamp(state["mood"] + economy.GOOD_DAY_MOOD, 0, 100), 2)
    return [schema.push_event(state, now, "goodday", speech_lines.EVENTS["goodday"])]
