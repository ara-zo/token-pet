"""토키 종족과 도감. 첫 펫은 모찌, 나머지는 평생 기록이 조건을 채우면 도감에 등록되고
/pet reset 할 때 고를 수 있다. 지금 키우는 펫의 종은 바꾸지 않는다. (캔버스 '토키 도감', '종족 추가안')"""
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


def dex_payload(state: dict) -> dict:
    rows = []
    for key in ORDER:
        sp = SPECIES[key]
        cur, goal = progress(state, key)
        rows.append({"id": key, "name": sp.ko, "part": sp.part, "desc": sp.desc, "condition": sp.condition,
                     "unlocked": key in state["dex"], "current": key == state["species"],
                     "cur": min(cur, goal) if goal else 0, "goal": goal})
    return {"current": state["species"], "species": rows}


def dex_text(state: dict) -> str:
    p = dex_payload(state)
    have = sum(r["unlocked"] for r in p["species"])
    lines = [f"📖 토키 도감 ({have}/{len(p['species'])})"]
    for r in p["species"]:
        mark = "✔" if r["unlocked"] else "·"
        if r["current"]:
            note = "지금 키우는 중"
        elif r["unlocked"]:
            note = r["part"]
        else:
            note = f"{r['condition']}  {r['cur']:,} / {r['goal']:,}"
        lines.append(f"  {mark} {r['id']:<9} {r['name']:<7} {note}")
    lines.append("새로 시작할 때 고르기: /pet reset --confirm <id>  (레벨·진화·코인은 처음부터, 도감은 유지)")
    return "\n".join(lines)
