import pytest

from petlib import economy as E


def test_level_for_xp_boundaries():
    # every table entry is the exact xp where that level starts
    for i, need in enumerate(E.LEVELS):
        assert E.level_for_xp(need) == i + 1
        if need:
            assert E.level_for_xp(need - 1) == i
    top, step = E.LEVELS[-1], E.LEVEL_STEP_AFTER_10
    assert E.level_for_xp(top + step - 1) == 10
    assert E.level_for_xp(top + step) == 11
    assert E.level_for_xp(top + 2 * step) == 12


def test_levels_strictly_increase():
    assert E.LEVELS[0] == 0
    assert all(a < b for a, b in zip(E.LEVELS, E.LEVELS[1:]))


def test_xp_for_level_matches_table():
    for lv in range(1, 15):
        assert E.level_for_xp(E.xp_for_level(lv)) == lv
    assert E.xp_for_level(5) == E.LEVELS[4] and E.xp_for_level(10) == E.LEVELS[-1]


@pytest.mark.parametrize("form,period,mult", [
    ("base", "day", 1.0), ("model", "night", 1.1), ("scholar", "day", 1.2),
    ("owl", "night", 2.0), ("owl", "day", 1.0), ("hunter", "night", 3.0),
    ("hunter", "dawn", 1.0), ("vampire", "day", 0.95), ("vampire", "night", 1.0),
    ("burnout", "day", 0.0), ("thug", "day", 1.0),
])
def test_earn_multiplier(form, period, mult):
    assert E.earn_multiplier(form, period) == mult


def test_turn_coins_cache_bonus_boundary():
    # cache ratio exactly 0.5 gets the bonus
    base = 1000 * E.COIN_PER_OUTPUT_TOKEN
    assert E.turn_coins(1000, 50, 50, 0, "base", "day") == pytest.approx(base * E.CACHE_BONUS)
    assert E.turn_coins(1000, 51, 49, 0, "base", "day") == pytest.approx(base)
    assert E.turn_coins(1000, 0, 0, 0, "base", "day") == pytest.approx(base)


def test_price_miser():
    for item in ("fedora", "sunglasses", "plant"):
        base = E.CATALOG[item].price
        assert E.price(item, "base") == base
        assert E.price(item, "miser") == int(round(base * E.MISER_PRICE_MULT)) > base


def test_crown_lock():
    assert not E.is_unlocked("crown", {"level": 4, "form": "base"})
    assert E.is_unlocked("crown", {"level": 5, "form": "base"})
    assert E.is_unlocked("crown", {"level": 1, "form": "tycoon"})
    assert E.is_unlocked("plant", {"level": 1, "form": "base"})


@pytest.mark.parametrize("form,period,blocked", [
    ("owl", "day", True), ("owl", "night", False), ("owl", "dawn", False),
    ("vampire", "day", True), ("runaway", "night", True), ("base", "day", False),
])
def test_feed_blocked(form, period, blocked):
    assert (E.feed_blocked(form, period) is not None) == blocked


def test_forms_cover_all_sixteen():
    assert len(E.FORMS) == 16
    assert all(f.glyph for f in E.FORMS.values())


def test_output_coins_softcap_split():
    cap = E.DAILY_SOFTCAP_OUT
    assert E.output_coins(80_000) == pytest.approx(160)
    assert E.output_coins(439_000) == pytest.approx(600 + 139_000 * E.COIN_PER_OUTPUT_TOKEN_OVER_CAP)
    # a turn straddling the cap pays the high rate only for the part below it
    assert E.output_coins(10_000, cap - 4_000) == pytest.approx(4_000 * E.COIN_PER_OUTPUT_TOKEN
                                                               + 6_000 * E.COIN_PER_OUTPUT_TOKEN_OVER_CAP)
    assert E.output_coins(1_000, cap + 1) == pytest.approx(1_000 * E.COIN_PER_OUTPUT_TOKEN_OVER_CAP)


def test_turn_coins_softcap_then_form_multiplier():
    over = E.DAILY_SOFTCAP_OUT
    assert E.turn_coins(1000, 0, 0, 0, "model", "day", over) == pytest.approx(1000 * E.COIN_PER_OUTPUT_TOKEN_OVER_CAP * 1.1)
