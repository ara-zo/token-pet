from petlib import speech, speech_lines, render, schema, clock, economy
from conftest import at

NOW = at(20, 14)


def st(**over):
    s = schema.new_state(at(20, 13))
    s.update(over)
    return s


def test_hungry_line_mentions_tokens():
    s = st(hunger=10)
    schema.today(s, NOW)["tokens_out"] = 12400
    said = {speech.choose(s, at(20, h)) for h in range(9, 21)}
    assert "오늘 12.4k 토큰 썼지? 나 배고파…" in said
    assert all("{" not in line for line in said)
    # nothing used today: the token line is skipped instead of saying "0 토큰"
    s2 = st(hunger=10)
    assert all("토큰" not in speech.choose(s2, at(20, h)) for h in range(9, 21))


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
    assert speech.choose(st(form="owl"), at(20, 23)) == "지금이야! 조각이 두 배로 떨어져"
    assert speech.choose(st(), NOW) in speech_lines.LINES["base"]["IDLE"]


def test_situation_lines_by_form_with_fallback():
    assert speech.choose(st(form="miser"), NOW, "FEED") == "50코인… 50코인… 맛있긴 하네"
    assert speech.choose(st(form="scholar"), NOW, "EARN", n=12) == "+12. 캐시 적중률 좋았어"
    assert speech.choose(st(form="thug"), NOW, "BUY", item="화분") == "화분! 고마워!"     # base fallback
    assert speech.choose(st(), NOW, "EARN") in speech_lines.LINES["base"]["IDLE"]     # {n} missing → mood line


def test_every_form_has_idle_and_lines_format():
    for form in economy.FORMS:
        assert speech_lines.lines(form, "IDLE"), form
        for sit, opts in speech_lines.LINES.get(form, {}).items():
            for line in opts:
                line.format(n=1, out="1k", item="모자")


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


def test_species_line_wins_for_its_form():
    assert speech.choose(st(species="mole"), NOW) == "…캤다."
    assert speech.choose(st(species="squirrel", form="thug"), NOW) == "냐핫! 10% 잡았다! 튄다!! 우다닥닥"
    assert speech.choose(st(species="robot", mood=72), NOW) == "보고: 공장 가동 중. 기분 72%. 이상 없음."
    assert speech.choose(st(species="robot", hunger=18), NOW) == "경고: 화로 연료 18%. 급식 요청 미처리."


def test_species_tic_dresses_form_lines():
    assert speech.choose(st(species="mole", form="miser"), NOW, "FEED") == "…50코인."
    assert speech.choose(st(species="robot", form="scholar"), NOW, "EARN", n=12) == "보고: +12. 캐시 적중률 좋았어."
    sp = lambda species: speech.choose(st(species=species, form="spender"), NOW, "PAT")
    assert sp("hamster") == "근데근데 머리 망가져! …그래도 좋아"
    assert sp("penguin") == "머리 망가져! …그래도 좋아…"
    assert sp("rabbit") == "신호 왔어. 머리 망가져! …그래도 좋아"
    assert sp("squirrel").endswith("!! 머리 망가져! …그래도 좋아!!")
    assert sp("mochi") == "머리 망가져! …그래도 좋아"
    assert speech.choose(st(species="hamster", form="runaway"), NOW, "PAT") == "(빈 쿠션만 만져진다)"


def test_strong_forms_keep_their_tone():
    for sp in ("squirrel", "mole", "robot", "penguin", "hamster", "rabbit"):
        assert speech_lines.lines("boss", "IDLE", sp) == speech_lines.LINES["boss"]["IDLE"]
        assert speech_lines.lines("runaway", "IDLE", sp) == speech_lines.LINES["runaway"]["IDLE"]


def test_every_species_line_formats():
    from petlib import species
    assert set(speech_lines.SPECIES_LINES) == set(species.SPECIES) == set(speech_lines.PAT_LIMIT)
    for by_form in speech_lines.SPECIES_LINES.values():
        for form, sits in by_form.items():
            assert form in economy.FORMS
            for opts in sits.values():
                for line in opts:
                    line.format(n=1, out="1k", item="모자", mood=50, fuel=10)


def test_species_feed_and_pat_lines_in_base_form():
    for key in speech_lines.SPECIES_LINES:
        base = speech_lines.SPECIES_LINES[key]["base"]
        assert len(base["FEED"]) == 2 and len(base["PAT"]) == 2, key
    assert speech.choose(st(species="robot", hunger=64), NOW, "FEED") in (
        "보고: 화로 연료 64%. 충전 완료.", "보고: 급식 수령 확인. 굴뚝 연기 정상.")
    assert speech.choose(st(species="mole"), NOW, "PAT") in ("…안전모는 벗기지 마라.", "…따뜻하다. 조금 더.")
