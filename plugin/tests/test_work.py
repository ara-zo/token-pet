import pytest

from petlib import economy, schema, tick, work
from conftest import at


def test_output_makes_the_pet_hungry(state):
    state["hunger"] = 50
    work.apply_output(state, at(20, 14), 80_000, at(20, 14))
    assert state["hunger"] == pytest.approx(42)
    assert state["mood"] == 80                       # under the hourly rush line: mood untouched


def test_hunger_follows_the_form_rate(state):
    state["hunger"], state["form"] = 50, "model"
    work.apply_output(state, at(20, 14), 100_000, at(20, 14))
    assert state["hunger"] == pytest.approx(50 - 10 * 0.7)


def test_rush_hour_costs_mood_past_the_line_once_per_hour(state):
    state["hunger"] = 100
    work.apply_output(state, at(20, 14, 10), 90_000, at(20, 14, 10))
    assert state["mood"] == 80
    work.apply_output(state, at(20, 14, 40), 60_000, at(20, 14, 40))     # 150k this hour → 50k over
    assert state["mood"] == pytest.approx(75)
    work.apply_output(state, at(20, 14, 50), 20_000, at(20, 14, 50))
    assert state["mood"] == pytest.approx(73)
    assert [e["type"] for e in state["events"]].count("tired") == 1
    work.apply_output(state, at(20, 15, 5), 90_000, at(20, 15, 5))      # new hour starts from zero
    assert state["mood"] == pytest.approx(73)
    assert state["work_hour"]["hour"] == "2026-10-20T15"


def test_rush_mood_respects_the_form_floor(state):
    state["form"], state["mood"] = "spender", 71
    work.apply_output(state, at(20, 14), 300_000, at(20, 14))
    assert state["mood"] == 70


@pytest.mark.parametrize("out,gain", [(49_999, 0), (50_000, 5), (300_000, 5), (300_001, 0)])
def test_moderate_day_lifts_mood_at_midnight(state, out, gain):
    state["mood"] = 60
    state["last_tick_at"] = "2026-10-20T23:59:00+09:00"
    schema.today(state, at(20, 23, 59))["tokens_out"] = out
    tick.apply(state, at(21, 0))
    assert state["mood"] == pytest.approx(60 - economy.MOOD_PER_HOUR / 60 + gain, abs=0.01)
    assert ("goodday" in [e["type"] for e in state["events"]]) == bool(gain)
