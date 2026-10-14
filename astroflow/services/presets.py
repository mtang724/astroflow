"""The user's own styles: a target's parameter edits saved under a name, to give other targets processed with the same
recipe the same look. Stored next to the settings file (presets.json):

    {"<name>": {"recipe": "osc_galaxy", "params": {stage: {step_id: override}}, "source": "M101", "saved": "..."}}

Applying a preset replaces the target's own edits (services.recipes keeps them in Post/params.json); the recipe's
defaults stay underneath, so a preset made with an older version still applies what it changed.
"""
import json
import threading
from datetime import datetime
from pathlib import Path

from .. import jsonfile, settings
from . import recipes

_lock = threading.Lock()


def _path():
    return Path(settings.settings_path()).parent / "presets.json"


def _load():
    p = _path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _edits(params):
    return sum(len({k for k in step if k != "params"}) + len(step.get("params") or {})
               for stage in params.values() for step in stage.values())


def list_presets(recipe=None):
    """[{name, recipe, source, saved, edits}], newest first; only those for `recipe` when given."""
    out = [{"name": name, "recipe": p["recipe"], "source": p.get("source"), "saved": p.get("saved"),
            "edits": _edits(p.get("params") or {})} for name, p in _load().items()]
    return sorted((p for p in out if recipe is None or p["recipe"] == recipe), key=lambda p: p["saved"] or "",
                  reverse=True)


def save(name, target_dir, recipe):
    """Save the target's current edits as preset `name` (replacing one of that name)."""
    name = name.strip()
    if not name:
        raise ValueError("a preset needs a name")
    params = recipes.overrides(target_dir)
    if not params:
        raise ValueError("this target has no edited parameters to save")
    with _lock:
        data = _load()
        data[name] = {"recipe": recipe, "params": params, "source": Path(target_dir).name,
                      "saved": datetime.now().isoformat(timespec="seconds")}
        jsonfile.write(_path(), data)
    return next(p for p in list_presets() if p["name"] == name)


def apply(name, target_dir, recipe):
    """Give the target the preset's edits (they replace its own)."""
    preset = _load().get(name)
    if preset is None:
        raise KeyError(f"no preset named {name}")
    if preset["recipe"] != recipe:
        raise ValueError(f"preset {name} is for the {preset['recipe']} recipe, this target uses {recipe}")
    recipes.replace(target_dir, preset["params"])


def delete(name):
    with _lock:
        data = _load()
        if data.pop(name, None) is not None:
            jsonfile.write(_path(), data)
