import pytest

from petlib import actions, schema, clock, economy
from petlib.actions import ActionError
from conftest import at

NOW = at(20, 14)        # day
NIGHT = at(20, 23)
DAWN = at(20, 5)


def st(form="base", coins=100, level=1, **over):
    s = schema.new_state(at(20, 0))
    s.update(form=form, coins=coins, level=level, hunger=50)
    s.update(over)
    return s


def test_feed_ok():
    s = st()
    r = actions.feed(s, NOW)
    F = economy.FEED_COST
    assert r == {"hunger": 90, "coins": 100 - F, "cost": F, "debt": 0}
    d = schema.today(s, NOW)
    assert d["feeds"] == 1 and d["day_feeds"] == 1 and d["dawn_feeds"] == 0
    assert s["last_fed_at"] == clock.fmt(NOW)
    assert s["events"][-1]["type"] == "feed"


def test_feed_caps_at_100():
    s = st(hunger=90)
    assert actions.feed(s, NOW)["hunger"] == 100


def test_feed_dawn_counts():
    s = st()
    actions.feed(s, DAWN)
    assert schema.today(s, DAWN)["dawn_feeds"] == 1


def test_feed_not_enough_coins():
    s = st(coins=29)
    with pytest.raises(ActionError, match="모자라"):
        actions.feed(s, NOW)


def test_loanshark_feeds_on_credit():
    s = st(form="loanshark", coins=10)
    r = actions.feed(s, NOW)
    assert r["coins"] == 0 and r["debt"] == economy.FEED_COST - 10


def test_owl_refuses_day_allows_night():
    s = st(form="owl")
    with pytest.raises(ActionError, match="자고"):
        actions.feed(s, NOW)
    actions.feed(s, NIGHT)


def test_vampire_force_feed_costs_double():
    s = st(form="vampire")
    with pytest.raises(ActionError):
        actions.feed(s, NOW)
    r = actions.feed(s, NOW, force=True)
    assert r["cost"] == economy.FORCE_FEED_COST == 2 * economy.FEED_COST
    assert r["coins"] == 100 - economy.FORCE_FEED_COST


def test_runaway_cannot_be_fed():
    with pytest.raises(ActionError, match="가출"):
        actions.feed(st(form="runaway"), NOW)


# ------------------------------------------------------------------ buy

def test_buy_ok_records_spend():
    p = economy.CATALOG["plant"].price
    s = st(coins=p + 50)
    r = actions.buy(s, NOW, "plant")
    assert r["cost"] == p and s["coins"] == 50 and "plant" in s["items_owned"]
    d = schema.today(s, NOW)
    assert d["spent"] == p and d["purchases"] == 1


def test_buy_unknown_duplicate_locked_blocked():
    with pytest.raises(ActionError):
        actions.buy(st(), NOW, "jetpack")
    with pytest.raises(ActionError, match="이미"):
        actions.buy(st(), NOW, "party_hat")
    with pytest.raises(ActionError, match="Lv.5"):
        actions.buy(st(coins=9999), NOW, "crown")
    with pytest.raises(ActionError, match="봉쇄"):
        actions.buy(st(form="thug", coins=9999), NOW, "plant")


def test_buy_miser_pays_more():
    s = st(form="miser", coins=9999)
    assert actions.buy(s, NOW, "plant")["cost"] == round(economy.CATALOG["plant"].price * economy.MISER_PRICE_MULT)


def test_buy_resolves_demand_and_influencer_refund():
    p = economy.CATALOG["plant"].price
    s = st(form="influencer", coins=p + 50)
    s["flags"]["demand_item"] = "plant"
    r = actions.buy(s, NOW, "plant")
    refund = int(p * economy.INFLUENCER_REFUND)
    assert r["refund"] == refund and s["coins"] == 50 + refund
    assert s["flags"]["demand_item"] is None


# ------------------------------------------------------------------ equip / rename

def test_equip_and_unequip():
    s = st()
    s["items_owned"].append("fedora")
    assert actions.equip(s, "fedora") == {"slot": "head", "item": "fedora"}
    assert s["equipped"]["head"] == "fedora"
    with pytest.raises(ActionError):
        actions.equip(s, "crown")
    assert actions.unequip(s, "head")["removed"] == "fedora"
    with pytest.raises(ActionError):
        actions.unequip(s, "tail")


def test_rename_limits():
    s = st()
    actions.rename(s, " 콩이 ")
    assert s["name"] == "콩이"
    with pytest.raises(ActionError):
        actions.rename(s, "")
    with pytest.raises(ActionError):
        actions.rename(s, "아주아주긴이름이야")


# ------------------------------------------------------------------ find / reset

def test_find_three_distinct_days_returns():
    s = st(form="runaway")
    assert actions.find(s, at(20, 10))["found"] is False
    assert actions.find(s, at(20, 22))["days"] == 1
    actions.find(s, at(21, 10))
    r = actions.find(s, at(22, 10))
    assert r["found"] is True and s["form"] == "model" and "returned" in s["badges"]
    with pytest.raises(ActionError):
        actions.find(s, NOW)


def test_reset_requires_confirm_unless_boss():
    s = st(coins=500)
    with pytest.raises(ActionError):
        actions.reset(s, NOW)
    s["badges"] = ["rehab"]
    actions.reset(s, NOW, confirm=True)
    assert s["coins"] == 500 and s["badges"] == ["rehab"] and s["level"] == 1   # wallet is shared, kept
    b = st(form="boss")
    actions.reset(b, NOW)
    assert b["form"] == "base" and "independence" in b["badges"]


# ------------------------------------------------------------------ pat

def test_pat_raises_mood_with_daily_limit():
    s = st(mood=50)
    r = actions.pat(s, NOW)
    assert s["mood"] == 50 + economy.PAT_MOOD
    assert r == {"mood": s["mood"], "left": economy.PAT_DAILY_LIMIT - 1}
    for _ in range(economy.PAT_DAILY_LIMIT - 1):
        actions.pat(s, NOW)
    assert schema.today(s, NOW)["pats"] == economy.PAT_DAILY_LIMIT
    with pytest.raises(ActionError, match="충분히"):
        actions.pat(s, NOW)
    assert actions.pat(s, at(21, 9))["left"] == economy.PAT_DAILY_LIMIT - 1   # resets the next day


def test_pat_caps_mood_and_refuses_runaway():
    s = st(mood=99)
    actions.pat(s, NOW)
    assert s["mood"] == 100
    with pytest.raises(ActionError, match="가출"):
        actions.pat(st(form="runaway"), NOW)


def test_pat_limit_refusal_speaks_like_the_species():
    s = st(species="robot")
    schema.today(s, NOW)["pats"] = economy.PAT_DAILY_LIMIT
    with pytest.raises(ActionError, match="접촉 한도 5/5"):
        actions.pat(s, NOW)
    s["species"], s["form"] = "mole", "thug"           # any form: still the species' words
    with pytest.raises(ActionError, match="굴 들어간다"):
        actions.pat(s, NOW)


def test_gift_treat_lifts_mood_with_a_daily_limit():
    s = st(coins=1000, mood=20)
    r = actions.gift(s, NOW, "pudding")
    assert s["mood"] == 50 and s["coins"] == 840 and r["kind"] == "treat" and r["treats_left"] == 2
    assert schema.today(s, NOW)["spent"] == 160 and schema.today(s, NOW)["purchases"] == 0   # not a shop purchase
    assert s["events"][-1]["type"] == "gift" and s["events"][-1]["gift"] == "pudding"
    actions.gift(s, NOW, "candy")
    actions.gift(s, NOW, "candy")
    with pytest.raises(ActionError, match="배탈"):
        actions.gift(s, NOW, "candy")
    s["mood"] = 10
    assert actions.gift(s, at(21, 9), "candy")["treats_left"] == 2    # a new day


def test_gift_refusals():
    with pytest.raises(ActionError, match="그런 선물"):
        actions.gift(st(), NOW, "pizza")
    with pytest.raises(ActionError, match="모자라"):
        actions.gift(st(coins=10, mood=10), NOW, "cake")
    with pytest.raises(ActionError, match="최고"):
        actions.gift(st(mood=100), NOW, "candy")
    with pytest.raises(ActionError, match="가출"):
        actions.gift(st(form="runaway", mood=10), NOW, "candy")
    with pytest.raises(ActionError, match="애들이나"):
        actions.gift(st(form="thug", mood=10), NOW, "candy")
    assert actions.gift(st(form="thug", mood=10, coins=500), NOW, "ball")["kind"] == "toy"   # toys still work


def test_gift_spender_gets_more_and_misers_grumble():
    s = st(form="spender", mood=10, coins=500)
    actions.gift(s, NOW, "candy")
    assert s["mood"] == 10 + 15 * 1.5
    r = actions.gift(st(form="miser", mood=10, coins=500), NOW, "candy")
    assert "비싼데" in r["line"]


def test_toy_halves_mood_decay_while_playing():
    from petlib import tick
    s = st(coins=500, mood=50, hunger=100)
    actions.gift(s, NOW, "yarn")                       # +10 and 3 hours of half-speed decay
    assert s["mood"] == 60 and s["toy"]["id"] == "yarn"
    tick.decay(s, NOW, at(20, 16))                      # 2 hours, all while playing
    assert s["mood"] == 60 - economy.MOOD_PER_HOUR * 2 * (1 - economy.TOY_DECAY)
    tick.decay(s, at(20, 16), at(20, 19))               # 1 hour of play, then 2 normal
    assert s["mood"] == 58 - economy.MOOD_PER_HOUR * (1 * (1 - economy.TOY_DECAY) + 2)
    assert s["toy"] is None                             # play time over
