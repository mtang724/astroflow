"""Editable recipe parameters and the user's per-target overrides.

A recipe (pipeline.RECIPES) is a list of stages, each a list of steps such as
    {"id": "sat", "op": "saturation", "boost": 0.72, "mask": "lum", "passes": 2}
    {"id": "nxt", "op": "nxt", "params": {"denoise": 0.30, "denoise_color": 0.40}}
Scalar values are the tunable parameters; `params.<key>` are those passed straight to the PixInsight process.
The user's edits are stored in <target>/Post/params.json ({stage: {step_id: {key: value, "params": {...}}}}); every
run applies them (pipeline.saved_overrides). Only this module writes that file: the pipeline keeps its own state.json,
which a running job rewrites while the user may be editing.
"""
import threading

from .. import jsonfile, pipeline

NOT_TUNABLE = {"id", "op", "optional", "path", "saveModel", "size"}
_lock = threading.Lock()                 # API requests run in a thread pool: one read-modify-write at a time


def _kind(v):
    return "bool" if isinstance(v, bool) else "int" if isinstance(v, int) else "float" if isinstance(v, float) else "str"


def step_fields(step):
    """Tunable scalar fields of a step: [{key, value, type}] with 'params.x' for process parameters."""
    out = []
    for k, v in step.items():
        if k in NOT_TUNABLE:
            continue
        if k == "params" and isinstance(v, dict):
            out += [{"key": f"params.{pk}", "value": pv, "type": _kind(pv)} for pk, pv in v.items()
                    if isinstance(pv, (bool, int, float, str))]
        elif isinstance(v, (bool, int, float, str)):
            out.append({"key": k, "value": v, "type": _kind(v)})
    return out


def spec(recipe):
    """The recipe as stages -> steps -> tunable fields (defaults)."""
    return [{"stage": s["stage"], "steps": [{"id": st["id"], "op": st["op"], "optional": bool(st.get("optional")),
                                              "fields": step_fields(st)} for st in s["steps"]]}
            for s in pipeline.RECIPES[recipe]]


def overrides(target_dir):
    return pipeline.saved_overrides(target_dir)


def set_field(target_dir, stage, step_id, key, value):
    """Remember one edited value (key 'boost' or 'params.denoise'); value None removes the edit."""
    with _lock:
        ov = overrides(target_dir)
        step = ov.setdefault(stage, {}).setdefault(step_id, {})
        if key.startswith("params."):
            params = step.setdefault("params", {})
            if value is None:
                params.pop(key[7:], None)
            else:
                params[key[7:]] = value
            if not params:
                step.pop("params")
        elif value is None:
            step.pop(key, None)
        else:
            step[key] = value
        _prune(ov)
        jsonfile.write(pipeline.params_path(target_dir), ov)


def reset(target_dir, stage=None):
    with _lock:
        ov = overrides(target_dir)
        if stage:
            ov.pop(stage, None)
        else:
            ov = {}
        jsonfile.write(pipeline.params_path(target_dir), ov)


def effective(recipe, target_dir):
    """spec() with the user's values filled in and marked (for the parameter panel)."""
    ov = overrides(target_dir)
    out = spec(recipe)
    for stage in out:
        for step in stage["steps"]:
            mine = ov.get(stage["stage"], {}).get(step["id"], {})
            for f in step["fields"]:
                if f["key"].startswith("params."):
                    user = mine.get("params", {}).get(f["key"][7:])
                else:
                    user = mine.get(f["key"])
                f["default"], f["edited"] = f["value"], user is not None
                if user is not None:
                    f["value"] = user
    return out


def _prune(ov):
    for stage in list(ov):
        for sid in list(ov[stage]):
            if not ov[stage][sid]:
                del ov[stage][sid]
        if not ov[stage]:
            del ov[stage]
