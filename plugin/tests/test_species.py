import datetime as dt
import json

import pytest

from petlib import actions, cli, economy, evolve, schema, species, store, clock
from petlib.actions import ActionError
from conftest import at

NOW = at(20, 14)


def fresh(**over):
    s = schema.new_state(at(20, 0))
    s.update(over)
    return s


def test_new_pet_is_mochi_with_mochi_in_dex():
    s = fresh()
    assert s["species"] == "mochi" and s["dex"] == ["mochi"]
    assert set(species.ORDER) == set(species.SPECIES) and species.ORDER[0] == "mochi"


@pytest.mark.parametrize("key,metric", [
    ("squirrel", "max_coins"), ("mole", "tokens_out"), ("robot", "attend_streak_max"),
    ("penguin", "night_out"), ("hamster", "pats"), ("rabbit", "evolutions"),
])
def test_each_species_unlocks_at_its_goal(key, metric):
    s = fresh()
    goal = species.SPECIES[key].goal
    s["lifetime"][metric] = goal - 1
    early = species.check(s, NOW)
    assert key not in s["dex"] and all(e["type"] == "dex_sign" for e in early)
    s["lifetime"][metric] = goal
    ev = species.check(s, NOW)
    assert key in s["dex"] and ev[-1]["type"] == "dex"
    assert species.SPECIES[key].ko in ev[-1]["text"] and species.SPECIES[key].condition in ev[-1]["text"]  # revealed now
    assert species.check(s, NOW) == []                       # registered once


def test_attendance_streak_counts_consecutive_days_only():
    s = fresh()
    for d in (20, 20, 21, 22):
        species.record_attendance(s, at(d, 10))
    assert s["lifetime"]["attend_streak"] == 3
    species.record_attendance(s, at(24, 10))                  # skipped the 23rd
    assert s["lifetime"]["attend_streak"] == 1 and s["lifetime"]["attend_streak_max"] == 3


def test_max_coins_tracks_the_peak_balance():
    s = fresh(coins=1800)
    species.check(s, NOW)
    s["coins"] = 300
    species.check(s, NOW)
    assert s["lifetime"]["max_coins"] == 1800


def test_migrate_seeds_lifetime_from_daily_log():
    s = fresh()
    del s["lifetime"]
    s["daily_log"][0].update(tokens_out=5000, night_out=2000, pats=3)
    schema.migrate(s)
    assert s["lifetime"]["tokens_out"] == 5000 and s["lifetime"]["night_out"] == 2000 and s["lifetime"]["pats"] == 3


def test_pat_and_evolution_feed_the_lifetime_counters():
    s = fresh(mood=50)
    actions.pat(s, NOW)
    assert s["lifetime"]["pats"] == 1
    evolve.set_form(s, "model", NOW, "test")
    assert s["lifetime"]["evolutions"] == 1
    evolve.set_form(s, "runaway", NOW, "test")               # running away is not an evolution
    assert s["lifetime"]["evolutions"] == 1


def test_reset_restarts_only_the_active_pet_and_keeps_the_dex():
    s = fresh(coins=500)
    s["dex"].append("mole")
    s["lifetime"]["pats"] = 12
    s["pets"] = {"mole": {"species": "mole", "level": 3}}
    s["level"], s["form"] = 6, "owl"
    actions.reset(s, NOW, confirm=True)
    assert s["species"] == "mochi" and s["level"] == 1 and s["form"] == "base"
    assert s["coins"] == 500                                 # the wallet is shared by every pet
    assert s["dex"] == ["mochi", "mole"] and s["lifetime"]["pats"] == 12
    assert s["pets"]["mole"]["level"] == 3                   # the resting pet is untouched


def test_cli_dex_keeps_locked_species_mysterious(pet_home):
    with store.transaction(NOW, tick=False) as s:
        s["lifetime"]["tokens_out"] = 400_000
        s["lifetime"]["pats"] = 50
    code, text = cli.main_pet(["dex", "--json"], NOW)
    r = json.loads(text)["result"]
    rows = {row["id"]: row for row in r["species"]}
    assert r["current"] == "mochi" and rows["hamster"]["unlocked"] and not rows["hamster"]["owned"]
    assert rows["hamster"]["adopt_cost"] == species.ADOPT_COST["hamster"]
    assert rows["hamster"]["condition"] == species.SPECIES["hamster"].condition    # revealed once met
    mole = rows["mole"]
    assert not mole["unlocked"] and mole["name"] == "???" and mole["hint"] == species.SPECIES["mole"].hint
    assert "condition" not in mole and "cur" not in mole and "goal" not in mole    # no numbers to grind
    assert mole["sign"] == 1                                                        # 40% of the way
    code, text = cli.main_pet(["dex"], NOW)
    assert code == 0 and "유리볼 햄스터" in text and "입양" in text
    assert "두더지" not in text and "400,000" not in text and species.SPECIES["mole"].hint in text


def test_sign_levels_and_the_almost_there_event():
    s = fresh()
    goal = species.SPECIES["mole"].goal
    assert species.sign(s, "mole") == 0
    s["lifetime"]["tokens_out"] = int(goal * 0.5)
    assert species.sign(s, "mole") == 1 and species.check(s, NOW) == []
    s["lifetime"]["tokens_out"] = int(goal * 0.8)
    ev = species.check(s, NOW)
    assert species.sign(s, "mole") == 2 and [e["type"] for e in ev] == ["dex_sign"]
    assert "두더지" not in ev[0]["text"]                                             # the name stays hidden
    assert species.check(s, NOW) == []                                              # once only


def test_collect_counts_lifetime_tokens_and_attendance(pet_home):
    from pathlib import Path
    fixture = str(Path(__file__).parent / "fixtures" / "transcript_3lines.jsonl")
    cli.main_collect({"session_id": "s1", "transcript_path": fixture}, NOW)
    s = store.load()
    assert s["lifetime"]["tokens_out"] == 547 and s["lifetime"]["night_out"] == 547
    assert s["lifetime"]["attend_streak"] == 1


def test_migrate_seeds_attendance_streak_from_log():
    s = fresh()
    del s["lifetime"]
    s["daily_log"] = [schema.new_day(f"2026-10-{d}") for d in (15, 17, 18, 19)]
    for d in s["daily_log"]:
        d["sessions"] = 1
    schema.migrate(s)
    assert s["lifetime"]["attend_streak"] == 3 and s["lifetime"]["last_attend"] == "2026-10-19"


# ------------------------------------------------------------ roster: adopt and switch

def unlocked(**over):
    over.setdefault("coins", 5000)
    s = fresh(**over)
    s["dex"] += ["hamster", "mole"]
    return s


def test_adopt_needs_dex_coins_and_makes_the_new_pet_active():
    s = unlocked(level=4, xp=8000, hunger=33)
    with pytest.raises(ActionError, match="도감"):
        species.adopt(s, NOW, "robot")
    poor = unlocked(coins=10)
    with pytest.raises(ActionError, match="모자라"):
        species.adopt(poor, NOW, "hamster")
    r = species.adopt(s, NOW, "hamster")
    cost = species.ADOPT_COST["hamster"]
    assert r["species"] == "hamster" and s["coins"] == 5000 - cost
    assert s["species"] == "hamster" and s["level"] == 1 and s["xp"] == 0 and s["form"] == "base"
    assert s["name"] == species.SPECIES["hamster"].ko
    assert s["pets"]["mochi"]["level"] == 4 and s["pets"]["mochi"]["hunger"] == 33   # mochi rests as it was
    with pytest.raises(ActionError, match="이미"):
        species.adopt(s, NOW, "mochi")
    with pytest.raises(ActionError, match="이미"):
        species.adopt(s, NOW, "hamster")


def test_switch_swaps_pets_and_rest_freezes_time():
    s = unlocked(level=4, xp=8000, hunger=60)
    s["equipped"]["head"] = "party_hat"
    species.adopt(s, NOW, "hamster", name="콩이")
    assert s["name"] == "콩이" and "head" not in s["equipped"]               # equipped belongs to each pet
    coins = s["coins"]
    later = NOW + dt.timedelta(days=10)                                    # mochi rested ten days
    species.switch(s, later, "mochi")
    assert s["species"] == "mochi" and s["level"] == 4 and s["hunger"] == 60
    assert s["equipped"]["head"] == "party_hat" and s["coins"] == coins     # one shared wallet
    # the rest does not count as being left unfed: no runaway on return
    assert clock.hours_between(clock.parse(s["last_fed_at"]), later) < 24
    assert s["pets"]["hamster"]["name"] == "콩이"
    with pytest.raises(ActionError, match="없어"):
        species.switch(s, later, "mole")                                  # unlocked but never adopted
    with pytest.raises(ActionError, match="이미"):
        species.switch(s, later, "mochi")


def test_cli_adopt_and_switch(pet_home):
    with store.transaction(NOW, tick=False) as s:
        s["coins"] = 3000
        s["dex"].append("hamster")
    payload = json.loads(cli.main_pet(["adopt", "hamster", "--json"], NOW)[1])
    assert payload["ok"] and payload["state"]["species"] == "hamster"
    assert {r["id"]: r for r in payload["result"]["species"]}["mochi"]["resting"]["level"] == 1
    code, text = cli.main_pet(["switch", "mochi"], NOW)
    assert code == 0 and store.load()["species"] == "mochi" and "모찌" in text
    assert "쉬는 중" in cli.main_pet(["status"], NOW)[1]
