"""Mono-camera targets: WBPP stacks every filter on its own (masterLight_..._FILTER-L_mono.xisf), and the mono recipes
start from those masters. R, G and B make the colour, L (when there is one) the detail (knowledge/videos/
ep3-mono-lrgb-broadband.md). Read from the file names only, so target lists stay cheap.
"""
import re
from pathlib import Path

from . import wbpp

CHANNELS = ("L", "R", "G", "B", "H", "O", "S")       # broadband, and the narrowband lines Ha, OIII, SII
ALIASES = {"l": "L", "lum": "L", "luminance": "L", "clear": "L",
           "r": "R", "red": "R", "g": "G", "green": "G", "b": "B", "blue": "B",
           "h": "H", "ha": "H", "halpha": "H", "o": "O", "oiii": "O", "o3": "O",
           "s": "S", "sii": "S", "s2": "S"}
MONO_MASTER = re.compile(r"_FILTER-(.+?)_mono(?:_[^.]+)?\.xisf$", re.I)      # then grouping keywords, _autocrop


def channel(filter_name):
    """A filter's channel: 'Lum', 'Red', 'ZWO B', 'Antlia V-Pro G' -> 'L' / 'R' / 'G' / 'B'; 'Ha 7nm', 'H-alpha',
    'OIII', 'Antlia SII 3nm' -> 'H' / 'O' / 'S'; None for others."""
    text = str(filter_name or "").lower().replace("-alpha", "alpha").replace("α", "alpha")
    words = [w for w in re.findall(r"[a-z]+[0-9]?|[0-9]+", text) if not re.fullmatch(r"[0-9]+(nm)?|nm", w)]
    for w in reversed(words):                      # the line or colour is usually last: 'Antlia V-Pro R', 'SII 3nm'
        if w in ALIASES:
            return ALIASES[w]
    return None


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
