"""Text output: /pet status, shop, and the status line."""
from __future__ import annotations

import datetime as dt
import re
from typing import Optional

from . import clock, economy, schema

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
C = {
    "reset": "\x1b[0m", "dim": "\x1b[2m", "text": "\x1b[97m", "sub": "\x1b[38;5;146m",
    "coin": "\x1b[38;5;221m", "hunger": "\x1b[38;5;215m", "mood": "\x1b[38;5;121m",
    "warn": "\x1b[38;5;211m", "path": "\x1b[38;5;111m",
}


def strip_ansi(s: str) -> str:
    return ANSI_RE.sub("", s)


def bars(value: float, width: int = 5) -> str:
    filled = int(round(float(value) / 100 * width))
    filled = max(0, min(width, filled))
    return "▓" * filled + "░" * (width - filled)


def _ago(ts: Optional[str], now: dt.datetime) -> str:
    if not ts:
        return "-"
    h = clock.hours_between(clock.parse(ts), now)
    if h < 1:
        return f"{int(h * 60)}분 전"
    if h < 48:
        return f"{int(h)}시간 전"
    return f"{int(h // 24)}일 전"


def status_text(state: dict, now: dt.datetime) -> str:
    form = economy.FORMS[state["form"]]
    day = schema.today(state, now)
    next_xp = economy.xp_for_level(state["level"] + 1)
    lines = [
        f"{form.glyph} {state['name']}  Lv.{state['level']}  {form.ko}",
        f"🪙 {state['coins']:,}   (xp {state['xp']:,} / 다음 레벨 {next_xp:,})",
        f"배고픔 {bars(state['hunger'])} {int(state['hunger'])}    기분 {bars(state['mood'])} {int(state['mood'])}",
        f"💬 {state['speech'] or '...'}",
        f"오늘 +{day['earned']} 코인 · 출력 {day['tokens_out']:,} 토큰 · 마지막 식사 {_ago(state['last_fed_at'], now)}",
    ]
    fc = state.get("forecast")
    if fc:
        lines.append(f"🔮 Lv.{fc['at_level']} 진화 예감: {fc['glyph']} {fc['ko']} · {fc['reason']}")
    eq = [economy.CATALOG[v].name for v in state["equipped"].values() if v in economy.CATALOG]
    if eq:
        lines.append("착용: " + ", ".join(eq))
    flags = state["flags"]
    if flags.get("debt"):
        lines.append(f"외상 {flags['debt']}코인")
    if flags.get("demand_item"):
        lines.append(f"요구: {economy.CATALOG[flags['demand_item']].name}")
    if state["badges"]:
        lines.append("배지: " + ", ".join(state["badges"]))
    return "\n".join(lines)


def shop_text(state: dict) -> str:
    form = state["form"]
    if economy.shop_blocked(form):
        return f"🚫 상점 봉쇄 중 ({economy.FORMS[form].ko})"
    lines = [f"🛒 상점   보유 🪙 {state['coins']:,}" + ("   (구두쇠 할증 +30%)" if form == "miser" else "")]
    for key, item in economy.CATALOG.items():
        if not economy.for_sale(key) and not item.grant:
            continue
        if key in state["items_owned"]:
            mark = "보유"
        elif item.grant:
            mark = item.grant
        elif not economy.is_unlocked(key, state):
            mark = f"Lv.{item.min_level} 해금"
        else:
            mark = f"{economy.price(key, form)}코인"
        lines.append(f"  {key:<11} {item.name:<6} [{item.slot}]  {mark}")
    lines.append("구매: /pet buy <id>   착용: /pet equip <id>")
    return "\n".join(lines)


def _virtual_tick(state: dict, now: dt.datetime) -> dict:
    """Decayed hunger/mood for display without writing (statusline is read-only)."""
    from . import tick
    import copy
    s = copy.deepcopy(state)
    try:
        for m in clock.midnights_between(clock.parse(s["last_tick_at"]), now):
            tick.decay(s, clock.parse(s["last_tick_at"]), m)
            s["last_tick_at"] = clock.fmt(m)
        tick.decay(s, clock.parse(s["last_tick_at"]), now)
    except (ValueError, KeyError):
        pass
    return s


def statusline(state: Optional[dict], cc: dict, now: dt.datetime) -> str:
    cwd = (cc.get("workspace") or {}).get("current_dir") or cc.get("cwd") or ""
    home = str(__import__("pathlib").Path.home())
    if cwd.startswith(home):
        cwd = "~" + cwd[len(home):]
    model = (cc.get("model") or {}).get("display_name") or ""
    ctx = (cc.get("context_window") or {}).get("used_percentage")
    cost = (cc.get("cost") or {}).get("total_cost_usd")
    sep = f" {C['dim']}│{C['reset']} "
    parts = []
    if cwd:
        parts.append(f"{C['path']}{cwd}{C['reset']}")
    if model:
        parts.append(f"{C['sub']}{model}{C['reset']}")
    if state is not None:
        s = _virtual_tick(state, now)
        form = economy.FORMS.get(s["form"], economy.FORMS["base"])
        if s["flags"].get("boss_hijack"):
            parts.append(f"{C['warn']}👔 보스: 상납 안 하면 알지?{C['reset']}")
        else:
            earn = f" {C['mood']}+{s['last_turn_earned']}{C['reset']}" if s.get("last_turn_earned") else ""
            parts.append(
                f"{form.glyph} {C['text']}{s['name']} Lv.{s['level']}{C['reset']} "
                f"{C['coin']}🪙{s['coins']:,}{C['reset']}{earn} "
                f"{C['sub']}배고픔{C['reset']}{C['hunger']}{bars(s['hunger'])}{C['reset']} "
                f"{C['sub']}기분{C['reset']}{C['mood']}{bars(s['mood'])}{C['reset']}"
            )
    tail = []
    if ctx is not None:
        tail.append(f"ctx {int(ctx)}%")
    if cost is not None:
        tail.append(f"${cost:.2f}")
    if tail:
        parts.append(f"{C['sub']}{' · '.join(tail)}{C['reset']}")
    return sep.join(parts)


STAT_KEYS = ("earned", "spent", "tokens_out", "feeds", "pats")


def stats_payload(state: dict, now: dt.datetime, days: int = 7) -> dict:
    """The last `days` days, oldest first, with missing days filled with zeros."""
    by_date = {d["date"]: d for d in state["daily_log"]}
    out = []
    for i in range(days - 1, -1, -1):
        date = clock.day_key(now - dt.timedelta(days=i))
        src = by_date.get(date, {})
        out.append({"date": date, **{k: int(src.get(k, 0) or 0) for k in STAT_KEYS}})
    total = {k: sum(d[k] for d in out) for k in STAT_KEYS}
    return {"days": out, "total": total}


def stats_text(state: dict, now: dt.datetime) -> str:
    p = stats_payload(state, now)
    top = max([d["earned"] for d in p["days"]] + [1])
    lines = ["📊 최근 7일   코인 · 출력 토큰 · 먹이"]
    for d in p["days"]:
        bar = bars(d["earned"] / top * 100, 8)
        lines.append(f"  {d['date'][5:].replace('-', '/')}  {bar}  +{d['earned']:,} · {d['tokens_out']:,} · {d['feeds']}")
    t = p["total"]
    lines.append(f"합계 +{t['earned']:,}코인 (사용 {t['spent']:,}) · 출력 {t['tokens_out']:,} · 먹이 {t['feeds']} · 쓰다듬기 {t['pats']}")
    return "\n".join(lines)
