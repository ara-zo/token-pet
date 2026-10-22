"""User actions: feed, pat, buy, equip, rename, find, reset. Each mutates state and returns a summary dict."""
from __future__ import annotations

import datetime as dt

from . import clock, economy, schema, speech_lines, vacation

MAX_NAME_LEN = 8


class ActionError(Exception):
    """User-facing refusal. Message is shown verbatim."""


def feed(state: dict, now: dt.datetime, force: bool = False) -> dict:
    _at_home(state)
    form = state["form"]
    period = clock.period(now)
    reason = economy.feed_blocked(form, period)
    cost = economy.FEED_COST
    if reason:
        if form == "vampire" and force:
            cost = economy.FORCE_FEED_COST
        else:
            raise ActionError(reason)
    flags = state["flags"]
    if state["coins"] < cost:
        if form == "loanshark":
            short = cost - state["coins"]
            flags["debt"] += short
            state["coins"] += short
        else:
            raise ActionError(f"코인이 모자라. {cost}코인 필요한데 {state['coins']}코인뿐이야")
    state["coins"] -= cost
    state["hunger"] = round(min(100.0, float(state["hunger"]) + economy.FEED_HUNGER), 2)
    state["last_fed_at"] = clock.fmt(now)
    day = schema.today(state, now)
    day["feeds"] += 1
    if period == "dawn":
        day["dawn_feeds"] += 1
    elif period == "day":
        day["day_feeds"] += 1
    schema.push_event(state, now, "feed", "냠냠! 고마워")
    return {"hunger": state["hunger"], "coins": state["coins"], "cost": cost, "debt": flags["debt"]}


def _at_home(state: dict) -> None:
    if vacation.active(state):
        raise ActionError(vacation.refused(state))


def pat(state: dict, now: dt.datetime) -> dict:
    _at_home(state)
    if state["form"] == "runaway":
        raise ActionError("가출 중이라 쓰다듬을 수 없어. /pet find 로 찾아봐")
    day = schema.today(state, now)
    if day["pats"] >= economy.PAT_DAILY_LIMIT:
        line = speech_lines.PAT_LIMIT.get(state.get("species"), speech_lines.PAT_LIMIT["mochi"])
        raise ActionError(line.format(limit=economy.PAT_DAILY_LIMIT))
    day["pats"] += 1
    state["lifetime"]["pats"] = state["lifetime"].get("pats", 0) + 1
    state["mood"] = round(min(100.0, float(state["mood"]) + economy.PAT_MOOD), 2)
    return {"mood": state["mood"], "left": economy.PAT_DAILY_LIMIT - day["pats"]}


def buy(state: dict, now: dt.datetime, item_id: str) -> dict:
    if item_id not in economy.CATALOG:
        raise ActionError(f"그런 아이템은 없어: {item_id}")
    form = state["form"]
    if economy.shop_blocked(form):
        raise ActionError("상점이 봉쇄됐어. 지금은 살 수 없어")
    if item_id in state["items_owned"]:
        raise ActionError("이미 갖고 있어")
    if not economy.for_sale(item_id):
        item = economy.CATALOG[item_id]
        raise ActionError(f"{item.name}은(는) 파는 게 아니야" + (f". {item.grant}" if item.grant else ""))
    if not economy.is_unlocked(item_id, state):
        item = economy.CATALOG[item_id]
        if item.forms:
            raise ActionError(f"{item.name}은(는) {economy.FORM_ONLY_KO.get(item.forms[0], '특정 형태만')} 살 수 있어")
        raise ActionError(f"{item.name}은(는) Lv.{item.min_level}부터")
    cost = economy.price(item_id, form)
    if state["coins"] < cost:
        raise ActionError(f"코인이 모자라. {cost}코인 필요한데 {state['coins']}코인뿐이야")
    state["coins"] -= cost
    refund = 0
    if form == "influencer":
        refund = int(cost * economy.INFLUENCER_REFUND)
        state["coins"] += refund
    state["items_owned"].append(item_id)
    day = schema.today(state, now)
    day["spent"] += cost
    day["purchases"] += 1
    flags = state["flags"]
    if flags.get("demand_item") == item_id:
        flags["demand_item"] = None
        flags["demand_since"] = None
    schema.push_event(state, now, "buy", f"{economy.CATALOG[item_id].name} 득템!")
    return {"item": item_id, "cost": cost, "refund": refund, "coins": state["coins"]}


def equip(state: dict, item_id: str) -> dict:
    if item_id not in economy.CATALOG or economy.CATALOG[item_id].slot != "hotel":
        _at_home(state)               # a hotel can be changed from afar: the pet just moves
    if item_id not in state["items_owned"]:
        raise ActionError("안 갖고 있는 아이템이야")
    slot = economy.CATALOG[item_id].slot
    state["equipped"][slot] = item_id
    return {"slot": slot, "item": item_id}


def unequip(state: dict, slot: str) -> dict:
    if slot == "hotel":
        raise ActionError("호텔은 하나는 있어야 해. 다른 호텔로 바꿔 줘")
    _at_home(state)
    if slot not in economy.SLOTS:
        raise ActionError(f"슬롯은 {', '.join(economy.SLOTS)} 중 하나")
    removed = state["equipped"].pop(slot, None)
    return {"slot": slot, "removed": removed}


def rename(state: dict, name: str) -> dict:
    name = name.strip()
    if not 1 <= len(name) <= MAX_NAME_LEN:
        raise ActionError(f"이름은 1~{MAX_NAME_LEN}자")
    state["name"] = name
    return {"name": name}


def find(state: dict, now: dt.datetime) -> dict:
    if state["form"] != "runaway":
        raise ActionError("가출한 상태가 아니야")
    from . import evolve
    days = state["flags"]["find_days"]
    key = clock.day_key(now)
    if key not in days:
        days.append(key)
    if len(days) >= 3:
        state["badges"].append("returned") if "returned" not in state["badges"] else None
        evolve.set_form(state, "model", now, "3일간 찾아다닌 끝에 귀환")
        evolve.grant(state, economy.GRANT_ON_RETURN, now)
        state["hunger"] = 50.0
        return {"found": True, "days": len(days)}
    return {"found": False, "days": len(days)}


def reset(state: dict, now: dt.datetime, confirm: bool = False) -> dict:
    """Start the pet you are looking after over: its level, evolution, hunger, mood and outfit.
    The wallet, wardrobe, dex and the pets resting in the village belong to the player and stay."""
    _at_home(state)
    from . import species
    boss = state["form"] == "boss"
    if not boss and not confirm:
        raise ActionError("정말 새로 시작하려면 --confirm 을 붙여")
    badges = list(state["badges"])
    if boss and "independence" not in badges:
        badges.append("independence")
    state["badges"] = badges
    kind = state.get("species", "mochi")
    fresh = schema.new_state(now, name=state["name"])
    for key in species.PET_FIELDS:
        if key in fresh:
            state[key] = fresh[key]
    state["species"] = kind
    schema.push_event(state, now, "born", f"{clock.josa(state['name'], '이/가')} 새로 태어났다")
    return {"reset": True, "badges": badges, "species": kind}
