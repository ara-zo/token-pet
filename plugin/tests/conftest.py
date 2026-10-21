import datetime as dt

import pytest

from petlib import schema

KST = dt.timezone(dt.timedelta(hours=9))


@pytest.fixture
def fixed_now():
    return dt.datetime(2026, 10, 20, 14, 0, tzinfo=KST)


@pytest.fixture
def pet_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PET_HOME", str(tmp_path))
    monkeypatch.setenv("TOKEN_PET_NO_WIDGET", "1")
    return tmp_path


@pytest.fixture
def state(fixed_now):
    return schema.new_state(fixed_now)


def at(day, hour, minute=0):
    """2026-10-{day} {hour}:{minute} KST"""
    return dt.datetime(2026, 10, day, hour, minute, tzinfo=KST)
