import json
import shutil
from pathlib import Path

from petlib import transcript

FIXTURE = Path(__file__).parent / "fixtures" / "transcript_3lines.jsonl"


def test_three_lines_count_once():
    usages, off, seen = transcript.read_new(str(FIXTURE), 0, [])
    assert [u.message_id for u in usages] == ["msg_A", "msg_B"]
    assert usages[0].output == 447 and usages[0].cache_read == 34219
    assert usages[1].input == 5000
    assert off == FIXTURE.stat().st_size
    assert seen == ["msg_A", "msg_B"]


def test_sidechain_excluded():
    usages, _, _ = transcript.read_new(str(FIXTURE), 0, [])
    assert all(u.message_id != "msg_S" for u in usages)


def test_sidechain_included_for_subagent_files():
    usages, _, _ = transcript.read_new(str(FIXTURE), 0, [], include_sidechain=True)
    assert any(u.message_id == "msg_S" for u in usages)


def test_second_call_from_same_offset_is_empty():
    _, off, seen = transcript.read_new(str(FIXTURE), 0, [])
    usages, off2, seen2 = transcript.read_new(str(FIXTURE), off, seen)
    assert usages == [] and off2 == off and seen2 == seen


def test_seen_ids_dedupe_even_if_offset_rewinds():
    _, _, seen = transcript.read_new(str(FIXTURE), 0, [])
    usages, _, _ = transcript.read_new(str(FIXTURE), 0, seen)
    assert usages == []


def test_partial_last_line_is_deferred(tmp_path):
    p = tmp_path / "t.jsonl"
    shutil.copy(FIXTURE, p)
    full_size = p.stat().st_size
    partial = json.dumps({"type": "assistant", "message": {"id": "msg_C", "usage": {"output_tokens": 7}}})
    with open(p, "a") as f:
        f.write(partial[:40])
    usages, off, seen = transcript.read_new(str(p), 0, [])
    assert [u.message_id for u in usages] == ["msg_A", "msg_B"]
    assert off == full_size
    with open(p, "a") as f:
        f.write(partial[40:] + "\n")
    usages, off2, _ = transcript.read_new(str(p), off, seen)
    assert [u.message_id for u in usages] == ["msg_C"] and usages[0].output == 7
    assert off2 == p.stat().st_size


def test_timestamp_converted_to_local():
    usages, _, _ = transcript.read_new(str(FIXTURE), 0, [])
    assert usages[0].ts.tzinfo is not None
    assert usages[0].ts.utcoffset() == usages[0].ts.astimezone().utcoffset()


def test_seen_limit(tmp_path):
    p = tmp_path / "t.jsonl"
    with open(p, "w") as f:
        for i in range(250):
            f.write(json.dumps({"type": "assistant", "timestamp": "2026-10-20T00:00:00Z",
                                "message": {"id": f"m{i}", "usage": {"output_tokens": 1}}}) + "\n")
    usages, _, seen = transcript.read_new(str(p), 0, [])
    assert len(usages) == 250 and len(seen) == 200 and seen[-1] == "m249"


def test_missing_file():
    assert transcript.read_new("/nonexistent/x.jsonl", 5, ["a"]) == ([], 5, ["a"])
