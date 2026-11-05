import json

import pytest

from petlib import cli, diary, schema, store, transcript
from conftest import at


def _line(type_, ts="2026-10-20T06:10:00.000Z", **kw):
    return json.dumps({"type": type_, "timestamp": ts, **kw}) + "\n"


def _assistant(mid, out, content=None, ts="2026-10-20T06:10:00.000Z", cwd=""):
    return _line("assistant", ts, cwd=cwd, message={
        "id": mid, "content": content or [{"type": "text", "text": "ok"}],
        "usage": {"input_tokens": 1, "output_tokens": out, "cache_read_input_tokens": 0,
                  "cache_creation_input_tokens": 0}})


def _bash(command):
    return [{"type": "tool_use", "name": "Bash", "input": {"command": command}}]


@pytest.mark.parametrize("command,kinds", [
    ("git add . && git commit -m x", ["commit"]),
    ("git -C /repo commit -m x", ["commit"]),
    ("git commit --amend --no-edit", []),
    ("grep 'git commit' notes.txt", []),
    ("git commit -m \"$(cat <<'EOF'\nfix\npytest in the message\nEOF\n)\"", ["commit"]),
    ("cd plugin && python3 -m pytest -q", ["test"]),
    ("S=/tmp; $S/venv/bin/python -m pytest -q 2>&1 | tail -3", ["test"]),
    ("npm test", ["test"]), ("pnpm run test", ["test"]), ("FOO=1 npx vitest run", ["test"]),
    ("cargo test", ["test"]), ("cargo build", []), ("go test ./...", ["test"]),
    ("./gradlew :app:test", ["test"]), ("./gradlew build", []), ("mvn -q test", ["test"]),
    ("gh pr create --fill", ["pr"]), ("gh pr view 3", []),
    ("pytest -q; git commit -am x && gh pr create --fill", ["test", "commit", "pr"]),
])
def test_command_acts(command, kinds):
    assert transcript.command_acts(command) == kinds


def test_read_new_collects_title_cwd_and_commands_on_every_line(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text(
        _line("ai-title", aiTitle="첫 제목")
        + _assistant("m1", 10, cwd="/w/a")
        # same response, later line: usage is deduped but its tool_use still counts
        + _assistant("m1", 10, _bash("git commit -m x"), cwd="/w/a")
        + _assistant("m2", 20, _bash("pytest"), cwd="/w/a")
        + _line("ai-title", aiTitle="바뀐 제목"))
    meta = {}
    usages, _, _ = transcript.read_new(str(f), 0, [], meta=meta)
    assert [u.output for u in usages] == [10, 20] and usages[0].cwd == "/w/a"
    assert meta["title"] == "바뀐 제목"
    assert [a.kind for a in meta["acts"]] == ["commit", "test"] and meta["acts"][0].cwd == "/w/a"
    assert transcript.read_new(str(f), 0, [])[0] == usages          # meta stays optional


def test_repo_name_walks_up_to_the_work_tree(tmp_path):
    repo = tmp_path / "token-pet"
    (repo / ".git").mkdir(parents=True)
    (repo / "plugin" / "scripts").mkdir(parents=True)
    assert diary.repo_name(str(repo / "plugin" / "scripts")) == "token-pet"
    wt = tmp_path / "wt-feature"
    wt.mkdir()
    (wt / ".git").write_text("gitdir: /elsewhere\n")              # a worktree: .git is a file
    assert diary.repo_name(str(wt)) == "wt-feature"
    assert diary.repo_name(str(tmp_path / "plain")) == "plain"
    assert diary.repo_name("") == ""


def test_collect_files_hours_repos_titles_and_counts(pet_home, tmp_path):
    repo = tmp_path / "token-pet"
    (repo / ".git").mkdir(parents=True)
    other = tmp_path / "notes"
    other.mkdir()
    f = tmp_path / "s1.jsonl"
    f.write_text(
        _line("ai-title", aiTitle="펫 일기 만들기")
        # 06:10Z = 15:10 KST
        + _assistant("m1", 400, _bash("python3 -m pytest -q && git commit -m a"), cwd=str(repo / "plugin"))
        + _assistant("m2", 100, ts="2026-10-20T07:05:00.000Z", cwd=str(other)))
    hook = {"session_id": "sess-0001-abc", "transcript_path": str(f), "cwd": str(repo)}
    cli.main_collect(hook, at(20, 16))
    day = store.load()["daily_log"][-1]
    assert day["hours_out"][15] == 400 and day["hours_out"][16] == 100 and sum(day["hours_out"]) == 500
    r = day["repos"]["token-pet"]
    assert r["out"] == 400 and r["commits"] == 1 and r["tests"] == 1 and r["prs"] == 0
    assert r["sessions"] == ["sess-000"] and r["titles"] == {"sess-000": "펫 일기 만들기"}
    assert day["repos"]["notes"]["out"] == 100

    with open(f, "a") as fh:                                      # nothing new but a reworded title
        fh.write(_line("ai-title", aiTitle="펫 일기 · 작업한 곳"))
    cli.main_collect(hook, at(20, 17))
    day = store.load()["daily_log"][-1]
    assert day["repos"]["token-pet"]["titles"] == {"sess-000": "펫 일기 · 작업한 곳"}
    assert day["repos"]["token-pet"]["out"] == 400 and day["repos"]["token-pet"]["commits"] == 1


def test_old_days_get_the_new_fields(fixed_now):
    s = schema.new_state(fixed_now)
    for k in ("hours_out", "repos"):
        del s["daily_log"][0][k]
    s = schema.migrate(s)
    assert s["daily_log"][0]["hours_out"] == [0] * 24 and s["daily_log"][0]["repos"] == {}


def _day(date, out=0, hours=None, repos=None, **kw):
    d = schema.new_day(date)
    d["tokens_out"] = out
    if hours:
        for h, v in hours.items():
            d["hours_out"][h] = v
    d["repos"] = repos or {}
    d.update(kw)
    return d


def _repo(out, sessions=("a",), titles=None, **counts):
    return {"out": out, "sessions": list(sessions), "titles": titles or {}, "commits": 0, "tests": 0, "prs": 0, **counts}


@pytest.fixture
def week_state(state):
    # week of Mon 10/19 .. Sun 10/25; the week before has 1,000,000 output on Wed 10/14
    state["daily_log"] = [
        _day("2026-10-14", 1_000_000),
        _day("2026-10-19", 120_000, {10: 20_000, 15: 100_000}, night_out=0,
             repos={"token-pet": _repo(90_000, titles={"a": "선물 페이지"}, commits=2, tests=3),
                    "dk-jarvis": _repo(30_000, ("b",), {"b": "큐 정리"}, prs=1)}),
        _day("2026-10-20", 400_000, {15: 152_000, 23: 8_000}, night_out=8_000,
             repos={"token-pet": _repo(400_000, ("a", "c"), {"a": "선물 페이지", "c": "일기"}, commits=1)}),
    ]
    return state


def test_payload_this_week(week_state):
    p = diary.payload(week_state, at(20, 18))                     # Tuesday
    assert p["start"] == "2026-10-19" and p["end"] == "2026-10-25" and p["label"] == "10월 셋째 주"
    assert [d["weekday"] for d in p["days"]] == ["월", "화", "수", "목", "금", "토", "일"]
    assert p["days"][1]["today"] and p["days"][2]["future"] and not p["days"][0]["future"]
    assert p["peak"] == {"weekday": "화", "hour": 15, "out": 152_000, "date": "2026-10-20"}
    assert p["tired"] == 1                                       # only 152k is past the 100k rush line
    assert p["good"] == 1                                        # Monday's 120k; today isn't over yet
    assert p["night_days"] == 1 and p["change"] == -48           # 520k vs 1,000,000
    assert [s["id"] for s in p["stamps"]] == ["tired", "good", "night"]
    top = p["repos"][0]
    assert top["name"] == "token-pet" and top["out"] == 490_000 and top["share"] == 94
    assert top["sessions"] == 2 and top["titles"] == ["선물 페이지", "일기"]
    assert p["counts"] == {"commits": 3, "tests": 3, "prs": 1}
    assert [s["label"] for s in p["work_stamps"]] == ["한 우물 94%", "테스트 3번", "PR 1 · 커밋 3"]
    assert p["lines"]["time"][0] == "화요일 오후 3시에 공장이 제일 빨랐다. 15만 조각! 땀이 났다."
    assert p["lines"]["work"] == ["token-pet 공장에 제일 오래 있었다!", "커밋 3번, 테스트 3번, PR 1개!"]


def test_payload_last_week_from_monday_and_sunday(week_state):
    for now in (at(26, 9), at(31, 23)):                           # Monday and Saturday of the next week
        p = diary.payload(week_state, now, "last")
        assert p["start"] == "2026-10-19" and not any(d["future"] for d in p["days"])
    sunday = diary.payload(week_state, at(25, 23))                # Sunday still belongs to its week
    assert sunday["start"] == "2026-10-19"


def test_payload_empty_week_and_species_voice(state):
    state["species"] = "robot"
    p = diary.payload(state, at(20, 9))
    assert p["peak"] is None and p["repos"] == [] and p["lines"]["time"] == ["주간 보고서. 가동 없음. 대기 모드 유지."]
    assert "조용" in diary.text(schema.new_state(at(20, 9)), at(20, 9))


def test_extra_repos_are_summed_into_other(state):
    repos = {f"r{i}": _repo(1000 * (10 - i), (f"s{i}",)) for i in range(7)}
    state["daily_log"] = [_day("2026-10-20", 49_000, {9: 49_000}, repos=repos)]
    p = diary.payload(state, at(20, 18))
    assert [r["name"] for r in p["repos"]] == ["r0", "r1", "r2", "r3", "기타"]
    assert p["repos"][-1]["other"] == 3 and p["repos"][-1]["out"] == 6000 + 5000 + 4000
    assert p["work_stamps"][0]["label"] == "레포 7곳"


def test_text_and_widget_payload(pet_home, week_state):
    store.write(week_state)
    code, txt = cli.main_pet(["diary"], at(20, 18))
    assert code == 0 and "📔 모찌의 일기 · 10월 셋째 주 (10/19~10/25) · 쓰는 중" in txt
    assert "가장 바빴던 시간: 화요일 15시 (출력 15만)" in txt
    assert "📂 이번 주 작업한 곳" in txt and "  · 선물 페이지" in txt and "  커밋 3 · 테스트 3" in txt
    assert "도장: 지친 시간 1 · 좋은 날 1 · 밤 작업 1" in txt
    code, js = cli.main_pet(["diary", "last", "--json"], at(26, 9))
    res = json.loads(js)["result"]
    assert res["which"] == "last" and res["repos"][0]["name"] == "token-pet"
    assert all("titles" not in r for r in res["repos"])          # titles stay in the terminal
    assert cli.main_pet(["diary", "nope"], at(20, 18))[0] == 2
