"""Entry-point logic for hooks, /pet and the status line."""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from . import actions, clock, economy, evolve, render, schema, species, speech, speech_lines, store, transcript, widget
from .actions import ActionError

NOTIFY_TYPES = ("born", "evolve", "runaway", "extort", "demand", "sold", "rehab", "debt", "levelup", "dex")
USAGE = """사용법: /pet [status|feed [--force]|pat|stats|shop|buy <id>|equip <id>|unequip <slot>|name <이름>|dex|find|reset [--confirm] [종족]|setup [--write]|widget [on|off|install]]"""

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
        # subagents write their own transcripts next to the session's; same earning rules
        subs = sess.setdefault("subagents", {})
        for sub_path in transcript.subagent_files(path):
            key = os.path.basename(sub_path)
            cur = subs.get(key) or {"offset": 0, "seen_ids": []}
            more, sub_off, sub_seen = transcript.read_new(sub_path, cur["offset"], cur["seen_ids"],
                                                          include_sidechain=True)
            subs[key] = {"offset": sub_off, "seen_ids": sub_seen}
            usages.extend(more)

        earn_form = s["form"]
        if earn_form == "burnout" and not evolve.burnout_active(s, now):
            earn_form = "model"
        total = 0.0
        capped_before = day["tokens_out"] >= economy.DAILY_SOFTCAP_OUT
        for u in usages:
            per = clock.period(u.ts)
            total += economy.turn_coins(u.output, u.input, u.cache_read, u.cache_creation, earn_form, per,
                                        day["tokens_out"])
            day["tokens_in"] += u.input + u.cache_read + u.cache_creation
            day["tokens_out"] += u.output
            day["cache_read"] += u.cache_read
            if per == "night":
                day["night_out"] += u.output
            life = s["lifetime"]
            life["tokens_out"] += u.output
            if per == "night":
                life["night_out"] += u.output
        if usages:
            species.record_attendance(s, now)
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
        if not capped_before and day["tokens_out"] >= economy.DAILY_SOFTCAP_OUT:
            schema.push_event(s, now, "softcap", speech_lines.EVENTS["softcap"])
        new_level = economy.level_for_xp(s["xp"])
        if new_level > s["level"]:
            s["level"] = new_level
            schema.push_event(s, now, "levelup", speech_lines.EVENTS["levelup"].format(lv=new_level))
            evolve.check(s, now)
        species.check(s, now)
        s["speech"] = speech.choose(s, now, "EARN" if earned > 0 else None, n=earned)
        return earned


def main_session_start(stdin_json: dict, now: dt.datetime, plugin_root: Optional[str] = None) -> Optional[dict]:
    first = not store.state_path().exists()
    with store.transaction(now) as s:
        if plugin_root:
            s["plugin_root"] = plugin_root
        if first:
            schema.push_event(s, now, "born", speech_lines.EVENTS["born"].format(name=clock.josa(s["name"], "이/가")))
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


def _widget_cmd(sub: str, now: dt.datetime) -> Tuple[int, str]:
    if sub in ("on", "off"):
        with store.transaction(now) as s:
            s["settings"]["widget"] = sub == "on"
        if sub == "off":
            return 0, "세션을 시작해도, 로그인해도 위젯을 띄우지 않아요"
        return 0, "로그인할 때와 세션을 시작할 때 위젯을 띄워요" + ("" if widget.find_app() else ". 아직 설치 전이라 /pet widget install 로 설치해 주세요")
    if sub == "install":
        try:
            path = widget.install()
        except RuntimeError as e:
            return 2, str(e)
        return 0, f"위젯을 설치하고 띄웠어요 ({path}). 다음부터는 로그인할 때 저절로 떠요"
    if sub:
        return 2, "사용법: /pet widget [on|off|install]"
    app = widget.find_app()
    on = store.load(now)["settings"]["widget"] if store.state_path().exists() else True
    where = f"설치됨: {app}" if app else "설치 안 됨. /pet widget install 로 설치해요"
    return 0, f"데스크톱 위젯 · {where} · 세션 시작 시 띄우기 {'켬' if on else '끔'}"


def _session_start_widget(now: dt.datetime) -> None:
    """Bring the desktop widget up with the session; install it in the background on first use (once a day at most)."""
    if os.environ.get("TOKEN_PET_NO_WIDGET") or sys.platform != "darwin":
        return
    with store.transaction(now) as s:
        cfg = s["settings"]
        if not cfg["widget"]:
            return
        if widget.launch():
            return
        today_key = clock.day_key(now)
        if cfg.get("widget_install_tried") == today_key:
            return
        cfg["widget_install_tried"] = today_key
    import subprocess
    script = Path(__file__).resolve().parent.parent / "pet.py"
    subprocess.Popen([sys.executable, str(script), "widget", "install"], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def _shop_payload(s: dict) -> dict:
    """Machine-readable shop for the desktop widget: every purchasable item with its status."""
    form = s["form"]
    blocked = economy.shop_blocked(form)
    catalog = []
    for key, item in economy.CATALOG.items():
        owned = key in s["items_owned"]
        if blocked and not owned:          # shop closed: only what the pet already has, to wear
            continue
        # starters are listed only where they can be put back on (the default background)
        if not economy.for_sale(key) and not item.grant and not (owned and item.slot == "bg"):
            continue
        catalog.append({
            "id": key, "name": item.name, "slot": item.slot,
            "price": economy.price(key, form) if economy.for_sale(key) else 0,
            "owned": owned,
            "equipped": s["equipped"].get(item.slot) == key,
            "unlocked": economy.is_unlocked(key, s) and (economy.for_sale(key) or owned),
            "min_level": item.min_level,
            "grant": item.grant,
        })
    return {"blocked": blocked, "feed_cost": economy.FEED_COST, "catalog": catalog}


def _summary(s: dict) -> dict:
    return {k: s[k] for k in ("name", "level", "xp", "coins", "hunger", "mood", "form", "speech",
                              "items_owned", "equipped", "last_turn_earned", "last_turn_at", "badges")} \
        | {"forecast": s.get("forecast"), "species": s.get("species", "mochi"), "dex": s.get("dex", ["mochi"])}


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
    if cmd == "widget":
        return out(*_widget_cmd(pos[1] if len(pos) > 1 else "", now))

    try:
        with store.transaction(now) as s:
            if cmd == "status":
                s["speech"] = speech.choose(s, now)
                return out(0, render.status_text(s, now), state=s)
            if cmd == "shop":
                return out(0, render.shop_text(s), _shop_payload(s), s)
            if cmd == "feed":
                r = actions.feed(s, now, force="--force" in flags)
                s["speech"] = speech.choose(s, now, "FEED")
                msg = f"냠냠! 배고픔 {int(r['hunger'])}  🪙 {r['coins']:,} (-{r['cost']})"
                if r["debt"]:
                    msg += f"  외상 {r['debt']}"
                return out(0, msg, r, s)
            if cmd == "pat":
                r = actions.pat(s, now)
                s["speech"] = speech.choose(s, now, "PAT")
                return out(0, f"쓰담쓰담… 기분 {round(r['mood'])} (오늘 {r['left']}번 더)", r, s)
            if cmd == "dex":
                species.check(s, now)
                return out(0, species.dex_text(s), species.dex_payload(s), s)
            if cmd == "stats":
                return out(0, render.stats_text(s, now), render.stats_payload(s, now), s)
            if cmd == "buy":
                if len(pos) < 2:
                    raise ActionError("무엇을 살지 알려줘: /pet buy <id>")
                r = actions.buy(s, now, pos[1])
                s["speech"] = speech.choose(s, now, "BUY", item=economy.CATALOG[r["item"]].name)
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
                    raise ActionError("어느 슬롯을 벗길지 알려줘: /pet unequip <head|face|body|room|bg>")
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
                r = actions.reset(s, now, confirm="--confirm" in flags, species=pos[1] if len(pos) > 1 else None)
                kind = species.SPECIES[r["species"]].ko
                return out(0, f"{clock.josa(s['name'], '이/가')} {kind}(으)로 새로 태어났어요", r, s)
            raise ActionError(f"모르는 명령: {cmd}\n{USAGE}")
    except ActionError as e:
        if cmd not in ("feed", "pat", "buy", "equip"):
            return out(2, str(e))
        # the refused action wrote nothing; only the pet's reaction is saved
        with store.transaction(now) as s:
            s["speech"] = speech.choose(s, now, "REFUSE")
            return out(2, str(e), state=s)


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
        try:
            _session_start_widget(now)
        except Exception as e:
            store.log(f"widget launch failed: {e!r}")
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
    # In text mode a refusal ("not enough coins") is a normal answer, and the /pet skill
    # would show a non-zero exit as "Shell command failed". JSON callers keep the code.
    return code if "--json" in argv else 0
