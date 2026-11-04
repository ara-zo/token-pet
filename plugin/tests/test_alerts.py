import io
import json

from petlib import alerts, cli, store
from conftest import at

SID = "s-1"


def prompt(state, when, cwd="/Users/me/work/token-pet", term=None):
    return alerts.record(state, "prompt", {"session_id": SID, "cwd": cwd}, when, term)


def test_prompt_marks_the_session_working(state):
    a = prompt(state, at(20, 14), term={"app": "Orca", "orca": "term_1"})
    assert a["state"] == "working" and a["name"] == "token-pet"
    assert a["term"] == {"app": "Orca", "orca": "term_1"}


def test_long_turn_ends_done_short_turn_clears(state):
    prompt(state, at(20, 14))
    assert alerts.record(state, "stop", {"session_id": SID}, at(20, 14, 1))["state"] == "done"
    prompt(state, at(20, 15))
    assert alerts.record(state, "stop", {"session_id": SID}, at(20, 15, 0)) is None
    assert SID not in state["alerts"]


def test_permission_prompt_waits_until_the_next_turn(state):
    prompt(state, at(20, 14))
    a = alerts.record(state, "notify", {"session_id": SID, "message": "Claude needs your permission to use Bash"}, at(20, 14, 1))
    assert (a["state"], a["kind"]) == ("waiting", "permission")
    a = alerts.record(state, "notify", {"session_id": SID, "message": "Claude is waiting for your input"}, at(20, 14, 2))
    assert a["kind"] == "input"


def test_idle_reminder_after_a_finished_turn_stays_done(state):
    prompt(state, at(20, 14))
    alerts.record(state, "stop", {"session_id": SID}, at(20, 14, 2))
    a = alerts.record(state, "notify", {"session_id": SID, "message": "Claude is waiting for your input"}, at(20, 14, 3))
    assert a["state"] == "done"


def test_unknown_session_and_end(state):
    assert alerts.record(state, "notify", {"session_id": "other", "message": "x"}, at(20, 14)) is None
    prompt(state, at(20, 14))
    alerts.record(state, "end", {"session_id": SID}, at(20, 14, 5))
    assert state["alerts"] == {}


def test_quiet_sessions_drop_after_half_an_hour(state):
    prompt(state, at(20, 14))
    alerts.record(state, "stop", {"session_id": SID}, at(20, 14, 1))
    alerts.record(state, "prompt", {"session_id": "s-2", "cwd": "/x/docs"}, at(20, 14, 40))
    assert list(state["alerts"]) == ["s-2"]
    alerts.record(state, "prompt", {"session_id": "s-3", "cwd": "/x/api"}, at(20, 18))   # s-2 still working
    assert set(state["alerts"]) == {"s-2", "s-3"}


def test_turned_off_records_nothing(state):
    state["settings"]["alerts"] = False
    assert prompt(state, at(20, 14)) is None and state["alerts"] == {}


def test_seen_clears_done_and_quiets_waiting(state):
    prompt(state, at(20, 14))
    alerts.record(state, "notify", {"session_id": SID, "message": "needs your permission"}, at(20, 14, 1))
    alerts.seen(state, SID)
    assert state["alerts"][SID]["seen"] is True
    alerts.record(state, "stop", {"session_id": SID}, at(20, 14, 2))
    alerts.seen(state, SID)
    assert SID not in state["alerts"]


def test_long_folder_names_are_cut():
    assert alerts.name_of("/a/dk-server-observability") == "dk-server…"
    assert alerts.name_of(None) == "Claude Code"


def test_term_info_from_the_hook_environment():
    env = {"TERM_PROGRAM": "Orca", "__CFBundleIdentifier": "com.stablyai.orca", "ORCA_TERMINAL_HANDLE": "term_9",
           "ORCA_CLI_BIN_DIR": "/Applications/Orca.app/Contents/Resources/bin", "ITERM_SESSION_ID": ""}
    assert alerts.term_info(env, "/dev/ttys003") == {
        "app": "Orca", "bundle": "com.stablyai.orca", "tty": "/dev/ttys003",
        "orca": "term_9", "orca_bin": "/Applications/Orca.app/Contents/Resources/bin/orca"}


def test_open_commands_per_terminal():
    orca = alerts.open_commands({"term": {"bundle": "com.stablyai.orca", "orca": "term_9", "orca_bin": "/o/orca"}})
    assert orca == [["open", "-b", "com.stablyai.orca"], ["/o/orca", "terminal", "switch", "--terminal", "term_9"]]
    iterm = alerts.open_commands({"term": {"app": "iTerm.app", "bundle": "com.googlecode.iterm2", "iterm": "ABC"}})
    assert iterm[1][0] == "osascript" and 'unique id of s is "ABC"' in iterm[1][2]
    term = alerts.open_commands({"term": {"app": "Apple_Terminal", "bundle": "com.apple.Terminal", "tty": "/dev/ttys004"}})
    assert 'tty of t is "/dev/ttys004"' in term[1][2]
    code = alerts.open_commands({"cwd": "/p", "term": {"app": "vscode", "bundle": "com.microsoft.VSCode"}})
    assert code == [["open", "-b", "com.microsoft.VSCode", "/p"]]
    assert alerts.open_commands({"term": {"app": "ghostty", "bundle": "com.mitchellh.ghostty"}}) == [
        ["open", "-b", "com.mitchellh.ghostty"]]


def test_hook_entry_point_writes_state(pet_home, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"session_id": SID, "cwd": "/w/docs"})))
    monkeypatch.setattr(alerts, "_tty", lambda ppid: None)
    assert cli.run(["alert-hook", "prompt"]) == 0
    assert store.load()["alerts"][SID]["state"] == "working"


def test_pet_alert_off_clears(pet_home, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"session_id": SID, "cwd": "/w/docs"})))
    monkeypatch.setattr(alerts, "_tty", lambda ppid: None)
    cli.run(["alert-hook", "prompt"])
    code, text = cli.main_pet(["alert", "off"], store.clock.now())
    assert code == 0 and store.load()["alerts"] == {} and store.load()["settings"]["alerts"] is False
