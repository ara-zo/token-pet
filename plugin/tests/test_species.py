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
    assert species.check(s, NOW) == [] and key not in s["dex"]
    s["lifetime"][metric] = goal
    ev = species.check(s, NOW)
    assert key in s["dex"] and ev[-1]["type"] == "dex" and species.SPECIES[key].ko in ev[-1]["text"]
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


def test_reset_picks_a_registered_species_and_keeps_the_dex():
    s = fresh(coins=500)
    s["dex"].append("mole")
    s["lifetime"]["pats"] = 12
    with pytest.raises(ActionError, match="도감"):
        actions.reset(s, NOW, confirm=True, species="robot")
    actions.reset(s, NOW, confirm=True, species="mole")
    assert s["species"] == "mole" and s["coins"] == 0 and s["dex"] == ["mochi", "mole"]
    assert s["lifetime"]["pats"] == 12
    actions.reset(s, NOW, confirm=True)                      # no choice: keep the current species
    assert s["species"] == "mole"
    with pytest.raises(ActionError, match="그런 종족"):
        actions.reset(s, NOW, confirm=True, species="dragon")


def test_cli_dex_and_reset_with_species(pet_home):
    with store.transaction(NOW, tick=False) as s:
        s["lifetime"]["tokens_out"] = 400_000
        s["lifetime"]["pats"] = 50
    code, text = cli.main_pet(["dex", "--json"], NOW)
    r = json.loads(text)["result"]
    rows = {row["id"]: row for row in r["species"]}
    assert r["current"] == "mochi" and rows["hamster"]["unlocked"]          # unlocked by the tick
    assert rows["mole"]["cur"] == 400_000 and rows["mole"]["goal"] == 1_000_000 and not rows["mole"]["unlocked"]
    code, text = cli.main_pet(["dex"], NOW)
    assert code == 0 and "유리볼 햄스터" in text and "400,000" in text
    code, text = cli.main_pet(["reset", "--confirm", "hamster"], NOW)
    assert code == 0 and store.load()["species"] == "hamster"
    assert "유리볼 햄스터" in cli.main_pet(["status"], NOW)[1]


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
