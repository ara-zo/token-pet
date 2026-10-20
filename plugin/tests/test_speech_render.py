from petlib import speech, render, schema, clock, economy
from conftest import at

NOW = at(20, 14)


def st(**over):
    s = schema.new_state(at(20, 13))
    s.update(over)
    return s


def test_hungry_line_mentions_tokens():
    s = st(hunger=10)
    schema.today(s, NOW)["tokens_out"] = 12400
    assert speech.choose(s, NOW) == "오늘 12.4k 토큰 썼지? 나 배고파…"


def test_recent_event_wins():
    s = st(hunger=10)
    schema.push_event(s, at(20, 13, 55), "evolve", "진화했다!")
    assert speech.choose(s, NOW) == "진화했다!"
    schema.push_event(s, at(20, 13, 56), "feed", "냠냠")        # not a speaking event
    assert speech.choose(s, NOW) == "진화했다!"


def test_old_event_ignored():
    s = st(mood=10)
    schema.push_event(s, at(20, 12), "evolve", "진화했다!")
    assert speech.choose(s, NOW) == "심심해… 나한테 관심 좀 줘"


def test_demand_and_sleep_and_default():
    s = st(form="spender")
    s["flags"]["demand_item"] = "crown"
    assert "왕관" in speech.choose(s, NOW)
    assert speech.choose(st(form="owl"), NOW) == "zzz…"
    assert speech.choose(st(form="owl"), at(20, 23)) == "밤이 제일 좋아…"
    assert speech.choose(st(), NOW) == "오늘도 같이 일하자!"


def test_bars():
    assert render.bars(38) == "▓▓░░░"
    assert render.bars(72) == "▓▓▓▓░"
    assert render.bars(0) == "░░░░░" and render.bars(100) == "▓▓▓▓▓"


CC = {"model": {"display_name": "opus-5.5"}, "workspace": {"current_dir": "/tmp/work/dev-hub"},
      "context_window": {"used_percentage": 41.2}, "cost": {"total_cost_usd": 2.18}}


def test_statusline_structure():
    s = st(name="모찌", level=3, coins=1240, last_turn_earned=12, hunger=38, mood=72)
    line = render.strip_ansi(render.statusline(s, CC, at(20, 13)))
    assert line == "/tmp/work/dev-hub │ opus-5.5 │ 🐣 모찌 Lv.3 🪙1,240 +12 배고픔▓▓░░░ 기분▓▓▓▓░ │ ctx 41% · $2.18"


def test_statusline_applies_virtual_decay_without_writing():
    s = st(hunger=100, mood=100)
    line = render.strip_ansi(render.statusline(s, CC, at(20, 18)))   # 5h later
    hunger = 100 - 5 * economy.HUNGER_PER_HOUR
    assert f"배고픔{render.bars(hunger)}" in line and "기분▓▓▓▓▓" not in line
    assert s["hunger"] == 100


def test_statusline_without_state_and_missing_fields():
    assert render.strip_ansi(render.statusline(None, {"model": {"display_name": "x"}}, NOW)) == "x"
    assert render.strip_ansi(render.statusline(None, {}, NOW)) == ""


def test_statusline_boss_hijack():
    s = st(form="boss")
    s["flags"]["boss_hijack"] = True
    assert "상납" in render.strip_ansi(render.statusline(s, CC, NOW))


def test_status_and_shop_text_smoke():
    s = st(level=5, coins=300, speech="hi", form="miser")
    s["flags"]["debt"] = 5
    s["flags"]["demand_item"] = "plant"
    s["badges"] = ["rehab"]
    txt = render.status_text(s, NOW)
    assert "구두쇠" in txt and "외상 5" in txt and "배지: rehab" in txt and "착용: 파티 모자" in txt
    shop = render.shop_text(s)
    assert f"{economy.price('plant', 'miser')}코인" in shop and "할증" in shop and "crown" in shop
    assert "봉쇄" in render.shop_text(st(form="thug"))
