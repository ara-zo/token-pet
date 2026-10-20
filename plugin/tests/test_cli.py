import json
from pathlib import Path

import pytest

from petlib import cli, economy, store, schema, clock
from conftest import at

FIXTURE = str(Path(__file__).parent / "fixtures" / "transcript_3lines.jsonl")
NOW = at(20, 14)
STOP = {"session_id": "s1", "transcript_path": FIXTURE, "hook_event_name": "Stop"}


def test_collect_earns_once(pet_home):
    earned = cli.main_collect(STOP, NOW, plugin_root="/plug")
    s = store.load()
    # msg_A: 447 out with cache ratio 0.544 (bonus) ; msg_B: 100 out, no bonus
    raw = 447 * economy.COIN_PER_OUTPUT_TOKEN * economy.CACHE_BONUS + 100 * economy.COIN_PER_OUTPUT_TOKEN
    E = int(raw)
    assert E >= 1, "fixture should earn at least one whole coin"
    assert earned == E and s["coins"] == E and s["xp"] == E
    assert s["coin_carry"] == pytest.approx(raw - E, abs=1e-3)
    day = s["daily_log"][-1]
    assert day["tokens_out"] == 547 and day["night_out"] == 547    # 13:58Z/14:30Z = 22:58/23:30 KST
    assert day["sessions"] == 1 and day["day_sessions"] == 1 and day["earned"] == E
    assert s["plugin_root"] == "/plug" and s["last_turn_earned"] == E
    assert s["sessions"]["s1"]["offset"] == Path(FIXTURE).stat().st_size

    assert cli.main_collect(STOP, at(20, 15)) == 0
    s = store.load()
    assert s["coins"] == E and s["daily_log"][-1]["sessions"] == 1


def test_reset_does_not_recount_old_transcript(pet_home):
    cli.main_collect(STOP, NOW)
    assert store.load()["coins"] > 0
    assert cli.main_pet(["reset", "--confirm"], NOW)[0] == 0
    # same session, nothing new written to the transcript → nothing new to earn
    assert cli.main_collect(STOP, at(20, 15)) == 0
    s = store.load()
    assert s["coins"] == 0 and s["xp"] == 0


def test_collect_levels_up_and_evolves(pet_home):
    with store.transaction(NOW, tick=False) as s:
        s["xp"] = economy.LEVELS[economy.FIRST_EVOLUTION_LEVEL - 1] - 1   # one coin short of Lv.5
        s["level"] = 4
    cli.main_collect(STOP, NOW)
    s = store.load()
    assert s["level"] == 5 and s["form"] == "owl"      # fixture turns are all at night (KST)
    assert [e["type"] for e in s["events"]] == ["levelup", "evolve"]


def test_collect_ignores_missing_fields(pet_home):
    assert cli.main_collect({}, NOW) is None
    assert not store.state_path().exists()


def test_session_start_first_run_announces_birth(pet_home):
    r = cli.main_session_start({"session_id": "x"}, NOW, plugin_root="/plug")
    assert "태어났어요" in r["hookSpecificOutput"]["additionalContext"]
    assert r["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert cli.main_session_start({"session_id": "x"}, NOW) is None
    assert store.load()["plugin_root"] == "/plug"


def test_session_start_delivers_pending_events_once(pet_home):
    with store.transaction(NOW, tick=False) as s:
        schema.push_event(s, NOW, "extort", "삥")
        schema.push_event(s, NOW, "feed", "냠")
    r = cli.main_session_start({}, NOW)
    assert r["hookSpecificOutput"]["additionalContext"] == "[token-pet] 삥"
    assert cli.main_session_start({}, NOW) is None


def test_statusline_without_state(pet_home):
    assert cli.main_statusline({"model": {"display_name": "Opus"}}, NOW).endswith("Opus\x1b[0m")


def test_pet_status_feed_shop_roundtrip(pet_home):
    with store.transaction(NOW, tick=False) as s:
        s["coins"] = 100
        s["hunger"] = 30
    code, text = cli.main_pet(["status"], NOW)
    assert code == 0 and "모찌" in text and "Lv.1" in text
    code, text = cli.main_pet(["feed", "--json"], NOW)
    assert code == 0
    payload = json.loads(text)
    F = economy.FEED_COST
    assert payload["ok"] and payload["result"]["cost"] == F and payload["state"]["coins"] == 100 - F
    code, text = cli.main_pet(["feed"], NOW)        # drain until the json feed below is refused
    cli.main_pet(["feed"], NOW)
    code, text = cli.main_pet(["feed", "--json"], NOW)
    assert code == 2 and json.loads(text)["ok"] is False and "모자라" in json.loads(text)["text"]
    code, text = cli.main_pet(["shop"], NOW)
    assert "plant" in text


def test_pet_shop_json_catalog(pet_home):
    with store.transaction(NOW, tick=False) as s:
        s["coins"] = 100
        s["items_owned"].append("plant")
        s["equipped"]["room"] = "plant"
    code, text = cli.main_pet(["shop", "--json"], NOW)
    assert code == 0
    payload = json.loads(text)
    assert payload["ok"] and payload["result"]["blocked"] is False
    assert payload["result"]["feed_cost"] == economy.FEED_COST
    items = {i["id"]: i for i in payload["result"]["catalog"]}
    assert "party_hat" not in items                      # free starter item is not for sale
    assert items["plant"]["owned"] and items["plant"]["equipped"]
    assert items["fedora"] == {"id": "fedora", "name": "중절모", "slot": "head", "price": economy.CATALOG["fedora"].price,
                               "owned": False, "equipped": False, "unlocked": True, "min_level": None}
    assert items["crown"]["unlocked"] is False and items["crown"]["min_level"] == 5

    with store.transaction(NOW, tick=False) as s:
        s["form"] = "thug"
    payload = json.loads(cli.main_pet(["shop", "--json"], NOW)[1])
    assert payload["result"]["blocked"] is True and payload["result"]["catalog"] == []


def test_pet_buy_equip_name(pet_home):
    with store.transaction(NOW, tick=False) as s:
        s["coins"] = economy.CATALOG["fedora"].price + 100
    assert cli.main_pet(["buy"], NOW)[0] == 2
    code, text = cli.main_pet(["buy", "fedora"], NOW)
    assert code == 0 and "중절모" in text
    assert cli.main_pet(["equip", "fedora"], NOW)[0] == 0
    assert store.load()["equipped"]["head"] == "fedora"
    assert cli.main_pet(["unequip", "head"], NOW)[0] == 0
    assert cli.main_pet(["name", "콩이"], NOW)[1] == "이제부터 콩이!"
    assert cli.main_pet(["dance"], NOW)[0] == 2


def test_pet_reset_and_find(pet_home):
    with store.transaction(NOW, tick=False) as s:
        s["form"] = "runaway"
        s["level"] = 5
    assert "1/3" in cli.main_pet(["find"], NOW)[1]
    assert cli.main_pet(["reset"], NOW)[0] == 2
    assert cli.main_pet(["reset", "--confirm"], NOW)[0] == 0
    assert store.load()["form"] == "base"


def test_setup_prompt_write_and_exists(pet_home, tmp_path, monkeypatch):
    cfg = tmp_path / "cfg"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    code, text = cli.main_pet(["setup"], NOW)
    assert code == 0 and text.startswith("SETUP_PROMPT")
    assert not (cfg / "settings.json").exists()

    cfg.mkdir()
    (cfg / "settings.json").write_text('{"theme": "dark"}')
    code, text = cli.main_pet(["setup", "--write"], NOW)
    assert text.startswith("SETUP_DONE")
    settings = json.loads((cfg / "settings.json").read_text())
    assert settings["theme"] == "dark"
    assert settings["statusLine"]["command"] == f"python3 {pet_home / 'statusline.py'}"
    assert (pet_home / "statusline.py").read_text().startswith("#!/usr/bin/env python3")

    code, text = cli.main_pet(["setup", "--write"], NOW)          # idempotent
    assert text.startswith("SETUP_DONE")
    (cfg / "settings.json").write_text(json.dumps({"statusLine": {"type": "command", "command": "other"}}))
    code, text = cli.main_pet(["setup", "--write"], NOW)
    assert text.startswith("SETUP_EXISTS")


def test_run_dispatch_never_raises(pet_home, monkeypatch, capsys):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert cli.run(["collect"]) == 0
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"session_id": "a", "transcript_path": "/nope"})))
    assert cli.run(["collect"]) == 0
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    assert cli.run(["session-start"]) == 0
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"model": {"display_name": "M"}})))
    assert cli.run(["statusline"]) == 0
    assert "M" in capsys.readouterr().out
