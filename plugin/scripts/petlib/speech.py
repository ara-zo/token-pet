"""Pick the pet's speech bubble line from state."""
from __future__ import annotations

import datetime as dt

from . import clock, economy, schema

RECENT_EVENT_MINUTES = 10

FORM_LINES = {
    "base": "오늘도 같이 일하자!",
    "model": "오늘 목표 다 끝내면 간식 줘",
    "miser": "코인은 쓰는 게 아니라 모으는 거야",
    "owl": "밤이 제일 좋아…",
    "spender": "오늘은 뭐 사줄 거야?",
    "thug": "야. 코인 좀 내놔 봐",
    "runaway": "…",
    "scholar": "캐시를 잘 쓰면 코인이 더 모여",
    "burnout": "오늘은… 아무것도 하기 싫어",
    "tycoon": "돈이 돈을 벌어. 후후",
    "loanshark": "외상값은 꼭 받아낸다",
    "hunter": "새벽 사냥 가자",
    "vampire": "햇빛… 싫어…",
    "influencer": "오늘 룩 어때? 찍어줘",
    "broke": "통장이 텅… 아이템 팔아야 하나",
    "boss": "상납 안 하면 알지?",
}
EVENT_TYPES_TO_SPEAK = ("evolve", "runaway", "extort", "demand", "sold", "rehab", "born", "debt")


def _fmt_k(n: int) -> str:
    return f"{n/1000:.1f}k" if n >= 1000 else str(n)


def choose(state: dict, now: dt.datetime) -> str:
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
    if form == "runaway":
        return "(집이 비어 있다…)"
    if state["hunger"] < 20:
        out = schema.today(state, now)["tokens_out"]
        return f"오늘 {_fmt_k(out)} 토큰 썼지? 나 배고파…" if out else "배고파… 먹이 줘"
    if state["mood"] < 30:
        return "심심해… 나한테 관심 좀 줘"
    flags = state["flags"]
    if form in ("spender", "influencer") and flags.get("demand_item"):
        return f"신상 {economy.CATALOG[flags['demand_item']].name} 사줘!"
    if form in economy.NOCTURNAL and clock.period(now) == "day":
        return "zzz…"
    if form == "boss":
        return FORM_LINES["boss"]
    return FORM_LINES.get(form, FORM_LINES["base"])
