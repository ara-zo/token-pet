import io
import json
import threading

from petlib import alerts, answer, cli, store
from conftest import at

SID = "s-1"
BASH = {"session_id": SID, "cwd": "/w/token-pet", "tool_name": "Bash", "permission_mode": "default",
        "tool_input": {"command": "cd plugin && python3 -m pytest -q", "description": "테스트 실행"}}
QUESTION = {"session_id": SID, "cwd": "/w/token-pet", "tool_name": "AskUserQuestion", "tool_input": {"questions": [
    {"question": "어느 쪽으로 할까요?", "header": "진행 방식", "multiSelect": False,
     "options": [{"label": "안 A", "description": "세션 제목만"}, {"label": "안 B", "description": "커밋까지"}]}]}}


def test_off_with_alerts_and_on_vacation(state):
    state["settings"]["alerts"] = False
    assert answer.offer(state, BASH, at(20, 14)) is None
    state["settings"]["alerts"] = True
    state["vacation"] = {"until": "2026-10-23T12:00:00+09:00"}
    assert answer.offer(state, BASH, at(20, 14)) is None


def test_permission_prompt_goes_on_the_widget(state):
    ask = answer.offer(state, BASH, at(20, 14))
    entry = state["alerts"][SID]
    assert entry["state"] == "waiting" and entry["kind"] == "permission" and entry["ask"] is ask
    assert ask["command"] == "cd plugin && python3 -m pytest -q" and ask["description"] == "테스트 실행"
    assert ask["mode"] == "default" and not ask.get("terminal")
    assert entry["name"] == "token-pet"           # a session the prompt hook never saw still gets an entry


def test_dangerous_commands_and_previews_stay_in_the_terminal(state):
    state
    for cmd in ("rm -rf build", "git push --force origin main", "git push -f", "git reset --hard HEAD~1",
                "psql -c 'DROP TABLE users'", "sudo rm x"):
        ask = answer.offer(state, dict(BASH, tool_input={"command": cmd}), at(20, 14))
        assert ask["danger"] and ask["terminal"], cmd
    assert not answer.offer(state, dict(BASH, tool_input={"command": "rm build.log"}), at(20, 14)).get("danger")
    multi = json.loads(json.dumps(QUESTION))
    multi["tool_input"]["questions"][0]["multiSelect"] = True
    assert not answer.offer(state, multi, at(20, 14)).get("terminal")   # the widget ticks several
    preview = json.loads(json.dumps(QUESTION))
    preview["tool_input"]["questions"][0]["options"][0]["preview"] = "<b>시안</b>"
    assert answer.offer(state, preview, at(20, 14))["terminal"]


def test_reply_checks_and_decisions(state):
    ask = answer.offer(state, QUESTION, at(20, 14))
    assert answer.reply(state, SID, "nope", {"answers": {}}, at(20, 14)) == "그 질문은 이미 끝났어요"
    assert answer.reply(state, SID, ask["id"], {"answers": {"다른 질문": "x"}}, at(20, 14)) == "모든 질문에 답해야 해요"
    assert answer.reply(state, SID, ask["id"], {"answers": {"어느 쪽으로 할까요?": " 둘 다 "}}, at(20, 14)) is None
    assert ask["reply"] == {"answers": {"어느 쪽으로 할까요?": "둘 다"}}
    out = answer.decision(QUESTION, ask["reply"])["hookSpecificOutput"]
    assert out["hookEventName"] == "PermissionRequest" and out["decision"]["behavior"] == "allow"
    assert out["decision"]["updatedInput"]["answers"] == {"어느 쪽으로 할까요?": "둘 다"}
    assert out["decision"]["updatedInput"]["questions"] == QUESTION["tool_input"]["questions"]
    assert answer.decision(BASH, {"behavior": "deny"})["hookSpecificOutput"]["decision"]["behavior"] == "deny"
    assert answer.decision(BASH, {"behavior": "allow"})["hookSpecificOutput"]["decision"] == {"behavior": "allow"}


def test_danger_cannot_be_allowed_from_the_widget(state):
    ask = answer.offer(state, dict(BASH, tool_input={"command": "rm -rf /tmp/x"}), at(20, 14))
    assert answer.reply(state, SID, ask["id"], {"behavior": "allow"}, at(20, 14)) == "이건 터미널에서 답해야 해요"


def test_last_said_and_title_from_the_transcript(tmp_path):
    t = tmp_path / "t.jsonl"
    rows = [
        {"type": "ai-title", "aiTitle": "펫 일기 구현"},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "일기 모듈 테스트를 새로 썼어요.\n전체를 돌릴게요."}]}},
        {"type": "assistant", "isSidechain": True, "message": {"content": [{"type": "text", "text": "서브에이전트 말"}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
    ]
    t.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    assert answer.last_said(str(t)) == {"said": "일기 모듈 테스트를 새로 썼어요. 전체를 돌릴게요.", "title": "펫 일기 구현"}
    assert answer.last_said(str(tmp_path / "missing")) == {}


def test_stop_and_notify_respect_the_ask(state):
    state
    alerts.record(state, "prompt", {"session_id": SID, "cwd": "/w/token-pet"}, at(20, 14))
    answer.offer(state, QUESTION, at(20, 14))
    alerts.record(state, "notify", {"session_id": SID, "message": "Claude needs your permission"}, at(20, 14))
    assert state["alerts"][SID]["kind"] == "question"          # the late notification doesn't relabel it
    ask_id = state["alerts"][SID]["ask"]["id"]
    assert answer.withdraw(state, SID, ask_id, at(20, 14), working=True)
    assert state["alerts"][SID]["state"] == "working" and "ask" not in state["alerts"][SID]
    alerts.record(state, "notify", {"session_id": SID, "message": "Claude needs your permission"}, at(20, 14))
    assert state["alerts"][SID]["state"] == "working"         # rang just after the widget answered: ignored
    answer.offer(state, BASH, at(20, 14))
    alerts.record(state, "stop", {"session_id": SID}, at(20, 14, 1))
    assert state["alerts"][SID]["state"] == "done" and "ask" not in state["alerts"][SID]


def test_wait_hands_over_the_widget_reply(pet_home, tmp_path):
    with store.transaction(at(20, 14), tick=False) as s:
        ask = answer.offer(s, BASH, at(20, 14))
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("{}\n")
    calls = []

    def sleep(_):
        calls.append(1)
        if len(calls) == 2:                     # the widget answers while the hook polls
            with store.transaction(at(20, 14), tick=False) as s:
                assert answer.reply(s, SID, ask["id"], {"behavior": "allow"}, at(20, 14)) is None

    data = dict(BASH, transcript_path=str(transcript))
    assert answer.wait(SID, ask["id"], data, now=lambda: at(20, 14), sleep=sleep) == {"behavior": "allow"}
    entry = store.load()["alerts"][SID]
    assert entry["state"] == "working" and "ask" not in entry


def test_wait_steps_aside_when_the_terminal_answers(pet_home, tmp_path):
    with store.transaction(at(20, 14), tick=False) as s:
        ask = answer.offer(s, BASH, at(20, 14))
    transcript = tmp_path / "t.jsonl"
    use = lambda i: {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": i, "name": "Bash", "input": BASH["tool_input"]}]}}
    result = lambda i: {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": i}]}}
    transcript.write_text(json.dumps(use("old")) + "\n" + json.dumps(result("old")) + "\n")   # same command, earlier
    steps = [use("new"), {"type": "attachment"}, result("new")]

    def sleep(_):
        if steps:                               # the pending tool_use lands late, then other lines, then its result
            with open(transcript, "a") as f:
                f.write(json.dumps(steps.pop(0)) + "\n")
        if len(steps) == 1:
            assert "ask" in store.load()["alerts"][SID]    # still asking: nothing answered it yet

    data = dict(BASH, transcript_path=str(transcript))
    assert answer.wait(SID, ask["id"], data, now=lambda: at(20, 14), sleep=sleep, limit=5) is None
    assert not steps and "ask" not in store.load()["alerts"][SID]


def test_wait_gives_up_after_the_limit(pet_home):
    with store.transaction(at(20, 14), tick=False) as s:
        ask = answer.offer(s, BASH, at(20, 14))
    assert answer.wait(SID, ask["id"], BASH, now=lambda: at(20, 14), sleep=lambda _: None, limit=0.01) is None
    entry = store.load()["alerts"][SID]
    assert "ask" not in entry and entry["state"] == "waiting"   # the terminal dialog is still up


def test_hook_end_to_end(pet_home, monkeypatch, capsys):
    store.write(store.load())
    monkeypatch.setattr(alerts, "_tty", lambda ppid: None)
    monkeypatch.setattr(alerts, "looking", lambda state, sids: [])
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(QUESTION)))
    monkeypatch.setattr(answer, "POLL", 0.02)
    monkeypatch.setattr(answer, "WAIT", 5)

    def widget():
        for _ in range(200):
            ask = answer.current(store.load(), SID)
            if ask:
                code, text = cli.main_pet(["alert", "answer", SID, ask["id"], "answers",
                                           json.dumps({"어느 쪽으로 할까요?": "안 B"})], at(20, 14))
                assert code == 0, text
                return
            threading.Event().wait(0.01)

    t = threading.Thread(target=widget)
    t.start()
    assert cli.run(["alert-hook", "ask"]) == 0
    t.join()
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["decision"]["updatedInput"]["answers"] == {"어느 쪽으로 할까요?": "안 B"}


def test_hook_stays_quiet_when_off(pet_home, monkeypatch, capsys):
    s = store.load()
    s["settings"]["alerts"] = False
    store.write(s)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(BASH)))
    assert cli.run(["alert-hook", "ask"]) == 0
    assert capsys.readouterr().out == "" and store.load()["alerts"] == {}


def test_send_commands_per_terminal():
    assert alerts.send_commands({"term": {"herdr": "w1:p3", "herdr_bin": "/h"}}, "커밋해") == [
        ["/h", "agent", "prompt", "w1:p3", "커밋해"]]
    assert alerts.send_commands({"term": {"orca": "term_9", "orca_bin": "/o"}}, "커밋해") == [
        ["/o", "terminal", "send", "--terminal", "term_9", "--text", "커밋해", "--enter"]]
    assert alerts.send_commands({"term": {"tmux": "%3"}}, "x")[1] == ["tmux", "send-keys", "-t", "%3", "Enter"]
    script = alerts.send_commands({"term": {"iterm": "ABC", "app": "iTerm.app"}}, 'say "hi"')[0][2]
    assert 'unique id of s is "ABC"' in script and 'write text "say \\"hi\\""' in script
    assert alerts.send_commands({"term": {"app": "Apple_Terminal", "tty": "/dev/ttys1"}}, "x") == []
    assert alerts.can_send({"term": {"orca": "t"}}) and not alerts.can_send({"term": {"app": "vscode"}})


def test_send_only_to_a_finished_session(pet_home, monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "send_text", lambda entry, sid, text: sent.append(text) or True)
    with store.transaction(at(20, 14), tick=False) as s:
        alerts.record(s, "prompt", {"session_id": SID, "cwd": "/w/token-pet"}, at(20, 14), {"orca": "t"})
    code, text = cli.main_pet(["alert", "send", SID, "커밋해"], at(20, 14))
    assert code == 1 and "일하는 중" in text and not sent
    with store.transaction(at(20, 14), tick=False) as s:
        alerts.record(s, "stop", {"session_id": SID, "said": "다 고쳤어요", "title": "작업 알림"}, at(20, 14, 2))
    assert store.load()["alerts"][SID]["said"] == "다 고쳤어요"
    code, text = cli.main_pet(["alert", "send", SID, "커밋하고", "푸시해"], at(20, 14, 3))
    assert code == 0 and sent == ["커밋하고 푸시해"] and store.load()["alerts"][SID]["state"] == "working"


def test_clear_done_and_quick_replies(pet_home):
    with store.transaction(at(20, 14), tick=False) as s:
        for sid in ("a", "b"):
            alerts.record(s, "prompt", {"session_id": sid, "cwd": "/w/x"}, at(20, 14))
        alerts.record(s, "stop", {"session_id": "a"}, at(20, 14, 1))
    code, text = cli.main_pet(["alert", "clear"], at(20, 14, 2))
    assert code == 0 and list(store.load()["alerts"]) == ["b"]
    assert store.load()["settings"]["alert_replies"] == ["커밋해", "계속해", "테스트 돌려"]
    cli.main_pet(["alert", "reply", "푸시해,", "리뷰", "해줘"], at(20, 14))
    assert store.load()["settings"]["alert_replies"] == ["푸시해", "리뷰 해줘"]


def test_sound_on_off(pet_home):
    assert store.load()["settings"]["sound"] is True
    code, text = cli.main_pet(["sound", "off"], at(20, 14))
    assert code == 0 and store.load()["settings"]["sound"] is False
    assert "꺼져" in cli.main_pet(["sound"], at(20, 14))[1]
