import json

import pytest

from petlib import cli, clock, schema, store, tick, vacation
from petlib.actions import ActionError
from conftest import at

NOW = at(24, 14)


def st(**over):
    s = schema.new_state(at(24, 13))
    s.update(coins=1240, hunger=62, mood=70, last_tick_at=clock.fmt(NOW), last_fed_at=clock.fmt(at(24, 12)))
    s.update(over)
    return s


def test_start_charges_and_freezes_time():
    s = st()
    r = vacation.start(s, NOW, "3")
    assert r["fee"] == 60 and s["coins"] == 1180
    assert s["vacation"]["until"] == clock.fmt(at(27, 14))
    assert vacation.used_this_month(s, NOW) == 3
    assert s["events"][-1]["type"] == "vacation_leave"
    tick.apply(s, at(26, 9))                       # two nights later: nothing moved
    assert (s["hunger"], s["mood"]) == (62, 70)
    assert s["since_form"]["days"] == 0
    assert vacation.d_label(s, at(26, 9)) == "D-1" and vacation.d_label(s, at(27, 9)) == "D-DAY"


def test_back_by_itself_after_the_stay():
    s = st()
    vacation.start(s, NOW, "3")
    tick.apply(s, at(27, 15))                      # an hour past checkout
    assert s["vacation"] is None
    assert s["mood"] == pytest.approx(80 - 2 * 1, abs=0.01)    # +10 on return, then an hour of normal decay
    assert s["last_fed_at"] == clock.fmt(at(27, 12))           # the meal moved by the 3-day stay
    assert any(e["type"] == "vacation_back" for e in s["events"])


def test_early_return_refunds_whole_days_left():
    s = st()
    vacation.start(s, NOW, "3")
    r = vacation.finish(s, at(25, 10), early=True)             # 52h left → 2 whole days back
    assert (r["unused"], r["refund"]) == (2, 40) and s["coins"] == 1220
    assert vacation.used_this_month(s, at(25, 10)) == 1
    assert s["events"][-1]["type"] == "vacation_early"


@pytest.mark.parametrize("form,arg,msg", [
    ("thug", "3", "불량배"), ("boss", "3", "조직 보스"), ("runaway", "3", "가출"),
    ("base", "30", "1~14일"), ("base", "0", "1~14일"), ("base", "x", "1~14일"),
])
def test_refusals(form, arg, msg):
    with pytest.raises(vacation.VacationError, match=msg):
        vacation.start(st(form=form), NOW, arg)


def test_money_and_month_limits():
    with pytest.raises(vacation.VacationError, match="숙박비 100코인"):
        vacation.start(st(coins=40), NOW, "5")
    s = st()
    s["settings"]["vacation_days"] = {"2026-10": 16}
    with pytest.raises(vacation.VacationError, match="남은 날: 4일"):
        vacation.start(s, NOW, "7")
    vacation.start(s, NOW, "4")
    with pytest.raises(vacation.VacationError, match="이미 휴가 중"):
        vacation.start(s, NOW, "1")


def test_pet_commands_wait_for_the_pet(pet_home):
    with store.transaction(NOW, tick=False) as s:
        s.update(coins=1240)
    code, text = cli.main_pet(["vacation", "3"], NOW)
    assert code == 0 and "토키 호텔에 맡겼어요" in text and "10/27(화) 14:00" in text
    for argv in (["feed"], ["pat"], ["equip", "party_hat"], ["switch", "mochi"]):
        code, text = cli.main_pet(argv, at(25, 9))
        assert code == 2 and "토키 호텔에 묵고 있어요" in text, argv
    code, text = cli.main_pet(["vacation"], at(25, 9))
    assert "휴가 중 · D-2" in text
    code, text = cli.main_pet(["vacation", "end", "--json"], at(25, 9))
    r = json.loads(text)
    assert r["ok"] and r["state"]["vacation"] is None and "+40코인" in r["text"]


def test_no_coins_while_away(pet_home, tmp_path):
    with store.transaction(NOW, tick=False) as s:
        s.update(coins=1240)
        vacation.start(s, NOW, "2")
    tr = tmp_path / "t.jsonl"
    tr.write_text(json.dumps({"type": "assistant", "timestamp": "2026-10-24T05:30:00Z", "message": {
        "id": "m1", "usage": {"input_tokens": 10, "output_tokens": 50000}}}) + "\n")
    earned = cli.main_collect({"session_id": "s", "transcript_path": str(tr)}, at(24, 15))
    s = store.load(at(24, 15))
    assert earned == 0 and s["coins"] == 1200
    assert schema.today(s, at(24, 15))["tokens_out"] == 50000      # still on the record


def test_statusline_shows_the_hotel():
    from petlib import render
    s = st()
    vacation.start(s, NOW, "3")
    line = render.statusline(s, {}, at(25, 9))
    assert "휴가 중" in line and "D-2" in line and "10/27 복귀" in line


def test_hotels_buy_choose_and_notes():
    from petlib import actions, economy
    s = st(coins=5000, species="penguin")
    assert s["equipped"]["hotel"] == "toki_hotel"
    actions.buy(s, NOW, "space_hotel")
    with pytest.raises(ActionError, match="재벌만"):
        actions.buy(s, NOW, "golden_hotel")
    s["form"] = "tycoon"
    actions.buy(s, NOW, "golden_hotel")
    s["form"] = "base"
    vacation.start(s, NOW, "2")
    actions.equip(s, "space_hotel")                 # can move hotels while away
    assert vacation.line(s, "away") == "(우주 호텔 창으로 진짜 별을 보고 있다)"
    with pytest.raises(ActionError, match="호텔에 묵고"):
        actions.equip(s, "party_hat")
    with pytest.raises(ActionError, match="하나는 있어야"):
        actions.unequip(s, "hotel")
    m = st(species="mochi")
    m["equipped"]["hotel"] = "snow_lodge"
    m["items_owned"].append("snow_lodge")
    assert vacation.line(m, "away") == "(눈 산장 202호에서 꿀잠 중…)"
    assert economy.bought_count(st()) == 1          # the starter hat as before; the free hotel adds nothing
