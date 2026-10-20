import pytest

from petlib import evolve, schema, clock, economy
from conftest import at

# per-day starvation that crosses the thug threshold over a 7-day window
STARVE = evolve.THUG_ZERO_HOURS / 7 + 1

NOW = at(20, 14)


def lv5(form="base", coins=0, items=None, days=None, **over):
    s = schema.new_state(at(13, 0))
    s.update(level=5, xp=2000, coins=coins, form=form)
    if items:
        s["items_owned"] = items
    s["daily_log"] = []
    for i in range(7):
        d = schema.new_day(f"2026-10-{14 + i:02d}")
        if days:
            d.update(days[i] if i < len(days) else {})
        s["daily_log"].append(d)
    s["last_fed_at"] = clock.fmt(at(20, 10))
    s["last_tick_at"] = clock.fmt(NOW)
    s.update(over)
    return s


def same(spec, n=7):
    return [dict(spec) for _ in range(n)]


@pytest.mark.parametrize("name,kw,expected", [
    ("default", dict(days=same({"tokens_out": 1000, "earned": 20, "feeds": 2})), "model"),
    ("thug", dict(days=same({"hunger_zero_hours": STARVE})), "thug"),
    ("owl", dict(days=same({"tokens_out": 1000, "night_out": 600})), "owl"),
    ("owl_under", dict(days=same({"tokens_out": 1000, "night_out": 599})), "model"),
    ("miser", dict(coins=2000, days=same({"feeds": 1})), "miser"),
    ("miser_bought", dict(coins=2000, days=same({"feeds": 1, "purchases": 1})), "model"),
    ("spender", dict(items=["party_hat", "a", "b", "c"], days=same({"earned": 100, "spent": 80})), "spender"),
    ("spender_few_items", dict(items=["party_hat"], days=same({"earned": 100, "spent": 80})), "model"),
    ("priority_thug_over_owl", dict(days=same({"hunger_zero_hours": STARVE, "tokens_out": 10, "night_out": 10})), "thug"),
    ("priority_owl_over_miser", dict(coins=5000, days=same({"tokens_out": 10, "night_out": 10})), "owl"),
])
def test_judge_first(name, kw, expected):
    assert evolve.judge_first(lv5(**kw)) == expected


def test_check_evolves_base_at_level_5_and_resets_since_form():
    s = lv5(days=same({"tokens_out": 100, "night_out": 100}))
    s["since_form"]["days"] = 9
    ev = evolve.check(s, NOW)
    assert s["form"] == "owl" and s["since_form"]["days"] == 0
    assert s["form_since"] == clock.fmt(NOW)
    assert ev[0]["type"] == "evolve" and ev[0]["form"] == "owl"


def test_check_does_nothing_below_level_5():
    s = lv5(level=4, days=same({"hunger_zero_hours": 10}))
    assert evolve.check(s, NOW) == [] and s["form"] == "base"


# ------------------------------------------------------------ ongoing transitions

def test_any_form_becomes_thug_after_long_starving():
    s = lv5(form="model", days=same({"hunger_zero_hours": STARVE}))
    evolve.check(s, NOW)
    assert s["form"] == "thug"


def test_thug_runs_away_after_3_unfed_days():
    s = lv5(form="thug", coins=1001)
    s["flags"]["thug_days"] = 3
    ev = evolve.check(s, NOW)
    assert s["form"] == "runaway" and s["coins"] == 500
    assert any(e["type"] == "runaway" for e in ev)


def test_thug_rehab_rejudges():
    s = lv5(form="thug", days=same({"tokens_out": 100, "night_out": 100}))
    s["since_form"]["feed_streak"] = 3
    evolve.check(s, NOW)
    assert "rehab" in s["badges"] and s["form"] == "owl"


def test_neglect_7_days_runs_away():
    s = lv5(form="model", coins=10)
    s["last_fed_at"] = clock.fmt(at(13, 13))
    evolve.check(s, NOW)
    assert s["form"] == "runaway" and s["coins"] == 5


def test_runaway_and_boss_are_terminal_for_check():
    for form in ("runaway", "boss"):
        s = lv5(form=form, days=same({"hunger_zero_hours": 10}))
        assert evolve.check(s, NOW) == [] and s["form"] == form


# ------------------------------------------------------------ second tier

def lv10(form, sf=None, coins=0, items=None):
    s = lv5(form=form, coins=coins, items=items, level=10, xp=10000)
    s["since_form"].update(sf or {})
    return s


@pytest.mark.parametrize("form,sf,coins,items,expected", [
    ("model", {"tokens_in_total": 100, "cache_read": 70}, 0, None, "scholar"),
    ("model", {"tokens_in_total": 100, "cache_read": 69}, 0, None, "model"),
    ("model", {"streak_50k": 5, "tokens_in_total": 100, "cache_read": 100}, 0, None, "burnout"),
    ("miser", {"purchases": 1}, 10000, None, "tycoon"),
    ("miser", {"purchases": 0}, 10000, None, "loanshark"),
    ("miser", {"purchases": 0}, 9999, None, "miser"),
    ("owl", {"dawn_feeds": 3}, 0, None, "hunter"),
    ("owl", {"tokens_out": 100, "night_out": 90, "day_feeds": 0}, 0, None, "vampire"),
    ("owl", {"tokens_out": 100, "night_out": 90, "day_feeds": 0, "dawn_feeds": 5}, 0, None, "vampire"),
    ("owl", {"tokens_out": 100, "night_out": 90, "day_feeds": 1}, 0, None, "owl"),
    ("spender", {"refusals": 3}, 0, ["party_hat"] + list("abcde"), "influencer"),
    ("spender", {"refusals": 4}, 0, ["party_hat"] + list("abcde"), "spender"),
    ("spender", {"zero_balance_days": 5, "refusals": 5}, 0, ["party_hat"] + list("abcde"), "broke"),
    ("thug", {}, 0, None, "boss"),
])
def test_judge_second(form, sf, coins, items, expected):
    assert evolve.judge_second(lv10(form, sf, coins, items)) == expected


def test_check_applies_second_tier_at_level_10():
    s = lv10("miser", {"purchases": 1}, coins=10000)
    evolve.check(s, NOW)
    assert s["form"] == "tycoon"


def test_burnout_sets_until_and_blocks_earning():
    s = lv10("model", {"streak_50k": 5})
    evolve.check(s, NOW)
    assert s["form"] == "burnout"
    assert evolve.burnout_active(s, NOW)
    assert not evolve.burnout_active(s, at(23, 0))


def test_burnout_recovers_after_rest_day():
    s = lv10("burnout")
    s["flags"]["burnout_until"] = clock.fmt(at(19, 0))
    s["flags"]["rest_day_seen"] = True
    evolve.check(s, NOW)
    assert s["form"] == "model"


def test_vampire_recovers_with_day_feeds():
    s = lv10("vampire", {"day_feeds": 3})
    evolve.check(s, NOW)
    assert s["form"] == "owl"


def test_loanshark_recovers_with_purchase():
    s = lv10("loanshark", {"purchases": 1})
    evolve.check(s, NOW)
    assert s["form"] == "tycoon"


def test_broke_recovers_with_balance_streak():
    s = lv10("broke", {"balance_ok_streak": 3})
    evolve.check(s, NOW)
    assert s["form"] == "spender"


def test_thug_at_level_10_becomes_boss_with_hijack():
    s = lv10("thug")
    evolve.check(s, NOW)
    assert s["form"] == "boss" and s["flags"]["boss_hijack"] is True
