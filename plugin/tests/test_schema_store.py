import json
import multiprocessing
import os

from petlib import schema, store, clock
from conftest import at

EXPECTED_KEYS = {
    "version", "name", "created_at", "level", "xp", "coins", "coin_carry",
    "hunger", "mood", "form", "form_since", "items_owned", "equipped",
    "last_fed_at", "last_tick_at", "last_turn_at", "last_turn_earned",
    "plugin_root", "speech", "events", "sessions", "daily_log", "since_form",
    "flags", "badges", "settings", "species", "dex", "lifetime",
}


def test_new_state_keys(state):
    assert set(state.keys()) == EXPECTED_KEYS
    assert state["items_owned"] == ["party_hat", "street"]
    assert state["equipped"] == {"head": "party_hat", "bg": "street"}
    assert state["daily_log"][0]["date"] == "2026-10-20"


def test_migrate_fills_missing_keys():
    s = schema.migrate({"version": 0, "coins": 5})
    assert set(s.keys()) == EXPECTED_KEYS
    assert s["coins"] == 5
    assert s["version"] == schema.VERSION
    assert s["daily_log"] == []


def test_migrate_fills_nested_keys():
    s = schema.migrate({"flags": {"debt": 3}, "since_form": {}})
    assert s["flags"]["debt"] == 3
    assert s["flags"]["find_days"] == []
    assert s["since_form"]["streak_50k"] == 0


def test_today_creates_new_day(state):
    d = schema.today(state, at(21, 9))
    assert d["date"] == "2026-10-21"
    assert [x["date"] for x in state["daily_log"]] == ["2026-10-20", "2026-10-21"]
    assert schema.today(state, at(21, 10)) is d


# ---------------------------------------------------------------- store

def test_load_missing_returns_new_state_without_writing(pet_home, fixed_now):
    s = store.load(fixed_now)
    assert s["name"] == "모찌"
    assert not store.state_path().exists()


def test_transaction_creates_and_persists(pet_home, fixed_now):
    with store.transaction(fixed_now, tick=False) as s:
        s["coins"] = 42
    assert json.loads(store.state_path().read_text())["coins"] == 42
    with store.transaction(fixed_now, tick=False) as s:
        assert s["coins"] == 42
    assert not list(pet_home.glob("*.tmp*"))


def _bump(home, n):
    os.environ["PET_HOME"] = home
    for _ in range(n):
        with store.transaction(clock.now(), tick=False) as s:
            s["coins"] += 1


def test_concurrent_transactions_preserve_total(pet_home):
    procs = [multiprocessing.Process(target=_bump, args=(str(pet_home), 50)) for _ in range(8)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    assert store.load()["coins"] == 400


def test_log_keeps_last_50_lines(pet_home):
    for i in range(60):
        store.log(f"line {i}")
    lines = (pet_home / "collect.log").read_text().splitlines()
    assert len(lines) == 50
    assert lines[-1].endswith("line 59")
    assert lines[0].endswith("line 10")
