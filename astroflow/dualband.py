"""Colour cameras with dual-band filters: Ha + OIII (the night's filter_class osc_multiband) and SII + OIII (osc_so).
Their frames do not say which filter was used (FILTER is empty or "NoFilter"), so the night's session.json does. When a
target has nights of both, astroflow.multinight puts each filter set's frames under BAND_HO / BAND_SO and WBPP makes
one master per set (masterLight_..._BAND-HO.xisf); the two make an SHO image (video ep5b). Read from file names only.
"""
import re
from pathlib import Path

from . import wbpp

KEYWORD = "BAND"
BANDS = {"osc_multiband": "HO", "osc_so": "SO"}          # the night's filter_class -> its filter set
MASTER = re.compile(r"_BAND-(HO|SO)(?=[_.])", re.I)


def band_of(filter_class):
    """'HO' / 'SO' for a dual-band night, None for any other."""
    return BANDS.get(filter_class)


def masters(target_dir, recorded=None):
    """{'HO': path, 'SO': path} of a target's dual-band masters: `recorded` (state.json "masters"), else WBPP's,
    the autocropped ones first."""
    if recorded:
        return {b: Path(p) for b, p in recorded.items() if b in ("HO", "SO") and Path(p).exists()}
    out = {}
    for p in wbpp.masters(target_dir):
        m = MASTER.search(p.name)
        if m and m.group(1).upper() not in out:
            out[m.group(1).upper()] = p
    return out


def is_sho(found):
    return "HO" in found and "SO" in found
