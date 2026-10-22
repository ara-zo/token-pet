"""Pick the pet's speech bubble line from state."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from . import clock, economy, schema
from . import speech_lines as L

RECENT_EVENT_MINUTES = 10

EVENT_TYPES_TO_SPEAK = ("evolve", "runaway", "extort", "demand", "sold", "rehab", "born", "debt", "softcap")


def _fmt_k(n: int) -> str:
    return f"{n/1000:.1f}k" if n >= 1000 else str(n)


def _pick(form: str, situation: str, now: dt.datetime, species: str = "mochi", **fmt) -> Optional[str]:
    """One line for the situation, rotating hourly so the bubble doesn't feel stuck."""
    options = [t for t in L.lines(form, situation, species)
               if all("{" + k + "}" not in t or fmt.get(k) is not None for k in ("n", "out", "item", "mood", "fuel"))]
    if not options:
        return None
    line = options[(now.toordinal() * 24 + now.hour) % len(options)]
    return line.format(**{k: v for k, v in fmt.items() if v is not None}) if "{" in line else line


def choose(state: dict, now: dt.datetime, situation: Optional[str] = None, **fmt) -> str:
    """Recent event > reaction to what just happened (FEED, PAT, BUY, EARN, REFUSE) > mood of the moment."""
    for ev in reversed(state["events"]):
        if ev["type"] not in EVENT_TYPES_TO_SPEAK:
            continue
        try:
            age = clock.hours_between(clock.parse(ev["at"]), now) * 60
        except ValueError:
            continue
        if age <= RECENT_EVENT_MINUTES:
            return ev["text"]
        break
    form = state["form"]
    night = clock.period(now) == "night"
    fmt = {"mood": round(state["mood"]), "fuel": round(state["hunger"]), **fmt}
    pick = lambda f, sit, **more: _pick(f, sit, now, state.get("species", "mochi"), **{**fmt, **more})
    if situation:
        line = pick(form, situation)
        if line:
            return line
    if form == "runaway":
        return pick(form, L.IDLE)
    if state["hunger"] < 20:
        out = schema.today(state, now)["tokens_out"]
        return pick(form, L.HUNGRY, out=_fmt_k(out) if out else None) or "배고파… 밥 줘"
    if state["mood"] < 30:
        return pick(form, L.BORED)
    flags = state["flags"]
    if form in ("spender", "influencer") and flags.get("demand_item"):
        return f"신상 {economy.CATALOG[flags['demand_item']].name} 사줘!"
    if form in economy.NOCTURNAL:
        return (pick(form, L.NIGHT) or pick(form, L.IDLE)) if night else "zzz…"
    return pick(form, L.IDLE)
