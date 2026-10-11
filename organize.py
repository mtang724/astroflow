"""Organize raw astrophotography sessions into In Processing/<YYYYMonDD>/<Target>/{Light,Dark,Bias,Flat}.

Layout follows F:\\AstroPhotograph\\Processed\\2026Mar22\\M42. Sessions stay in "In Processing"
until post-processing is done, then move to "Processed".

- Lights: unorganized target folders directly under ROOT (any folder holding Light_*.fit).
  They are MOVED into the session folder.
- Darks:  copied from "Dark Library", matched by FITS header (EXPTIME, GAIN, OFFSET, binning,
  sensor size, camera, SET-TEMP). Folder names in the library are ignored.
- Bias:   copied from "Bias Library", matched the same way minus EXPTIME.
- Flats:  copied from "Flat", matched by observing night (same gain/offset/binning/camera).

The night is the local capture time minus 12 h, so frames after midnight stay with the evening.

Set-points within TEMP_TOLERANCE (1 °C) count as a match; an exact set-point always wins over a near one.

Usage:
    python organize.py                      # dry run: print the plan, touch nothing
    python organize.py --apply              # carry out the plan
    python organize.py --refresh [--apply]  # re-match calibration for targets already in In Processing
                                            # (e.g. after shooting missing darks); lights are never moved
"""
import argparse
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from astropy.io import fits

ROOT = Path(r"F:\AstroPhotograph")
STAGING = ROOT / "In Processing"
DARK_LIB = ROOT / "Dark Library"
BIAS_LIB = ROOT / "Bias Library"
FLAT_DIR = ROOT / "Flat"
SKIP_DIRS = {"Processed", "In Processing", "Dark Library", "Bias Library", "Flat"}

FNAME_TIME = re.compile(r"_(\d{8}-\d{6})_")
ROTATOR_WARN_DEG = 3


def read_meta(path):
    h = fits.getheader(path)
    meta = {
        "path": path,
        "type": str(h.get("IMAGETYP", "")).strip().lower(),
        "object": str(h.get("OBJECT", "")).strip(),
        "exptime": float(h.get("EXPTIME", 0)),
        "gain": h.get("GAIN"),
        "offset": h.get("OFFSET"),
        "settemp": h.get("SET-TEMP"),
        "ccdtemp": h.get("CCD-TEMP"),
        "bin": h.get("XBINNING", 1),
        "size": (h.get("NAXIS1"), h.get("NAXIS2")),
        "camera": str(h.get("INSTRUME", "")).strip(),
        "rotator": h.get("ROTATOR"),
    }
    meta["local_time"] = local_time(path, h)
    meta["night"] = (meta["local_time"] - timedelta(hours=12)).date()
    return meta


def local_time(path, h):
    m = FNAME_TIME.search(path.name)
    if m:
        return datetime.strptime(m.group(1), "%Y%m%d-%H%M%S")
    for key in ("DATE-LOC", "DATE-OBS"):
        if key in h:
            return datetime.fromisoformat(str(h[key])[:19])
    raise ValueError(f"No capture time for {path}")


def sensor_key(m):
    return (m["gain"], m["offset"], m["bin"], m["size"], m["camera"])


TEMP_TOLERANCE = 1.0   # °C between set-points; 0.5 °C changes IMX571 dark current by only ~6 %


def temp_diff(light, cal):
    if light["settemp"] is not None and cal["settemp"] is not None:
        return abs(float(light["settemp"]) - float(cal["settemp"]))
    return abs(float(light["ccdtemp"]) - float(cal["ccdtemp"]))


def temp_matches(light, cal):
    return temp_diff(light, cal) <= (TEMP_TOLERANCE if light["settemp"] is not None and cal["settemp"] is not None else 2)


def closest_temp(ref, frames):
    """Frames at the set-point closest to the light's (exact matches win over the tolerance band)."""
    ok = [c for c in frames if temp_matches(ref, c)]
    if not ok:
        return []
    best = min(temp_diff(ref, c) for c in ok)
    return [c for c in ok if temp_diff(ref, c) == best]


def scan_fits(folder):
    return [read_meta(p) for p in sorted(folder.rglob("*.fit*")) if p.suffix.lower() in (".fit", ".fits")]


def session_name(night):
    return f"{night.year}{night.strftime('%b')}{night.day:02d}"


def target_name(obj):
    m = re.fullmatch(r"M\s+(\d+)", obj)
    return f"M{m.group(1)}" if m else obj


def build_plan(refresh=False):
    """refresh=False: new target folders under ROOT. refresh=True: re-match calibration frames for targets
    already staged in In Processing (e.g. after new darks were added to the library); their lights stay put."""
    darks = [m for m in scan_fits(DARK_LIB) if m["type"] == "dark"]
    biases = [m for m in scan_fits(BIAS_LIB) if m["type"] == "bias"]
    flats = [m for m in scan_fits(FLAT_DIR) if m["type"] == "flat"]

    groups = defaultdict(list)
    skipped = []
    if refresh:
        for light_dir in sorted(STAGING.glob("*/*/Light")):
            for p in sorted(light_dir.glob("Light_*.fit*")):
                m = read_meta(p)
                m["source_dir"] = light_dir.parent
                groups[(m["night"], light_dir.parent.name)].append(m)
    else:
        for d in sorted(ROOT.iterdir()):
            if not d.is_dir() or d.name in SKIP_DIRS or d.name.startswith("."):
                continue
            lights = [read_meta(p) for p in sorted(d.glob("Light_*.fit*"))]
            if not lights:
                skipped.append(d)
                continue
            for m in lights:
                m["source_dir"] = d
                groups[(m["night"], target_name(m["object"] or d.name))].append(m)

    plan = []
    for (night, target), lights in sorted(groups.items()):
        dest = lights[0]["source_dir"] if refresh else STAGING / session_name(night) / target
        item = {"dest": dest, "lights": lights, "darks": [], "bias": [], "flats": [], "warnings": [],
                "lights_in_place": refresh}

        for skey in sorted({sensor_key(lt) for lt in lights}, key=str):
            ls = [lt for lt in lights if sensor_key(lt) == skey]
            for exp in sorted({lt["exptime"] for lt in ls}):
                for temp in sorted({lt["settemp"] for lt in ls if lt["exptime"] == exp}, key=str):
                    ref = next(lt for lt in ls if lt["exptime"] == exp and lt["settemp"] == temp)
                    match = closest_temp(ref, [c for c in darks if sensor_key(c) == skey
                                               and abs(c["exptime"] - exp) < 0.01])
                    if not match:
                        item["warnings"].append(f"NO DARKS for {exp:g}s @ {temp}C (gain {skey[0]}, offset {skey[1]})")
                    elif temp_diff(ref, match[0]) > 0:
                        item["warnings"].append(f"darks for {exp:g}s @ {temp}C taken at {match[0]['settemp']}C (within tolerance)")
                    item["darks"] += match
            for temp in sorted({lt["settemp"] for lt in ls}, key=str):
                ref = next(lt for lt in ls if lt["settemp"] == temp)
                match = closest_temp(ref, [c for c in biases if sensor_key(c) == skey])
                if not match:
                    item["warnings"].append(f"NO BIAS @ {temp}C")
                item["bias"] += match
            match = [f for f in flats if sensor_key(f) == skey and f["night"] == night]
            if not match:
                item["warnings"].append(f"NO FLATS for night {night}")
            item["flats"] += match

        light_rot = {lt["rotator"] for lt in lights if lt["rotator"] is not None}
        flat_rot = {f["rotator"] for f in item["flats"] if f["rotator"] is not None}
        if light_rot and flat_rot and max(abs(a - b) for a in light_rot for b in flat_rot) > ROTATOR_WARN_DEG:
            item["warnings"].append(f"Rotator mismatch: lights {sorted(light_rot)} vs flats {sorted(flat_rot)}")

        for key in ("darks", "bias", "flats"):
            item[key] = list({m["path"]: m for m in item[key]}.values())
        plan.append(item)
    return plan, skipped


def describe(frames):
    counts = defaultdict(int)
    for m in frames:
        counts[(float(f"{m['exptime']:.3g}"), m["settemp"])] += 1
    return ", ".join(f"{n}x {e:g}s@{t}C" for (e, t), n in sorted(counts.items(), key=str)) or "-"


def print_plan(plan, skipped):
    for item in plan:
        print(f"\n=== {item['dest'].relative_to(ROOT)}")
        srcs = sorted({str(lt['source_dir'].name) for lt in item["lights"]})
        print(f"  Light ({len(item['lights'])}) from {srcs}: {describe(item['lights'])}")
        print(f"  Dark  ({len(item['darks'])}): {describe(item['darks'])}")
        print(f"  Bias  ({len(item['bias'])}): {describe(item['bias'])}")
        print(f"  Flat  ({len(item['flats'])}): {describe(item['flats'])}")
        for w in item["warnings"]:
            print(f"  !! {w}")
    for d in skipped:
        print(f"\n(skipped {d.name}: no Light_*.fit files at top level)")


def copy_or_move(src, dst_dir, move):
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if dst.resolve() == src.resolve():   # already in place: never "move" a file onto itself (would unlink it)
        return
    if dst.exists():
        if dst.stat().st_size == src.stat().st_size:
            if move:
                src.unlink()
            return
        raise FileExistsError(f"{dst} exists with a different size")
    (shutil.move if move else shutil.copy2)(str(src), str(dst))


def apply_plan(plan):
    for item in plan:
        dest = item["dest"]
        print(f"Writing {dest} ...")
        for key, sub in (("darks", "Dark"), ("bias", "Bias"), ("flats", "Flat")):
            for m in item[key]:
                copy_or_move(m["path"], dest / sub, move=False)
        for m in ([] if item.get("lights_in_place") else item["lights"]):
            copy_or_move(m["path"], dest / "Light", move=True)
            thumb = m["path"].with_name(m["path"].stem + "_thn.jpg")
            if thumb.exists():
                copy_or_move(thumb, dest / "Thumbnails", move=True)
        with open(dest / "calibration_manifest.txt", "w", encoding="utf-8") as f:
            for key in ("lights", "darks", "bias", "flats"):
                f.write(f"[{key}]\n")
                for m in item[key]:
                    f.write(f"{m['path'].name}\texp={m['exptime']:g}\tset={m['settemp']}\tccd={m['ccdtemp']}\n")
            for w in item["warnings"]:
                f.write(f"WARNING: {w}\n")
    for src in {lt["source_dir"] for item in plan if not item.get("lights_in_place") for lt in item["lights"]}:
        if src.exists() and not any(src.iterdir()):
            src.rmdir()
            print(f"Removed empty {src}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="carry out the plan (default is a dry run)")
    ap.add_argument("--refresh", action="store_true",
                    help="re-match darks/bias/flats for targets already in 'In Processing' (lights are not moved)")
    args = ap.parse_args()
    plan, skipped = build_plan(refresh=args.refresh)
    print_plan(plan, skipped)
    if args.apply:
        apply_plan(plan)
    else:
        print("\nDry run only. Re-run with --apply to execute.")


if __name__ == "__main__":
    sys.exit(main())
