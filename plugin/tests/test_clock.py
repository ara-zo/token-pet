import datetime as dt

import pytest

from petlib import clock
from conftest import at


@pytest.mark.parametrize("hour,minute,expected", [
    (21, 59, "day"), (22, 0, "night"), (3, 59, "night"),
    (4, 0, "dawn"), (7, 59, "dawn"), (8, 0, "day"), (12, 0, "day"),
])
def test_period(hour, minute, expected):
    assert clock.period(at(20, hour, minute)) == expected


def test_hours_between():
    assert clock.hours_between(at(20, 10), at(20, 13, 30)) == 3.5


def test_parse_fmt_roundtrip():
    now = at(20, 14)
    assert clock.parse(clock.fmt(now)) == now


def test_day_key():
    assert clock.day_key(at(21, 0, 30)) == "2026-10-21"


def test_now_is_aware():
    assert clock.now().tzinfo is not None


def test_midnights_between_splits_days():
    pts = clock.midnights_between(at(20, 23), at(22, 1))
    assert [p.isoformat() for p in pts] == [
        at(21, 0).isoformat(), at(22, 0).isoformat()]


def test_midnights_between_same_day_is_empty():
    assert clock.midnights_between(at(20, 1), at(20, 23)) == []


@pytest.mark.parametrize("word,pair,expected", [
    ("모찌", "이/가", "모찌가"), ("콩", "이/가", "콩이"), ("모찌", "을/를", "모찌를"),
    ("올빼미", "으로/로", "올빼미로"), ("모범생", "으로/로", "모범생으로"), ("Bob", "이/가", "Bob이"),
])
def test_josa(word, pair, expected):
    assert clock.josa(word, pair) == expected
