"""The pet's weekly diary: when you worked (a weekday x hour grid of output) and where (repos).

Collect files each turn's output by clock hour and by repo, with the session's title and the
commits, test runs and PRs Claude made (transcript.Act). The diary reads a Monday-to-Sunday week
back from the daily log, so it shows this week while it is being written and the week before.
Sentences are templates in the pet's voice: no AI call, no tokens.
(canvas '펫 일기 · 제안 v2', '펫 일기 · 작업한 곳')"""
from __future__ import annotations

import datetime as dt
import os
import unicodedata
from typing import Dict, List

from . import economy

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
ORDINALS = ["첫째", "둘째", "셋째", "넷째", "다섯째"]
TITLES_PER_REPO_DAY = 8
SESSIONS_PER_REPO_DAY = 50
TOP_REPOS = 4                     # the rest are summed into "기타"
FOCUS_SHARE = 50                  # one repo at least this % of the week's output: 「한 우물」 stamp
SPAN_HOURS = 4                    # 「주로 오후 2~6시」: the busiest run of this many hours
OTHER = "기타"
COUNT_KEYS = ("commits", "tests", "prs")
ACT_KEY = {"commit": "commits", "test": "tests", "pr": "prs"}


# ----------------------------------------------------------------- collecting

def repo_name(cwd: str) -> str:
    """The git work tree's folder name (a worktree's own folder), else the folder's name."""
    if not cwd:
        return ""
    path = os.path.abspath(os.path.expanduser(cwd))
    cur = path
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return os.path.basename(cur) or cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    if path == os.path.expanduser("~"):
        return "~"
    return os.path.basename(path.rstrip("/")) or path


def _repo_of(sess: dict, cwd: str) -> str:
    cache = sess.setdefault("repo_names", {})
    if cwd not in cache:
        if len(cache) > 20:
            cache.clear()
        cache[cwd] = repo_name(cwd)
    return cache[cwd]


def _slot(day: dict, repo: str) -> dict:
    r = day.setdefault("repos", {}).get(repo)
    if r is None:
        r = day["repos"][repo] = {"out": 0, "sessions": [], "titles": {}, "commits": 0, "tests": 0, "prs": 0}
    return r


def record(day: dict, sess: dict, sid: str, usages: list, meta: dict, cwd: str = "") -> None:
    """File one collect's output, commands and title into today's log entry."""
    hours = day.setdefault("hours_out", [0] * 24)
    key = sid[:8]
    for u in usages:
        hours[u.ts.hour] += u.output
        repo = _repo_of(sess, u.cwd or cwd)
        if repo:
            r = _slot(day, repo)
            r["out"] += u.output
            if key not in r["sessions"] and len(r["sessions"]) < SESSIONS_PER_REPO_DAY:
                r["sessions"].append(key)
    for act in meta.get("acts") or []:
        repo = _repo_of(sess, act.cwd or cwd)
        if repo and act.kind in ACT_KEY:
            r = _slot(day, repo)
            r[ACT_KEY[act.kind]] += 1
            if key not in r["sessions"] and len(r["sessions"]) < SESSIONS_PER_REPO_DAY:
                r["sessions"].append(key)
    if meta.get("title"):
        sess["title"] = meta["title"][:80]
    title = sess.get("title")
    if title:
        for r in day.get("repos", {}).values():
            if key in r["sessions"] and (key in r["titles"] or len(r["titles"]) < TITLES_PER_REPO_DAY):
                r["titles"][key] = title


# ----------------------------------------------------------------- the week

def week_start(now: dt.datetime, which: str = "this") -> dt.date:
    today = now.date()
    monday = today - dt.timedelta(days=today.weekday())
    return monday - dt.timedelta(days=7) if which == "last" else monday


def week_label(monday: dt.date) -> str:
    return f"{monday.month}월 {ORDINALS[min(4, (monday.day - 1) // 7)]} 주"


def hour_ko(h: int) -> tuple:
    """(part of day, 12-hour number): 15 → ("오후", 3)."""
    h %= 24
    if h == 0:
        return "밤", 12
    if h < 6:
        return "새벽", h
    if h < 12:
        return "오전", h
    if h == 12:
        return "낮", 12
    if h <= 18:
        return "오후", h - 12
    return ("저녁" if h <= 20 else "밤"), h - 12


def span_ko(start: int, hours: int = SPAN_HOURS) -> str:
    p1, n1 = hour_ko(start)
    p2, n2 = hour_ko(start + hours)
    return f"{p1} {n1}~{n2}시" if p1 == p2 or p2 == "오후" and p1 == "낮" else f"{p1} {n1}시~{p2} {n2}시"


def man(n: int) -> str:
    """Korean count units: 1_520_000 → "152만", 15_200 → "1.5만", 950 → "950"."""
    if n >= 100_000_000:
        return f"{n / 100_000_000:.1f}".rstrip("0").rstrip(".") + "억"
    if n >= 100_000:
        return f"{round(n / 10_000)}만"
    if n >= 10_000:
        return f"{n / 10_000:.1f}".rstrip("0").rstrip(".") + "만"
    return f"{n:,}"


def _week_days(state: dict, monday: dt.date, today: dt.date) -> List[dict]:
    by_date = {d.get("date"): d for d in state.get("daily_log", [])}
    days = []
    for i in range(7):
        date = monday + dt.timedelta(days=i)
        src = by_date.get(date.isoformat(), {})
        hours = [int(x or 0) for x in (src.get("hours_out") or [])][:24]
        hours += [0] * (24 - len(hours))
        days.append({
            "date": date.isoformat(), "weekday": WEEKDAYS[i],
            "out": int(src.get("tokens_out", 0) or 0), "in": int(src.get("tokens_in", 0) or 0),
            "cache": int(src.get("cache_read", 0) or 0), "night_out": int(src.get("night_out", 0) or 0),
            "earned": int(src.get("earned", 0) or 0), "feeds": int(src.get("feeds", 0) or 0),
            "pats": int(src.get("pats", 0) or 0), "treats": int(src.get("treats", 0) or 0),
            "hours": hours, "today": date == today, "future": date > today,
            "repos": src.get("repos") or {},
        })
    return days


def _repos(days: List[dict]) -> List[dict]:
    merged: Dict[str, dict] = {}
    for d in days:
        for name, r in d["repos"].items():
            m = merged.setdefault(name, {"name": name, "out": 0, "sessions": set(), "titles": {},
                                         "commits": 0, "tests": 0, "prs": 0})
            m["out"] += int(r.get("out", 0) or 0)
            m["sessions"].update(r.get("sessions") or [])
            m["titles"].update(r.get("titles") or {})
            for k in COUNT_KEYS:
                m[k] += int(r.get(k, 0) or 0)
    ranked = sorted(merged.values(), key=lambda m: (-m["out"], -sum(m[k] for k in COUNT_KEYS), m["name"]))
    ranked = [m for m in ranked if m["out"] > 0 or any(m[k] for k in COUNT_KEYS)]
    if len(ranked) > TOP_REPOS + 1:
        rest = ranked[TOP_REPOS:]
        other = {"name": OTHER, "out": sum(m["out"] for m in rest), "sessions": set().union(*(m["sessions"] for m in rest)),
                 "titles": {}, "other": len(rest), **{k: sum(m[k] for m in rest) for k in COUNT_KEYS}}
        ranked = ranked[:TOP_REPOS] + [other]
    total = sum(m["out"] for m in ranked) or 1
    out = []
    for m in ranked:
        titles = list(dict.fromkeys(m["titles"].values()))
        out.append({"name": m["name"], "out": m["out"], "share": round(m["out"] * 100 / total),
                    "sessions": len(m["sessions"]), "titles": titles, "other": m.get("other", 0),
                    **{k: m[k] for k in COUNT_KEYS}})
    return out


def payload(state: dict, now: dt.datetime, which: str = "this") -> dict:
    today = now.date()
    monday = week_start(now, which)
    days = _week_days(state, monday, today)
    total = {k: sum(d[k] for d in days) for k in ("out", "in", "cache", "night_out", "earned", "feeds", "pats", "treats")}

    peak = {"weekday": None, "hour": None, "out": 0, "date": None}
    for d in days:
        for h, v in enumerate(d["hours"]):
            if v > peak["out"]:
                peak = {"weekday": d["weekday"], "hour": h, "out": v, "date": d["date"]}
    busiest = max(days, key=lambda d: d["out"])
    by_hour = [sum(d["hours"][h] for d in days) for h in range(24)]
    span = None
    if any(by_hour):
        best = max(range(24), key=lambda h: (sum(by_hour[(h + i) % 24] for i in range(SPAN_HOURS)), -h))
        span = {"start": best, "hours": SPAN_HOURS, "text": span_ko(best)}

    lo, hi = economy.GOOD_DAY_OUT
    closed = [d for d in days if not d["future"] and not d["today"]]
    tired = sum(1 for d in days for v in d["hours"] if v > economy.RUSH_OUT_PER_HOUR)
    good = sum(1 for d in closed if lo <= d["out"] <= hi)
    night_days = sum(1 for d in days if d["night_out"] > 0)

    prev_days = _week_days(state, monday - dt.timedelta(days=7), today)
    prev_out = sum(d["out"] for d in prev_days)
    change = round((total["out"] - prev_out) * 100 / prev_out) if prev_out and total["out"] else None

    repos = _repos(days)
    counts = {k: sum(r[k] for r in repos) for k in COUNT_KEYS}
    stamps = []
    if tired:
        stamps.append({"id": "tired", "label": f"지친 시간 {tired}"})
    if good:
        stamps.append({"id": "good", "label": f"좋은 날 {good}"})
    if night_days:
        stamps.append({"id": "night", "label": f"밤 작업 {night_days}"})
    work_stamps = []
    if len(repos) > 1 and repos[0]["share"] >= FOCUS_SHARE and repos[0]["name"] != OTHER:
        work_stamps.append({"id": "focus", "label": f"한 우물 {repos[0]['share']}%"})
    elif len(repos) > 1:
        work_stamps.append({"id": "repos", "label": f"레포 {sum(r['other'] or 1 for r in repos)}곳"})
    if counts["tests"]:
        work_stamps.append({"id": "tests", "label": f"테스트 {counts['tests']}번"})
    if counts["prs"] or counts["commits"]:
        parts = ([f"PR {counts['prs']}"] if counts["prs"] else []) + ([f"커밋 {counts['commits']}"] if counts["commits"] else [])
        work_stamps.append({"id": "ship", "label": " · ".join(parts)})

    p = {
        "which": which, "name": state.get("name", ""), "species": state.get("species", "mochi"),
        "start": monday.isoformat(), "end": (monday + dt.timedelta(days=6)).isoformat(), "label": week_label(monday),
        "days": [{k: v for k, v in d.items() if k != "repos"} for d in days],
        "total": total, "peak": peak if peak["out"] else None,
        "busiest": {"weekday": busiest["weekday"], "date": busiest["date"], "out": busiest["out"]} if busiest["out"] else None,
        "span": span, "night_pct": round(total["night_out"] * 100 / total["out"]) if total["out"] else 0,
        "tired": tired, "good": good, "night_days": night_days,
        "prev_out": prev_out, "change": change,
        "repos": repos, "counts": counts, "stamps": stamps, "work_stamps": work_stamps,
        "hours_known": any(any(d["hours"]) for d in days),
    }
    p["lines"] = lines(p)
    return p


# ----------------------------------------------------------------- the pet's voice

# peak: {wd} 화, {h} 15, {part} 오후, {h12} 3, {k} "15만"; repo: {repo}, {share}, {n} repos; counts: labels per species
VOICE = {
    "mochi": {"peak": "{wd}요일 {part} {h12}시에 공장이 제일 빨랐다. {k} 조각! 땀이 났다.",
              "repo": "{repo} 공장에 제일 오래 있었다!", "counts": ("커밋 {commits}번", "테스트 {tests}번", "PR {prs}개"),
              "counts_end": "!", "quiet": "조용한 한 주였다. 낮잠을 많이 잤다."},
    "robot": {"peak": "주간 보고서. 최대 가동 {wd} {h:02d}:00 ({k}). 과열 {tired}회.",
              "repo": "가동 위치 1위 {repo} ({share}%). {n}개 현장 순회.", "counts": ("출하 {commits}건", "검사 {tests}회", "납품 {prs}건"),
              "counts_end": ".", "quiet": "주간 보고서. 가동 없음. 대기 모드 유지."},
    "squirrel": {"peak": "{wd}요일 {h12}시!! 결정 엄청!! 꼬리 흔들다 땀!!",
                 "repo": "{repo}!! 거기만 계속 팠어!!", "counts": ("커밋 {commits}번", "테스트 {tests}번", "PR {prs}개"),
                 "counts_end": "!!", "quiet": "결정이 하나도 안 자랐어!! 다음 주엔 꼭!!"},
    "mole": {"peak": "…{wd}요일. {h12}시. 많이 캤다. 더웠다.",
             "repo": "…{repo}. 굴이 깊어졌다.", "counts": ("커밋 {commits}개", "테스트 {tests}번", "PR {prs}개"),
             "counts_end": ".", "quiet": "…조용한 주. 땅이 식었다."},
    "rabbit": {"peak": "{wd} {h}시 신호 최대. 귀가 뜨거웠어.",
               "repo": "주파수 {n}. 제일 센 건 {repo}.", "counts": ("커밋 신호 {commits}번", "테스트 {tests}번", "PR 신호 {prs}번"),
               "counts_end": ".", "quiet": "신호가 약한 주였어. 주인도 쉬었나 봐."},
    "penguin": {"peak": "{wd}요일 {part} {h12}시… 별가루가 제일 많이 쏟아졌어…",
                "repo": "{repo}에서 제일 오래 줄 섰어…", "counts": ("커밋 {commits}개", "테스트 {tests}번", "PR {prs}개"),
                "counts_end": "…", "quiet": "별이 안 뜬 주였어… 푹 잤어…"},
    "hamster": {"peak": "근데근데 {wd}요일 {h12}시에 볼이 터질 뻔했어! {k}이나!",
                "repo": "{repo}에 제일 오래 있었어!", "counts": ("커밋 {commits}번", "테스트 {tests}번", "PR {prs}개"),
                "counts_end": "이나 했대!", "quiet": "볼이 홀쭉한 주였어… 간식 주면 안 돼?"},
}


def lines(p: dict) -> dict:
    """{"time": [...], "work": [...]}: sentences for the two diary pages."""
    v = VOICE.get(p["species"]) or VOICE["mochi"]
    time_lines, work_lines = [], []
    if not p["total"]["out"]:
        return {"time": [v["quiet"]], "work": []}
    pk = p["peak"]
    if pk:
        part, h12 = hour_ko(pk["hour"])
        time_lines.append(v["peak"].format(wd=pk["weekday"], h=pk["hour"], part=part, h12=h12, k=man(pk["out"]),
                                           tired=p["tired"]))
    if p["span"]:
        night = f" · 밤 작업 {p['night_pct']}%" if p["night_pct"] else ""
        time_lines.append(f"주로 {p['span']['text']}에 일했다{night}.")
    if p["change"] is not None:
        if abs(p["change"]) < 5:
            time_lines.append("지난주랑 비슷하게 일했다.")
        else:
            time_lines.append(f"지난주보다 {abs(p['change'])}% {'더' if p['change'] > 0 else '덜'} 일했다.")
    named = [r for r in p["repos"] if r["name"] != OTHER]
    if named:
        top = named[0]
        work_lines.append(v["repo"].format(repo=top["name"], share=top["share"], n=len(p["repos"])))
    c = p["counts"]
    parts = [t.format(**c) for t, k in zip(v["counts"], COUNT_KEYS) if c[k]]
    if parts:
        work_lines.append(", ".join(parts) + v["counts_end"])
    return {"time": time_lines, "work": work_lines}


# ----------------------------------------------------------------- terminal

HEAT = "·▁▂▃▄▅▆▇█"
HOURS_HEAD = "    0      6      12     18   23"     # over heat_row's columns, after the 「월  」 prefix
EIGHTHS = " ▏▎▍▌▋▊▉"


def _width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def _pad(s: str, width: int) -> str:
    return s + " " * max(1, width - _width(s))


def _bar(share: float, width: int = 12) -> str:
    eighths = int(round(share / 100 * width * 8))
    full, rest = divmod(eighths, 8)
    return ("█" * full + (EIGHTHS[rest] if rest else "")).ljust(width)


def heat_row(hours: List[int], top: int) -> str:
    cells = []
    for v in hours:
        cells.append(HEAT[0] if v <= 0 else HEAT[max(1, min(8, round(v / top * 8)))])
    return " ".join("".join(cells[i:i + 6]) for i in range(0, 24, 6))


def text(state: dict, now: dt.datetime, which: str = "this") -> str:
    p = payload(state, now, which)
    start, end = p["start"][5:].replace("-", "/"), p["end"][5:].replace("-", "/")
    head = f"📔 {p['name']}의 일기 · {p['label']} ({start}~{end})" + (" · 쓰는 중" if which == "this" else "")
    out = [head]
    if not p["total"]["out"] and not p["repos"]:
        out.append("  " + p["lines"]["time"][0])
        return "\n".join(out)

    top = max([v for d in p["days"] for v in d["hours"]] + [1])
    out.append(HOURS_HEAD)
    for d in p["days"]:
        if d["future"]:
            out.append(f"{d['weekday']}")
            continue
        out.append(f"{d['weekday']}  {heat_row(d['hours'], top)}" + ("  ← 오늘" if d["today"] else ""))
    if not p["hours_known"]:
        out.append("  (시간표는 일기 기능을 켠 뒤부터 쌓여요)")
    pk = p["peak"]
    if pk:
        out.append(f"가장 바빴던 시간: {pk['weekday']}요일 {pk['hour']}시 (출력 {man(pk['out'])})")
    for line in p["lines"]["time"]:
        out.append(line)
    t = p["total"]
    out.append(f"출력 {man(t['out'])} · 코인 +{t['earned']:,} · 밥 {t['feeds']} · 쓰다듬기 {t['pats']} · 선물 {t['treats']}")
    if p["stamps"]:
        out.append("도장: " + " · ".join(s["label"] for s in p["stamps"]))

    if p["repos"]:
        out.append("")
        out.append("📂 " + ("이번 주" if which == "this" else "그 주") + " 작업한 곳")
        name_w = max(_width(r["name"]) for r in p["repos"]) + 2
        for r in p["repos"]:
            out.append(f"{_pad(r['name'], name_w)}{_bar(r['share'])}  {r['share']:>3}%  {man(r['out']):>5}  세션 {r['sessions']}"
                       + (f" · {r['other']}곳" if r["other"] else ""))
            counts = [f"{label} {r[k]}" for label, k in (("커밋", "commits"), ("테스트", "tests"), ("PR", "prs")) if r[k]]
            if counts:
                out.append("  " + " · ".join(counts))
            shown = r["titles"][:3]
            for title in shown:
                out.append(f"  · {title}")
            if len(r["titles"]) > len(shown):
                out[-1] += f"  …외 {len(r['titles']) - len(shown)}"
        c = p["counts"]
        if any(c.values()):
            out.append(f"합계 커밋 {c['commits']} · 테스트 {c['tests']} · PR {c['prs']}")
        for line in p["lines"]["work"]:
            out.append(line)
    return "\n".join(out)


def widget_payload(state: dict, now: dt.datetime, which: str = "this") -> dict:
    """What the widget shows: session titles stay in the terminal (screen sharing)."""
    p = payload(state, now, which)
    p["repos"] = [{k: v for k, v in r.items() if k != "titles"} for r in p["repos"]]
    return p
