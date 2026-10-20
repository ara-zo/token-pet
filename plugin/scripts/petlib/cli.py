"""Entry-point logic for hooks, /pet and the status line."""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from . import actions, clock, economy, evolve, render, schema, speech, store, transcript
from .actions import ActionError

NOTIFY_TYPES = ("born", "evolve", "runaway", "extort", "demand", "sold", "rehab", "debt", "levelup")
USAGE = """사용법: /pet [status|feed [--force]|shop|buy <id>|equip <id>|unequip <slot>|name <이름>|find|reset [--confirm]|setup [--write]]"""

STATUSLINE_BOOTSTRAP = '''#!/usr/bin/env python3
"""token-pet status line bootstrap. Finds the installed plugin via state.json."""
import json, os, sys
home = os.environ.get("PET_HOME") or os.path.join(os.path.expanduser("~"), ".claude", "pet")
try:
    root = json.load(open(os.path.join(home, "state.json"), encoding="utf-8")).get("plugin_root") or ""
except Exception:
    root = ""
sys.path.insert(0, os.path.join(root, "scripts"))
try:
    from petlib import cli
except ImportError:
    data = sys.stdin.read()
    try:
        cc = json.loads(data)
        print(f"{(cc.get('model') or {}).get('display_name', '')} · token-pet: 세션을 한 번 시작하면 연결돼요")
    except Exception:
        print("")
    sys.exit(0)
sys.exit(cli.run(["statusline"]))
'''


# ----------------------------------------------------------------- hooks

def main_collect(stdin_json: dict, now: dt.datetime, plugin_root: Optional[str] = None) -> Optional[int]:
    sid = stdin_json.get("session_id")
    path = stdin_json.get("transcript_path")
    if not sid or not path:
        return None
    path = os.path.expanduser(path)
    with store.transaction(now) as s:
        if plugin_root:
            s["plugin_root"] = plugin_root
        day = schema.today(s, now)
        sess = s["sessions"].get(sid)
        if sess is None:
            sess = s["sessions"][sid] = {"offset": 0, "seen_ids": [], "updated_at": clock.fmt(now)}
            day["sessions"] += 1
            if clock.period(now) == "day":
                day["day_sessions"] += 1
        usages, off, seen = transcript.read_new(path, sess["offset"], sess["seen_ids"])
        sess.update(offset=off, seen_ids=seen, updated_at=clock.fmt(now))

        earn_form = s["form"]
        if earn_form == "burnout" and not evolve.burnout_active(s, now):
            earn_form = "model"
        total = 0.0
        for u in usages:
            per = clock.period(u.ts)
            total += economy.turn_coins(u.output, u.input, u.cache_read, u.cache_creation, earn_form, per)
            day["tokens_in"] += u.input + u.cache_read + u.cache_creation
            day["tokens_out"] += u.output
            day["cache_read"] += u.cache_read
            if per == "night":
                day["night_out"] += u.output
        s["coin_carry"] = round(s["coin_carry"] + total, 4)
        earned = int(s["coin_carry"])
        if earned > 0:
            s["coin_carry"] = round(s["coin_carry"] - earned, 4)
            s["coins"] += earned
            s["xp"] += earned
            day["earned"] += earned
            s["last_turn_earned"] = earned
            s["last_turn_at"] = clock.fmt(now)
        elif usages:
            s["last_turn_earned"] = 0
            s["last_turn_at"] = clock.fmt(now)
        new_level = economy.level_for_xp(s["xp"])
        if new_level > s["level"]:
            s["level"] = new_level
            schema.push_event(s, now, "levelup", f"Lv.{new_level} 달성!")
            evolve.check(s, now)
        s["speech"] = speech.choose(s, now)
        return earned


def main_session_start(stdin_json: dict, now: dt.datetime, plugin_root: Optional[str] = None) -> Optional[dict]:
    first = not store.state_path().exists()
    with store.transaction(now) as s:
        if plugin_root:
            s["plugin_root"] = plugin_root
        if first:
            schema.push_event(s, now, "born", f"{clock.josa(s['name'], '이/가')} 태어났어요! 토큰을 쓰면 코인이 모이고, /pet 으로 돌봐 주세요")
        s["speech"] = speech.choose(s, now)
        pending = [e["text"] for e in s["events"] if not e.get("delivered") and e["type"] in NOTIFY_TYPES]
        for e in s["events"]:
            e["delivered"] = True
    if not pending:
        return None
    return {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext": "[token-pet] " + " / ".join(pending)}}


def main_statusline(stdin_json: dict, now: dt.datetime) -> str:
    state = store.load(now) if store.state_path().exists() else None
    return render.statusline(state, stdin_json, now)


# ----------------------------------------------------------------- /pet

def _config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def _setup(write: bool) -> Tuple[int, str]:
    settings_path = _config_dir() / "settings.json"
    bootstrap = store.home() / "statusline.py"
    snippet = {"statusLine": {"type": "command", "command": f"python3 {bootstrap}", "padding": 0}}
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    except ValueError:
        return 1, f"SETUP_ERROR {settings_path} 가 올바른 JSON이 아니에요. 직접 확인해 주세요"
    existing = settings.get("statusLine")
    if existing and existing.get("command") != snippet["statusLine"]["command"]:
        return 0, ("SETUP_EXISTS 이미 다른 상태표시줄이 설정돼 있어요. 바꾸려면 settings.json의 statusLine을 아래로 교체하세요:\n"
                   + json.dumps(snippet, ensure_ascii=False, indent=2))
    if not write:
        return 0, ("SETUP_PROMPT 상태표시줄에 펫을 띄우려면 " + str(settings_path) + " 에 아래를 추가해야 해요:\n"
                   + json.dumps(snippet, ensure_ascii=False, indent=2)
                   + "\n동의하면 `/pet setup --write` 로 자동 적용됩니다.")
    bootstrap.write_text(STATUSLINE_BOOTSTRAP, encoding="utf-8")
    settings.update(snippet)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0, f"SETUP_DONE 상태표시줄 설정 완료. 새 세션부터 보여요. ({settings_path})"


def _shop_payload(s: dict) -> dict:
    """Machine-readable shop for the desktop widget: every purchasable item with its status."""
    form = s["form"]
    blocked = economy.shop_blocked(form)
    catalog = []
    if not blocked:
        for key, item in economy.CATALOG.items():
            if item.price == 0:
                continue
            catalog.append({
                "id": key, "name": item.name, "slot": item.slot,
                "price": economy.price(key, form),
                "owned": key in s["items_owned"],
                "equipped": s["equipped"].get(item.slot) == key,
                "unlocked": economy.is_unlocked(key, s),
                "min_level": item.min_level,
            })
    return {"blocked": blocked, "feed_cost": economy.FEED_COST, "catalog": catalog}


def _summary(s: dict) -> dict:
    return {k: s[k] for k in ("name", "level", "xp", "coins", "hunger", "mood", "form", "speech",
                              "items_owned", "equipped", "last_turn_earned", "last_turn_at", "badges")}


def main_pet(argv: List[str], now: dt.datetime) -> Tuple[int, str]:
    args = [a for a in argv if a]
    flags = {a for a in args if a.startswith("--")}
    pos = [a for a in args if not a.startswith("--")]
    cmd = pos[0] if pos else "status"
    as_json = "--json" in flags

    def out(code: int, text: str, result=None, state=None) -> Tuple[int, str]:
        if as_json:
            payload = {"ok": code == 0, "text": text, "result": result}
            if state is not None:
                payload["state"] = _summary(state)
            return code, json.dumps(payload, ensure_ascii=False)
        return code, text

    if cmd == "setup":
        code, text = _setup("--write" in flags)
        return out(code, text)
    if cmd == "help":
        return out(0, USAGE)

    try:
        with store.transaction(now) as s:
            if cmd == "status":
                s["speech"] = speech.choose(s, now)
                return out(0, render.status_text(s, now), state=s)
            if cmd == "shop":
                return out(0, render.shop_text(s), _shop_payload(s), s)
            if cmd == "feed":
                r = actions.feed(s, now, force="--force" in flags)
                s["speech"] = speech.choose(s, now)
                msg = f"냠냠! 배고픔 {int(r['hunger'])}  🪙 {r['coins']:,} (-{r['cost']})"
                if r["debt"]:
                    msg += f"  외상 {r['debt']}"
                return out(0, msg, r, s)
            if cmd == "buy":
                if len(pos) < 2:
                    raise ActionError("무엇을 살지 알려줘: /pet buy <id>")
                r = actions.buy(s, now, pos[1])
                s["speech"] = speech.choose(s, now)
                msg = f"{economy.CATALOG[r['item']].name} 구매! 🪙 {r['coins']:,} (-{r['cost']}"
                msg += f", 환급 +{r['refund']})" if r["refund"] else ")"
                return out(0, msg + "\n착용하려면 /pet equip " + r["item"], r, s)
            if cmd == "equip":
                if len(pos) < 2:
                    raise ActionError("무엇을 착용할지 알려줘: /pet equip <id>")
                r = actions.equip(s, pos[1])
                return out(0, f"{economy.CATALOG[r['item']].name} 착용 ({r['slot']})", r, s)
            if cmd == "unequip":
                if len(pos) < 2:
                    raise ActionError("어느 슬롯을 벗길지 알려줘: /pet unequip <head|face|body|room>")
                r = actions.unequip(s, pos[1])
                return out(0, f"{r['slot']} 슬롯 비움", r, s)
            if cmd == "name":
                if len(pos) < 2:
                    raise ActionError("새 이름을 알려줘: /pet name <이름>")
                r = actions.rename(s, " ".join(pos[1:]))
                return out(0, f"이제부터 {r['name']}!", r, s)
            if cmd == "find":
                r = actions.find(s, now)
                s["speech"] = speech.choose(s, now)
                msg = f"{clock.josa(s['name'], '을/를')} 찾았다! 집으로 돌아왔어" if r["found"] else f"오늘도 찾아봤지만 아직… ({r['days']}/3일)"
                return out(0, msg, r, s)
            if cmd == "reset":
                r = actions.reset(s, now, confirm="--confirm" in flags)
                return out(0, f"{clock.josa(s['name'], '이/가')} 새로 태어났어요", r, s)
            raise ActionError(f"모르는 명령: {cmd}\n{USAGE}")
    except ActionError as e:
        return out(2, str(e))


# ----------------------------------------------------------------- dispatcher

def _read_stdin_json() -> dict:
    try:
        data = sys.stdin.read()
        return json.loads(data) if data.strip() else {}
    except ValueError:
        return {}


def run(argv: List[str]) -> int:
    now = clock.now()
    cmd = argv[0] if argv else "status"
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if cmd == "collect":
        try:
            main_collect(_read_stdin_json(), now, plugin_root)
        except Exception as e:  # never break the session
            store.log(f"collect failed: {e!r}")
        return 0
    if cmd == "session-start":
        try:
            result = main_session_start(_read_stdin_json(), now, plugin_root)
            if result:
                print(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            store.log(f"session-start failed: {e!r}")
        return 0
    if cmd == "statusline":
        try:
            print(main_statusline(_read_stdin_json(), now))
        except Exception as e:
            store.log(f"statusline failed: {e!r}")
            print("")
        return 0
    code, text = main_pet(argv, now)
    print(text)
    return code
