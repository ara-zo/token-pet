"""Evolution judgement. Pure functions over state; see design §8."""
from __future__ import annotations

import datetime as dt
from typing import List, Optional

from . import clock, economy, schema, speech_lines

# v1 catalog has 7 items, so the spec's 8/15 thresholds are unreachable.
# Scaled down until the catalog grows (documented in README 미정).
SPENDER_ITEMS = 4
INFLUENCER_ITEMS = 6

THUG_ZERO_HOURS = 72
OWL_NIGHT_RATIO = 0.6
MISER_COINS = 1000
MISER_MAX_FEEDS = 7
SPENDER_SPEND_RATIO = 0.8
SCHOLAR_CACHE_RATIO = 0.7
BURNOUT_STREAK = 5
BURNOUT_DAILY_OUT = 500_000
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
            and economy.bought_count(state) >= SPENDER_ITEMS:
        return "spender"
    return "model"


def judge_second(state: dict) -> str:
    form = state["form"]
    sf = state["since_form"]
    items = economy.bought_count(state)
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
    grant(state, economy.GRANT_ON_FORM.get(form), now)
    name = economy.FORMS[form].ko
    # evolution is the exchange's qualification exam: an assignment, not a pass/fail (docs/LORE.md)
    text = f"환전소 통지서: {clock.josa(state['name'], '은/는')} {name} 과정에 배정되었습니다 ({reason})"
    return schema.push_event(state, now, "evolve", text, form=form, old_form=old)


def grant(state: dict, item_id, now: dt.datetime) -> None:
    if item_id and item_id not in state["items_owned"]:
        state["items_owned"].append(item_id)
        schema.push_event(state, now, "unlock", f"배경 해금: {economy.CATALOG[item_id].name}", item=item_id)


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
                events.append(schema.push_event(state, now, "runaway", speech_lines.EVENTS["runaway"].format(name=clock.josa(state["name"], "이/가"))))
                return events
            if sf["feed_streak"] >= REHAB_FEED_STREAK:
                _add_badge(state, "rehab")
                state["form"] = "base"
                events.append(schema.push_event(state, now, "rehab", speech_lines.EVENTS["rehab"]))
                form = "base"
        elif clock.hours_between(clock.parse(state["last_fed_at"]), now) >= RUNAWAY_HOURS:
            state["coins"] //= 2
            events.append(set_form(state, "runaway", now, "7일 방치"))
            events.append(schema.push_event(state, now, "runaway", speech_lines.EVENTS["runaway"].format(name=clock.josa(state["name"], "이/가"))))
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


# ----------------------------------------------------------------- forecast
# Which form the pet is heading for, from the same records the judgement uses.
# Shown to the user before the evolution so the 5-day wait has a direction.

def _pct(x: float) -> str:
    return f"{x:.0%}"


def _first_reason(state: dict, form: str) -> str:
    w = window(state)
    night = w["night_out"] / w["tokens_out"] if w["tokens_out"] else 0.0
    if form == "thug":
        return f"배고픔 0으로 {w['hunger_zero_hours']:.0f}시간을 보냈어요"
    if form == "owl":
        return f"출력의 {_pct(night)}를 밤 10시~새벽 4시에 썼어요"
    if form == "miser":
        return f"코인 {state['coins']:,}개를 모으고 아무것도 안 샀어요"
    if form == "spender":
        return f"번 코인의 {_pct(w['spent'] / w['earned'])}를 꾸미기에 썼어요"
    # model: point at the closest other road, if any
    if night >= OWL_NIGHT_RATIO * 2 / 3:
        return f"밤 출력이 {_pct(night)}예요. {_pct(OWL_NIGHT_RATIO)}를 넘으면 올빼미가 돼요"
    if w["hunger_zero_hours"] >= THUG_ZERO_HOURS / 2:
        return f"배고픔 0으로 {w['hunger_zero_hours']:.0f}시간… {THUG_ZERO_HOURS}시간이면 불량배가 돼요"
    if state["coins"] >= MISER_COINS / 2 and w["purchases"] == 0:
        return f"코인을 모으기만 해요. {MISER_COINS:,}개를 넘기면 구두쇠가 돼요"
    return "규칙적으로 지내고 있어요"


def _second_reason(state: dict, form: str, target: str) -> str:
    sf = state["since_form"]
    cache = sf["cache_read"] / sf["tokens_in_total"] if sf["tokens_in_total"] else 0.0
    night = sf["night_out"] / sf["tokens_out"] if sf["tokens_out"] else 0.0
    if target == "burnout":
        return f"하루 출력 {BURNOUT_DAILY_OUT // 10000}만 토큰 넘게 {sf['streak_50k']}일 연속 일했어요"
    if target == "scholar":
        return f"캐시 적중률이 {_pct(cache)}예요"
    if target == "tycoon":
        return "코인을 많이 모았고 지갑도 열어요"
    if target == "loanshark":
        return "코인은 많은데 한 번도 안 썼어요"
    if target == "vampire":
        return f"출력의 {_pct(night)}가 밤이고 낮에는 안 먹어요"
    if target == "hunter":
        return f"새벽에 {sf['dawn_feeds']}번 밥을 먹었어요"
    if target == "broke":
        return "잔액 0인 날이 많아요"
    if target == "influencer":
        return f"아이템을 {economy.bought_count(state)}개 모았어요"
    if target == "boss":
        return "불량배로 계속 지내면 조직 보스가 돼요"
    # staying the same: hint at the nearest change for the model student
    if form == "model" and sf["streak_50k"] >= BURNOUT_STREAK - 2:
        return f"하루 출력 {BURNOUT_DAILY_OUT // 10000}만 토큰 넘게 {sf['streak_50k']}일 연속… {BURNOUT_STREAK}일이면 번아웃이에요"
    if form == "model" and cache >= SCHOLAR_CACHE_RATIO * 0.7:
        return f"캐시 적중률 {_pct(cache)}. {_pct(SCHOLAR_CACHE_RATIO)}를 넘으면 박사가 돼요"
    return "지금 모습 그대로 자랄 것 같아요"


def forecast(state: dict) -> Optional[dict]:
    """The form the next evolution would pick today, or None when no evolution is ahead."""
    form = state["form"]
    if form == "base":
        target, at_level = judge_first(state), economy.FIRST_EVOLUTION_LEVEL
        reason = _first_reason(state, target)
    elif form in economy.FIRST_TIER and form != "runaway":
        target, at_level = judge_second(state), economy.SECOND_EVOLUTION_LEVEL
        reason = _second_reason(state, form, target)
    else:
        return None
    info = economy.FORMS[target]
    need = economy.xp_for_level(at_level)
    return {
        "form": target, "ko": info.ko, "glyph": info.glyph, "reason": reason,
        "at_level": at_level, "progress": round(min(1.0, state["xp"] / need), 3) if need else 1.0,
    }
