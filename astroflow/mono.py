"""Mono-camera targets: WBPP stacks every filter on its own (masterLight_..._FILTER-L_mono.xisf), and the mono recipes
start from those masters. R, G and B make the colour, L (when there is one) the detail (knowledge/videos/
ep3-mono-lrgb-broadband.md). Read from the file names only, so target lists stay cheap.
"""
import re
from pathlib import Path

from . import wbpp

CHANNELS = ("L", "R", "G", "B")
ALIASES = {"l": "L", "lum": "L", "luminance": "L", "clear": "L",
           "r": "R", "red": "R", "g": "G", "green": "G", "b": "B", "blue": "B"}
MONO_MASTER = re.compile(r"_FILTER-(.+?)_mono(?:_autocrop)?\.xisf$", re.I)


def channel(filter_name):
    """A filter's channel: 'Lum', 'Red', 'ZWO B', 'Antlia V-Pro G' ... -> 'L' / 'R' / 'G' / 'B'; None for others (Ha ...)."""
    words = re.findall(r"[a-z]+", str(filter_name or "").lower())
    return ALIASES.get(words[-1]) if words else None


def masters(target_dir, recorded=None):
    """{channel: path} of a mono target's masters: `recorded` (state.json "masters", for masters made elsewhere), else
    WBPP's, the autocropped ones first."""
    if recorded:
        return {c: Path(p) for c, p in recorded.items() if c in CHANNELS and Path(p).exists()}
    out = {}
    for p in wbpp.masters(target_dir):
        m = MONO_MASTER.search(p.name)
        c = channel(m.group(1)) if m else None
        if c and c not in out:
            out[c] = p
    return out


def is_rgb(found):
    """R, G and B are there (L is optional): enough for the mono LRGB recipes."""
    return all(c in found for c in "RGB")
