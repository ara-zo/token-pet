import datetime as dt

import pytest

from petlib import tick, schema, clock, economy, evolve

H = economy.HUNGER_PER_HOUR
from conftest import at


def fresh(now, **over):
    s = schema.new_state(now)
    s.update(over)
    return s


def test_ten_hours_decay():
    s = fresh(at(20, 0))
    tick.apply(s, at(20, 5))
    assert s["hunger"] == pytest.approx(80 - 5 * H) and s["mood"] == 70
    assert s["last_tick_at"] == clock.fmt(at(20, 5))
    s = fresh(at(20, 0))
    tick.apply(s, at(20, 10))
    assert s["last_tick_at"] == clock.fmt(at(20, 10))


def test_model_form_hunger_slower():
    s = fresh(at(20, 0), form="model")
    tick.apply(s, at(20, 5))
    assert s["hunger"] == pytest.approx(80 - 5 * H * 0.7)


def test_hunger_hits_zero_and_accumulates_zero_hours():
    s = fresh(at(20, 0))
    to_zero = 80 / H                 # hours until a fresh pet (hunger 80) starves; must stay < 24
    tick.apply(s, at(20, 0) + dt.timedelta(minutes=int(to_zero * 60) - 1))   # a minute before zero
    assert s["hunger"] > 0
    s = fresh(at(19, 0))
    tick.apply(s, at(20, 16))        # 40h, single day boundary at 20 00:00
    assert s["hunger"] == 0
    day19 = s["daily_log"][0]
    day20 = s["daily_log"][1]
    # starvation starts on day 19 after to_zero hours, then all 16h of day 20
    assert day19["hunger_zero_hours"] == pytest.approx(24 - to_zero, abs=0.01)
    assert day20["hunger_zero_hours"] == pytest.approx(16.0, abs=0.01)
    # mood drains 2/h then 4/h over 40h → clamped 0
    assert s["mood"] == 0


def test_multi_day_rollover_creates_days_and_trims():
    s = fresh(at(1, 12))
    tick.apply(s, at(20, 12))
    dates = [d["date"] for d in s["daily_log"]]
    assert len(dates) == schema.DAILY_LOG_DAYS
    assert dates[-1] == "2026-10-20" and dates[0] == "2026-10-07"
    assert s["since_form"]["days"] == 19


def test_max_gap_hours_tracked():
    s = fresh(at(20, 0))
    tick.apply(s, at(20, 7))
    assert schema.today(s, at(20, 7))["max_gap_hours"] == 7


def test_sessions_pruned_after_7_days():
    s = fresh(at(10, 0))
    s["sessions"] = {"old": {"offset": 1, "seen_ids": [], "updated_at": clock.fmt(at(10, 0))},
                     "new": {"offset": 1, "seen_ids": [], "updated_at": clock.fmt(at(19, 0))}}
    tick.apply(s, at(20, 0))
    assert set(s["sessions"]) == {"new"}


def test_clock_going_backwards_is_harmless():
    s = fresh(at(20, 10))
    tick.apply(s, at(20, 9))
    assert s["hunger"] == 80 and s["last_tick_at"] == clock.fmt(at(20, 9))


# ----------------------------------------------------------- daily effects

def rollover(form, **over):
    s = fresh(at(20, 23), form=form, **over)
    s["hunger"] = 100
    ev = tick.apply(s, at(21, 0, 30))
    return s, ev


@pytest.mark.parametrize("form,coins,expected", [
    ("miser", 1000, 1010), ("tycoon", 1000, 1030),
    ("thug", 1000, 900), ("boss", 1000, 750), ("base", 1000, 1000),
])
def test_daily_money_effects(form, coins, expected):
    s, _ = rollover(form, coins=coins)
    assert s["coins"] == expected


def test_loanshark_debt_interest_taken_from_balance():
    s, ev = rollover("loanshark", coins=50)
    assert s["coins"] == 50
    s = fresh(at(20, 23), form="loanshark", coins=50)
    s["flags"]["debt"] = 30
    tick.apply(s, at(21, 0, 30))
    assert s["flags"]["debt"] == 0 and s["coins"] == 17      # 30 + ceil(3) = 33 paid


def test_spender_demand_and_refusal():
    s, ev = rollover("spender")
    assert s["flags"]["demand_item"] == "plant"              # cheapest unowned
    assert any(e["type"] == "demand" for e in ev)
    tick.apply(s, at(22, 0, 30))                              # ignored a whole day
    assert s["daily_log"][-2]["refusals"] == 1
    assert s["since_form"]["refusals"] == 1


def test_broke_sells_most_expensive_item_and_drops_mood():
    s = fresh(at(20, 23), form="broke")
    s["items_owned"] = ["party_hat", "plant", "hoodie"]
    s["equipped"] = {"head": "party_hat", "body": "hoodie"}
    s["mood"] = 90
    tick.apply(s, at(21, 0, 30))
    assert s["items_owned"] == ["party_hat", "plant"]
    assert "body" not in s["equipped"]
    assert s["coins"] == int(economy.CATALOG["hoodie"].price * economy.BROKE_SELL_RATIO)
    assert s["mood"] < 60


def test_streaks_and_zero_balance():
    s = fresh(at(20, 23), form="model", coins=0)
    schema.today(s, at(20, 23))["tokens_out"] = evolve.BURNOUT_DAILY_OUT
    tick.apply(s, at(21, 0, 30))
    sf = s["since_form"]
    assert sf["streak_50k"] == 1 and sf["feed_streak"] == 0 and sf["zero_balance_days"] == 1
    assert s["daily_log"][-2]["zero_balance"] is True
    schema.today(s, at(21, 1))["feeds"] = 2
    schema.today(s, at(21, 1))["tokens_out"] = 10
    s["coins"] = 600
    tick.apply(s, at(22, 0, 30))
    sf = s["since_form"]
    assert sf["streak_50k"] == 0 and sf["feed_streak"] == 1 and sf["balance_ok_streak"] == 1


def test_thug_days_count_unfed_days():
    s = fresh(at(20, 23), form="thug")
    tick.apply(s, at(22, 0, 30))
    assert s["flags"]["thug_days"] == 2


def test_burnout_rest_day_flag():
    s = fresh(at(20, 23), form="burnout", level=10)
    s["flags"]["burnout_until"] = clock.fmt(at(22, 23))
    tick.apply(s, at(21, 0, 30))
    assert s["flags"]["rest_day_seen"] is True
    assert s["form"] == "burnout"          # still inside the 2-day penalty
    s["hunger"] = 100.0                    # keep it fed: this test is about resting, not starving
    tick.apply(s, at(22, 12))
    s["hunger"] = 100.0
    tick.apply(s, at(23, 0, 30))
    assert s["form"] == "model"            # penalty over + rested → recovered


def test_background_bonuses_apply_to_matching_family_only():
    s = fresh(at(20, 23), form="miser", coins=10000)
    s["items_owned"].append("vault")
    s["equipped"]["bg"] = "vault"
    tick.apply(s, at(21, 0, 1))
    assert s["coins"] == 10000 + int(10000 * (0.01 + 0.005))

    s = fresh(at(20, 23), form="model", coins=10000, mood=50)
    s["items_owned"].append("night_factory")
    s["equipped"]["bg"] = "night_factory"
    tick.apply(s, at(21, 0, 1))
    assert s["mood"] < 50                                   # not nocturnal: no bonus

    s = fresh(at(20, 23), form="owl", mood=50)
    s["equipped"]["bg"] = "night_factory"
    tick.apply(s, at(21, 0, 1))
    assert s["mood"] > 50


def test_evolving_into_thug_grants_alley():
    from petlib import evolve
    s = fresh(at(20, 23))
    evolve.set_form(s, "thug", at(20, 23), "test")
    assert "alley" in s["items_owned"]
