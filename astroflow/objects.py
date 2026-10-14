"""Catalogue lookup (PixInsight's AdP Messier/NGC-IC tables) and the target type -> recipe decision.

Types the table does not know come back as "unknown"; the agent asks the LLM to classify them instead of
guessing in code.
"""
import csv
import re
from functools import lru_cache
from pathlib import Path

from . import config

# Types of common targets. Anything else: the agent decides (LLM) and may record it in knowledge/targets.
KNOWN_TYPES = {
    "M8": "emission_nebula", "M16": "emission_nebula", "M17": "emission_nebula", "M20": "emission_nebula",
    "M42": "emission_nebula", "M43": "emission_nebula", "M1": "supernova_remnant", "M27": "planetary_nebula",
    "M57": "planetary_nebula", "M97": "planetary_nebula", "M76": "planetary_nebula",
    "NGC6334": "emission_nebula", "NGC6357": "emission_nebula", "IC1805": "emission_nebula",
    "IC1848": "emission_nebula", "IC434": "emission_nebula", "NGC2237": "emission_nebula", "NGC7000": "emission_nebula",
    "IC1396": "emission_nebula", "NGC6960": "supernova_remnant", "NGC6992": "supernova_remnant",
    "NGC246": "planetary_nebula", "NGC7293": "planetary_nebula", "NGC6543": "planetary_nebula",
    "NGC7023": "reflection_nebula", "M45": "reflection_nebula", "M78": "reflection_nebula",
    "M31": "galaxy", "M33": "galaxy", "M51": "galaxy", "M63": "galaxy", "M64": "galaxy", "M74": "galaxy",
    "M81": "galaxy", "M82": "galaxy", "M83": "galaxy", "M101": "galaxy", "M104": "galaxy", "M106": "galaxy",
    "NGC891": "galaxy", "NGC253": "galaxy", "NGC2403": "galaxy", "NGC4565": "galaxy", "NGC5457": "galaxy",
    "M13": "globular_cluster", "M3": "globular_cluster", "M92": "globular_cluster", "M44": "open_cluster",
}

RECIPE_FOR_TYPE = {
    "galaxy": "osc_galaxy",
    "emission_nebula": "osc_broadband_nebula", "reflection_nebula": "osc_broadband_nebula",
    "planetary_nebula": "osc_broadband_nebula", "supernova_remnant": "osc_broadband_nebula",
    "dark_nebula": "osc_broadband_nebula",
    "comet": "comet",
}

COMET_NAME = re.compile(r"^(?:[CP][/-]?\s*\d{4}[\s_-]*[A-Z]{1,2}\d*|\d+P\b|COMET\b)", re.I)   # C/2025 R3, C2025-R3, 12P/...


def norm(name):
    """'M 101' -> 'M101', 'NGC 6334' -> 'NGC6334', 'IC 1805' -> 'IC1805', 'C-2025 R3' -> unchanged-ish."""
    n = re.sub(r"\s+", "", str(name)).upper()
    n = re.sub(r"^MESSIER", "M", n)
    return n


def _catalog():
    return _load_catalog(str(config.PI_SCRIPTS))     # keyed by the folder: a path fixed in Settings applies at once


@lru_cache(maxsize=4)
def _load_catalog(scripts_dir):
    rows = {}
    for fname, key_extra in (("Messier.csv", "NGC/IC"), ("NGC-IC.csv", "Messier")):
        path = Path(scripts_dir) / "AdP" / fname
        if not path.exists():
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            for r in csv.DictReader(f):
                rid = norm(r["id"])
                rows.setdefault(rid, r)
                alt = r.get(key_extra) or ""
                if alt:
                    rows.setdefault(norm(alt), r)
    return rows


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def lookup(name):
    r = _catalog().get(norm(name))
    if not r:
        return None
    return {"id": r["id"], "ra": _f(r["alpha"]), "dec": _f(r["delta"]), "magnitude": _f(r.get("magnitude")),
            "diameter": _f(r.get("diameter")), "axisRatio": _f(r.get("axisRatio")) or 1.0,
            "posAngle": _f(r.get("posAngle")) or 0.0, "common_name": r.get("Common name") or None}


def object_type(name):
    if COMET_NAME.match(str(name).strip()):
        return "comet"
    return KNOWN_TYPES.get(norm(name), "unknown")


NEBULA_TYPES = {"emission_nebula", "reflection_nebula", "planetary_nebula", "supernova_remnant", "dark_nebula"}


def recipe_for(name, type_hint=None, filter_class=None):
    """Recipe from object type and the night's filter (session.json filter_class: osc_broadband | osc_multiband)."""
    t = type_hint or object_type(name)
    if filter_class == "osc_multiband" and t in NEBULA_TYPES:
        return "osc_multiband_nebula", t
    return RECIPE_FOR_TYPE.get(t), t


def session_path(target_dir):
    """Where the filter of a target's night is recorded: In Processing/<night>/session.json, or the target's own
    session.json (a multi-night target, astroflow.multinight)."""
    from pathlib import Path
    own = Path(target_dir) / "session.json"
    return own if own.exists() or (Path(target_dir) / "combined.json").exists() else Path(target_dir).parent / "session.json"


def session_info(target_dir):
    """The night's session.json (filter used that night etc.), {} when absent."""
    import json
    p = session_path(target_dir)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
