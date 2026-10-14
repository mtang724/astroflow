"""Shared fixtures: every test runs on its own settings file and a fake credential store (never the user's)."""
from types import SimpleNamespace

import pytest

from astroflow import settings


@pytest.fixture
def tmp_settings(tmp_path, monkeypatch):
    """Settings in tmp_path (job files in tmp_path/runs) and an in-memory credential store; yields (tmp_path, store)."""
    monkeypatch.setenv("ASTROFLOW_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.setattr(settings, "_current", None)
    store = {}
    fake = SimpleNamespace(
        get_password=lambda app, name: store.get(name),
        set_password=lambda app, name, key: store.__setitem__(name, key),
        delete_password=lambda app, name: store.pop(name, None),
        errors=settings.keyring.errors)
    monkeypatch.setattr(settings, "keyring", fake)
    monkeypatch.setattr(settings, "_dotenv", lambda key: None)
    s = settings.get()
    s.runs_dir = (tmp_path / "runs").as_posix()
    s.preferences["language"] = "zh"                  # the messages tests compare are the Chinese ones
    settings.save(s)
    yield tmp_path, store
    monkeypatch.setattr(settings, "_current", None)


@pytest.fixture(autouse=True)
def _own_settings(tmp_settings):
    """Every test runs on its own settings file (Chinese messages), never the user's."""
    yield
