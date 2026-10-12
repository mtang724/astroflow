"""Top-rated works of a target from AstroBin, used as style references (local, personal use only).

    python -m astroflow.references "M 8" [--n 8]

For each target: knowledge/targets/<slug>/refs.json (title, author, URL, likes, awards, equipment, integration),
thumbnails refs/*.jpg (620 px "regular" size) and their metrics fingerprints (metrics.analyze), so the agent can
compare its result against how the best images of the same object look. Two groups are kept:
    "best"  - most liked overall, IOTD / Top Pick first (aspiration: structure, colour, balance)
    "peer"  - colour-sensor (OSC) images without narrowband filters (what this equipment can realistically reach)
Credits are kept with every image; nothing here is redistributed.
"""
import argparse
import json
import re
import time
from pathlib import Path

import requests

from . import config, jobctx, jsonfile, metrics

API = "https://www.astrobin.com/api/v2/images/image-search/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/141.0.0.0 Safari/537.36")
NARROWBAND = {"H_ALPHA", "OIII", "SII", "NII", "H_BETA", "MULTIBAND", "DUAL_BAND", "TRI_BAND", "QUAD_BAND"}

# Common names help the search and the notes; extend as new targets appear.
ALIASES = {
    "M8": ["M8", "M 8", "Lagoon Nebula"], "M101": ["M101", "M 101", "Pinwheel Galaxy"],
    "NGC 6334": ["NGC 6334", "Cat's Paw Nebula"], "IC 1805": ["IC 1805", "Heart Nebula"],
    "NGC 246": ["NGC 246", "Skull Nebula"], "NGC 7293": ["NGC 7293", "Helix Nebula"],
    "M42": ["M42", "M 42", "Orion Nebula"], "IC 434": ["IC 434", "Horsehead Nebula"],
    "C/2025 R3": ["C/2025 R3", "C/2025 R3 (PanSTARRS)"],
}


def slug(target):
    return re.sub(r"[^A-Za-z0-9]+", "", target).upper()


def _get(params, tries=3):
    for i in range(tries):
        r = requests.get(API, params=params, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=40)
        if r.status_code == 200:
            return r.json()
        jobctx.sleep(3 * (i + 1))
    r.raise_for_status()


def search(target, pages=2, page_size=50):
    names = ALIASES.get(target.replace(" ", "") if target.replace(" ", "").startswith("M") else target, [target])
    seen, out = set(), []
    for name in names[:2]:
        for page in range(1, pages + 1):
            d = _get({"subject": name, "ordering": "-likes", "page_size": page_size, "page": page})
            for r in d.get("results", []):
                key = r.get("hash") or r.get("objectId")
                if key in seen:
                    continue
                seen.add(key)
                out.append(r)
            if not d.get("next"):
                break
    return out


def _is_peer(r, mode="broadband"):
    """broadband: colour sensor, no narrowband filters. multiband: colour sensor + dual/quad-band or line filters."""
    sensors = " ".join(r.get("imagingSensors") or [])
    filters = set(r.get("filterTypes") or [])
    if "(color)" not in sensors:
        return False
    return bool(filters & NARROWBAND) if mode == "multiband" else not (filters & NARROWBAND)


def _entry(r):
    url = f"https://www.astrobin.com/{r['hash']}/" if r.get("hash") else f"https://www.astrobin.com/{r.get('objectId')}/"
    return {"title": r.get("title"), "author": r.get("userDisplayName") or r.get("username"), "url": url,
            "likes": r.get("likes"), "iotd": r.get("isIotd"), "top_pick": r.get("isTopPick"),
            "sensors": r.get("imagingSensors"), "telescopes": r.get("imagingTelescopes2"),
            "filters": r.get("filterTypes"), "integration_h": round((r.get("integration") or 0) / 3600, 1),
            "pixel_scale": r.get("pixelScale"), "field_radius_deg": r.get("fieldRadius"),
            "thumb": r.get("regularThumbnail"), "thumb_hd": r.get("hdThumbnail")}


def _sep_deg(ra1, dec1, ra2, dec2):
    import math
    r = math.radians
    c = math.sin(r(dec1)) * math.sin(r(dec2)) + math.cos(r(dec1)) * math.cos(r(dec2)) * math.cos(r(ra1 - ra2))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def _on_target(r, cat, target):
    """Common-name searches return other objects ('Skull Nebula' -> NGC 2467, Sh2-68...). Keep an image when its
    plate-solved centre is near the catalogue position, or (unsolved) when its title names the object."""
    ra, dec = r.get("coordRaCenter"), r.get("coordDecCenter")
    if cat and ra is not None and dec is not None:
        limit = max(1.0, (r.get("fieldRadius") or 1.0)) + (cat.get("diameter") or 10) / 120.0
        return _sep_deg(ra, dec, cat["ra"], cat["dec"]) <= limit
    title = re.sub(r"\s+", "", (r.get("title") or "")).upper()
    ids = {re.sub(r"\s+", "", a).upper() for a in ALIASES.get(target, [target]) if re.match(r"^(M|NGC|IC|SH2|LBN)", a.upper())}
    ids.add(re.sub(r"\s+", "", target).upper())
    return any(i in title for i in ids)


def _fov_ok(r, fov_radius):
    fr = r.get("fieldRadius")
    return fov_radius is None or fr is None or fov_radius / 3 <= fr <= fov_radius * 3


def _in_window(r, window):
    if not window:
        return True
    day = (r.get("published") or "")[:10]
    return bool(day) and window[0] <= day <= window[1]


def fetch(target, n=8, out_root=None, fov_radius=None, peer="broadband", published=None):
    """fov_radius (deg): our field radius; references framed very differently (mosaics, close-ups) are skipped.
    peer: "broadband" or "multiband" - which colour-sensor images count as peers (match the night's filter).
    published: (first, last) ISO dates - for comets, whose tail changes within days; without a catalogue
    position the title has to name the comet."""
    out = Path(out_root or config.KNOWLEDGE / "targets") / slug(target)
    (out / "refs").mkdir(parents=True, exist_ok=True)
    for f in (out / "refs").glob("*.jpg"):   # a refetch may reorder/replace images: never reuse old best_NN/peer_NN files
        f.unlink()
    from . import objects
    cat = objects.lookup(target)
    raw = search(target)
    results = [r for r in raw if _fov_ok(r, fov_radius) and _on_target(r, cat, target) and _in_window(r, published)]
    def award(r):
        return bool(r.get("isIotd")) or bool(r.get("isTopPick")), r.get("likes") or 0

    best = sorted(results, key=award, reverse=True)[:n]
    peer_list = [r for r in sorted(results, key=lambda r: r.get("likes") or 0, reverse=True) if _is_peer(r, peer)]
    peer_mode = peer
    peer_list = [r for r in peer_list if r not in best][:n]
    groups = {"best": [_entry(r) for r in best], "peer": [_entry(r) for r in peer_list]}
    for gname, items in groups.items():
        for i, e in enumerate(items):
            if not e["thumb"]:
                continue
            p = out / "refs" / f"{gname}_{i:02d}.jpg"
            r = requests.get(e["thumb"], headers={"User-Agent": UA}, timeout=60)
            if r.status_code != 200:
                continue
            p.write_bytes(r.content)
            e["file"] = p.as_posix()
            try:
                e["fingerprint"] = metrics.analyze(p)
            except Exception as ex:   # corrupt/animated thumbnails
                e["fingerprint_error"] = str(ex)
    doc = {"target": target, "aliases": ALIASES.get(target, [target]), "fetched": time.strftime("%Y-%m-%d"),
           "peer_mode": peer_mode, "published_window": published,
           "source": "AstroBin image search, ordered by likes", "candidates_seen": len(raw),
           "candidates_on_target": len(results), **groups}
    jsonfile.write(out / "refs.json", doc)
    return doc


def load(target):
    p = config.KNOWLEDGE / "targets" / slug(target) / "refs.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def fingerprints(target, group=None):
    doc = load(target) or {}
    gs = [group] if group else ["best", "peer"]
    return [e["fingerprint"] for g in gs for e in doc.get(g, []) if e.get("fingerprint")]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--fov", type=float, help="our field radius in degrees (filters out very different framings)")
    ap.add_argument("--peer", choices=["broadband", "multiband"], default="broadband")
    ap.add_argument("--published", nargs=2, metavar=("FIRST", "LAST"), help="ISO dates (comets)")
    a = ap.parse_args()
    d = fetch(a.target, a.n, fov_radius=a.fov, peer=a.peer, published=a.published)
    for g in ("best", "peer"):
        print(g)
        for e in d[g]:
            print(f"  {e['likes']:>5}  {'IOTD' if e['iotd'] else '    '} {'TP' if e['top_pick'] else '  '} "
                  f"{(e['title'] or '')[:50]:<50} {e['author']}  {e['integration_h']}h")
