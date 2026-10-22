"""Vacation (토키 호텔): leave the pet for 1-14 days and time stops for it.

While away nothing decays, no day closes for it (no interest, extortion, sales, demands, form counters),
evolution and dex signs wait, and turns earn no coins. Coming back, hunger and mood are as they were plus
a little rest, and the last meal moves forward by the stay so the starvation and runaway clocks resume.
"""
from __future__ import annotations

import datetime as dt
import math
from typing import Optional

from . import clock, economy, schema, speech_lines

FEE_PER_DAY = 20
MAX_DAYS = 14
MONTH_DAYS = 20
MOOD_BONUS = 10
BLOCKED = {"thug": "호텔이 불량배는 체크인을 안 받아 준대요. 밥부터 챙겨 주세요",
           "boss": "호텔이 조직 보스는 체크인을 안 받아 준대요. 밥부터 챙겨 주세요",
           "runaway": "가출 중이라 맡길 수 없어요. /pet find 로 찾아보세요"}
WEEKDAY = "월화수목금토일"


class VacationError(Exception):
    pass


def active(state: dict) -> Optional[dict]:
    return state.get("vacation") or None


def when(d: dt.datetime) -> str:
    """10/27(월) 14:00"""
    return f"{d.month}/{d.day}({WEEKDAY[d.weekday()]}) {d:%H:%M}"


def short_when(d: dt.datetime) -> str:
    return f"{d.month}/{d.day} {d:%H:%M}"


def d_label(state: dict, now: dt.datetime) -> str:
    """D-2 · D-1 · D-DAY by calendar day, like a countdown on a door sign."""
    vac = active(state)
    if not vac:
        return ""
    left = (clock.parse(vac["until"]).date() - now.date()).days
    return "D-DAY" if left <= 0 else f"D-{left}"


def month_key(d: dt.datetime) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def used_this_month(state: dict, now: dt.datetime) -> int:
    return int(state["settings"].get("vacation_days", {}).get(month_key(now), 0))


def _add_month_days(state: dict, key: str, n: int) -> None:
    days = state["settings"].setdefault("vacation_days", {})
    days[key] = max(0, int(days.get(key, 0)) + n)
    for k in sorted(days)[:-12]:              # a year is plenty
        del days[k]


def line(state: dict, kind: str) -> str:
    lines = speech_lines.VACATION.get(state.get("species", "mochi")) or speech_lines.VACATION["mochi"]
    return lines[kind]


def refused(state: dict) -> str:
    """What /pet feed and friends say while the pet is at the hotel."""
    vac = active(state)
    until = clock.parse(vac["until"])
    return (f"{clock.josa(state['name'], '은/는')} 토키 호텔에 묵고 있어요. {short_when(until)} 복귀 · "
            f"일찍 데려오려면 /pet vacation end")


def start(state: dict, now: dt.datetime, days_arg: str) -> dict:
    if active(state):
        until = clock.parse(state["vacation"]["until"])
        raise VacationError(f"이미 휴가 중이에요 ({short_when(until)} 복귀). 늘리려면 데려온 뒤 다시 맡겨 주세요")
    try:
        days = int(days_arg.rstrip("일d"))
    except ValueError:
        raise VacationError(f"1~{MAX_DAYS}일 사이로 정해 주세요")
    if not 1 <= days <= MAX_DAYS:
        raise VacationError(f"1~{MAX_DAYS}일 사이로 정해 주세요")
    if state["form"] in BLOCKED:
        raise VacationError(BLOCKED[state["form"]])
    left = MONTH_DAYS - used_this_month(state, now)
    if days > left:
        raise VacationError(f"이번 달 휴가는 {MONTH_DAYS}일까지예요. 남은 날: {max(0, left)}일")
    fee = FEE_PER_DAY * days
    if state["coins"] < fee:
        raise VacationError(f"숙박비 {fee}코인이 필요해요 (지금 🪙 {state['coins']:,})")
    state["coins"] -= fee
    until = now + dt.timedelta(days=days)
    state["vacation"] = {"since": clock.fmt(now), "until": clock.fmt(until), "days": days, "fee": fee,
                         "month": month_key(now)}
    _add_month_days(state, month_key(now), days)
    schema.push_event(state, now, "vacation_leave", line(state, "leave"))
    state["speech"] = line(state, "away")
    return {"days": days, "fee": fee, "until": clock.fmt(until), "coins": state["coins"],
            "used": used_this_month(state, now)}


def finish(state: dict, at: dt.datetime, early: bool) -> dict:
    """Back from the hotel at `at`. Early: refund the whole days not stayed, and give them back to the month."""
    vac = state["vacation"]
    since, until = clock.parse(vac["since"]), clock.parse(vac["until"])
    unused = max(0, math.floor((until - at).total_seconds() / 86400)) if early else 0
    refund = unused * FEE_PER_DAY
    state["coins"] += refund
    if unused:
        _add_month_days(state, vac.get("month") or month_key(since), -unused)
    stayed = at - since
    state["last_fed_at"] = clock.fmt(clock.parse(state["last_fed_at"]) + stayed)
    state["mood"] = round(min(100.0, float(state["mood"]) + MOOD_BONUS), 2)
    state["vacation"] = None
    kind = "early" if early else "back"
    schema.push_event(state, at, f"vacation_{kind}", line(state, kind))
    state["speech"] = line(state, kind)
    return {"early": early, "refund": refund, "unused": unused, "coins": state["coins"]}


def status_text(state: dict, now: dt.datetime) -> str:
    vac = active(state)
    name = state["name"]
    if not vac:
        left = MONTH_DAYS - used_this_month(state, now)
        return (f"{clock.josa(name, '은/는')} 집에 있어요\n"
                f"  /pet vacation <1~{MAX_DAYS}> 로 토키 호텔에 보낼 수 있어요\n"
                f"  숙박비 하루 {FEE_PER_DAY}코인 · 이번 달 남은 휴가 {max(0, left)}일")
    since, until = clock.parse(vac["since"]), clock.parse(vac["until"])
    return (f"🏖 {name} 휴가 중 · {d_label(state, now)}\n"
            f"  {when(since)} → {when(until)}\n"
            f"  배고픔 {round(state['hunger'])} · 기분 {round(state['mood'])} (맡길 때 그대로)\n"
            f"  이번 달 휴가 {used_this_month(state, now)}/{MONTH_DAYS}일\n"
            f"  호텔 쪽지: {line(state, 'away')}")


def payload(state: dict, now: dt.datetime) -> dict:
    """What the widget needs to draw the hotel and its buttons."""
    vac = active(state)
    used = used_this_month(state, now)
    out = {"fee_per_day": FEE_PER_DAY, "max_days": MAX_DAYS, "month_days": MONTH_DAYS, "used": used,
           "blocked": BLOCKED.get(state["form"])}
    if vac:
        until = clock.parse(vac["until"])
        unused = max(0, math.floor((until - now).total_seconds() / 86400))
        out.update(since=vac["since"], until=vac["until"], d=d_label(state, now), when=when(until),
                   refund=unused * FEE_PER_DAY, away=line(state, "away"))
    return out
