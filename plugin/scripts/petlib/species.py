"""토키 종족, 도감, 여러 마리 키우기.

첫 펫은 모찌. 평생 기록이 조건을 채우면 도감에 등록되고(입양 가능), 입양비를 내면 데려온다.
한 번에 한 마리를 돌보고, 나머지는 마을에서 쉰다: 상태가 멈춘 채 state["pets"] 에 보관된다.
코인·옷장·도감·평생 기록은 모두가 함께 쓰고, 레벨·진화·배고픔·기분·착용은 펫마다 따로다.
(캔버스 '토키 도감', '종족 추가안'; 여러 마리 보유는 이후 결정)"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import List, Optional, Tuple

from . import clock, schema


@dataclass(frozen=True)
class Species:
    ko: str
    part: str                  # the body part that shows coins and mood
    desc: str
    condition: str             # how to register it, as the user reads it
    metric: Optional[str]      # key in state["lifetime"]
    goal: int


SPECIES = {
    "mochi": Species("모찌", "찹쌀떡 몸", "기본 토키. 말랑하고 무난해서 어떤 진화든 잘 어울린다", "처음부터", None, 0),
    "squirrel": Species("결정 다람쥐", "꼬리 결정", "꼬리가 조각 결정으로 자란다. 모은 코인이 많을수록 결정이 커진다",
                        "잔액 2,000코인 달성", "max_coins", 2000),
    "mole": Species("두더지", "안전모 램프", "조각을 땅속에서 캔다. 코인이 들어오면 안전모 램프가 켜진다",
                    "출력 누적 100만 토큰", "tokens_out", 1_000_000),
    "robot": Species("굴뚝 로봇", "배 속 화로", "생각 공장의 부품이 살아났다. 조각이 들어오면 화로가 타고 굴뚝에서 연기",
                     "7일 연속 출석", "attend_streak_max", 7),
    "penguin": Species("별가루 펭귄", "배의 초승달", "환전소 앞에서 밤새 줄 서다 몸에 별이 박혔다. 오드아이",
                       "밤 출력 누적 30만 토큰", "night_out", 300_000),
    "hamster": Species("유리볼 햄스터", "투명 볼주머니", "볼 안에 채운 조각이 그대로 보인다. 귀가 네 개",
                       "쓰다듬기 누적 50번", "pats", 50),
    "rabbit": Species("안테나 토끼", "회로선 · 세 번째 눈", "공장 신호를 귀로 받는다. 세 번째 눈은 진화 예감을 볼 때만 열린다",
                      "진화 1번 겪기", "evolutions", 1),
}
ORDER = list(SPECIES)

ADOPT_COST = {"hamster": 500, "squirrel": 800, "robot": 800, "penguin": 1000, "mole": 1200, "rabbit": 1500}

# Fields that belong to one pet. Everything else in state is the player's (wallet, wardrobe, logs).
PET_FIELDS = ("name", "created_at", "level", "xp", "hunger", "mood", "form", "form_since",
              "equipped", "last_fed_at", "since_form", "flags", "species", "forecast")


def progress(state: dict, key: str) -> Tuple[int, int]:
    sp = SPECIES[key]
    if sp.metric is None:
        return 0, 0
    return int(state["lifetime"].get(sp.metric, 0)), sp.goal


def record_attendance(state: dict, now: dt.datetime) -> None:
    """Count consecutive days with at least one Claude Code turn."""
    life = state["lifetime"]
    today = clock.day_key(now)
    last = life.get("last_attend")
    if last == today:
        return
    yesterday = clock.day_key(now - dt.timedelta(days=1))
    life["attend_streak"] = life.get("attend_streak", 0) + 1 if last == yesterday else 1
    life["attend_streak_max"] = max(life.get("attend_streak_max", 0), life["attend_streak"])
    life["last_attend"] = today


def check(state: dict, now: dt.datetime) -> List[dict]:
    """Track the peak balance and register every species whose goal is met."""
    life = state["lifetime"]
    life["max_coins"] = max(life.get("max_coins", 0), int(state["coins"]))
    events = []
    for key in ORDER:
        if key in state["dex"]:
            continue
        cur, goal = progress(state, key)
        if SPECIES[key].metric is not None and cur >= goal:
            state["dex"].append(key)
            name = SPECIES[key].ko
            events.append(schema.push_event(
                state, now, "dex", f"도감에 {name} 등록! 새로 시작할 때 고를 수 있어요 (/pet dex)", species=key))
    return events


def owned(state: dict) -> List[str]:
    return [k for k in ORDER if k == state["species"] or k in state.get("pets", {})]


def dex_payload(state: dict) -> dict:
    rows = []
    pets = state.get("pets", {})
    for key in ORDER:
        sp = SPECIES[key]
        cur, goal = progress(state, key)
        rest = pets.get(key)
        rows.append({"id": key, "name": sp.ko, "part": sp.part, "desc": sp.desc, "condition": sp.condition,
                     "unlocked": key in state["dex"], "current": key == state["species"],
                     "owned": key in owned(state), "adopt_cost": ADOPT_COST.get(key, 0),
                     "resting": {"name": rest["name"], "level": rest["level"], "form": rest["form"]} if rest else None,
                     "cur": min(cur, goal) if goal else 0, "goal": goal})
    return {"current": state["species"], "species": rows}


def dex_text(state: dict) -> str:
    p = dex_payload(state)
    have = sum(r["unlocked"] for r in p["species"])
    lines = [f"📖 토키 도감 ({have}/{len(p['species'])})"]
    for r in p["species"]:
        mark = "✔" if r["unlocked"] else "·"
        if r["current"]:
            note = "지금 돌보는 중"
        elif r["resting"]:
            note = f"쉬는 중 · {r['resting']['name']} Lv.{r['resting']['level']}"
        elif r["unlocked"]:
            note = "입양 가능 · " + (f"{r['adopt_cost']:,}코인" if r["adopt_cost"] else "무료")
        else:
            note = f"{r['condition']}  {r['cur']:,} / {r['goal']:,}"
        lines.append(f"  {mark} {r['id']:<9} {r['name']:<7} {note}")
    lines.append("입양: /pet adopt <id> [이름]   데려오기: /pet switch <id>")
    return "\n".join(lines)


# ----------------------------------------------------------------- roster

def _shift(state: dict, key: str, delta: dt.timedelta, container: Optional[dict] = None) -> None:
    box = container if container is not None else state
    if box.get(key):
        box[key] = clock.fmt(clock.parse(box[key]) + delta)


def _put_to_rest(state: dict, now: dt.datetime) -> None:
    import copy
    snap = {k: copy.deepcopy(state[k]) for k in PET_FIELDS if k in state}
    snap["rested_at"] = clock.fmt(now)
    state.setdefault("pets", {})[state["species"]] = snap


def _bring_back(state: dict, key: str, now: dt.datetime) -> None:
    snap = state["pets"].pop(key)
    rested = clock.parse(snap.pop("rested_at", clock.fmt(now)))
    for k in PET_FIELDS:
        if k in snap:
            state[k] = snap[k]
    # time stood still while resting: move the pet's clocks forward by the rest
    delta = now - rested
    _shift(state, "last_fed_at", delta)
    _shift(state, "form_since", delta)
    for flag in ("burnout_until", "demand_since"):
        _shift(state, flag, delta, state["flags"])


def adopt(state: dict, now: dt.datetime, key: str, name: Optional[str] = None) -> dict:
    from .actions import ActionError, MAX_NAME_LEN
    if key not in SPECIES:
        raise ActionError(f"그런 종족은 없어: {key}. /pet dex 로 목록을 봐")
    if key in owned(state):
        raise ActionError(f"{SPECIES[key].ko}은(는) 이미 우리 집에 있어. /pet switch {key}")
    if key not in state["dex"]:
        raise ActionError(f"{SPECIES[key].ko}은(는) 아직 도감에 없어. 조건: {SPECIES[key].condition}")
    cost = ADOPT_COST.get(key, 0)
    if state["coins"] < cost:
        raise ActionError(f"코인이 모자라. 입양비 {cost:,}코인 필요한데 {state['coins']:,}코인뿐이야")
    pet_name = (name or SPECIES[key].ko).strip()
    if not 1 <= len(pet_name) <= MAX_NAME_LEN:
        raise ActionError(f"이름은 1~{MAX_NAME_LEN}자")
    state["coins"] -= cost
    schema.today(state, now)["spent"] += cost
    _put_to_rest(state, now)
    fresh = schema.new_state(now, name=pet_name)
    for k in PET_FIELDS:
        if k in fresh:
            state[k] = fresh[k]
    state["species"] = key
    state["equipped"] = {"bg": state.get("pets", {}).get("mochi", {}).get("equipped", {}).get("bg", "street")}
    schema.push_event(state, now, "born", f"{clock.josa(pet_name, '이/가')} 우리 집에 왔다! ({SPECIES[key].ko})")
    return {"species": key, "name": pet_name, "cost": cost, "coins": state["coins"]}


def switch(state: dict, now: dt.datetime, key: str) -> dict:
    from .actions import ActionError
    if key not in SPECIES:
        raise ActionError(f"그런 종족은 없어: {key}. /pet dex 로 목록을 봐")
    if key == state["species"]:
        raise ActionError(f"{state['name']}은(는) 이미 지금 돌보는 중이야")
    if key not in state.get("pets", {}):
        raise ActionError(f"{SPECIES[key].ko}은(는) 우리 집에 없어. /pet adopt {key} 로 먼저 입양해")
    _put_to_rest(state, now)
    _bring_back(state, key, now)
    return {"species": key, "name": state["name"], "level": state["level"]}


def resting_line(state: dict) -> Optional[str]:
    pets = state.get("pets", {})
    if not pets:
        return None
    parts = [f"{p['name']} Lv.{p['level']}" for k, p in sorted(pets.items(), key=lambda kv: ORDER.index(kv[0]))]
    return "🏘 마을에서 쉬는 중: " + ", ".join(parts)
