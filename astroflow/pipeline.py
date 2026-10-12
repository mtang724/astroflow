"""Post-processing recipes run stage by stage on a WBPP master, with checkpoints and per-stage metrics.

    python -m astroflow.pipeline "<target dir>" [--recipe osc_broadband_nebula] [--stage NAME | --from NAME]
                                 [--set stage.step.param=value ...]

Work directory: <target>/Post/
    state.json             stages done, parameters used, results, metrics
    params.json            the user's saved parameter edits (from the app), applied to every run
    NN_<stage>.xisf        checkpoint written by each stage (input of the next)
    previews/*.jpg         what a human (or the vision model) looks at
    metrics/*.tif          downsampled linear-value copies for metrics.py

Recipes are lists of stages; every stage is ONE headless PixInsight job (one launch, ~12 s overhead), so a
stage can be re-run with new parameters without redoing earlier ones. Parameter defaults come from the
tutorial videos (knowledge/videos/*.md); the user's saved edits and then `overrides` (from the CLI or the agent)
are merged per step.
"""
import argparse
import copy
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from . import jobctx, jsonfile, metrics, objects, pi, wbpp

# --------------------------------------------------------------------------- recipes
# Step dicts are passed verbatim to pjsr/steps.js (op = function name). "id" lets overrides address a step.

NEBULA_EP1 = [
    {"stage": "linear", "input": "master", "output": "10_linear", "linear_in": True, "steps": [
        {"id": "locate", "op": "locate_object", "optional": True},   # object position: masks, crops, colour metrics
        {"id": "bg", "op": "find_background"},
        {"id": "gc", "op": "gradient_correction", "params": {}, "saveModel": "{previews}/10_gc_model.jpg"},
        {"id": "bg2", "op": "find_background"},
        {"id": "cc", "op": "color_calibration"},
        {"id": "pv_cc", "op": "preview", "path": "{previews}/10a_after_cc.jpg", "size": 1600},
        {"id": "bxt", "op": "bxt", "params": {}},
        {"id": "nxt", "op": "nxt", "params": {"denoise": 0.30, "denoise_color": 0.40, "iterations": 2}},
    ]},
    {"stage": "stretch", "input": "10_linear", "output": "20_stretched", "linear_in": True, "steps": [
        {"id": "stretch", "op": "stretch", "method": "ez_soft", "targetMedian": 0.20, "expandLow": 0.05,
         "aggressiveness": 5},
    ]},
    {"stage": "stars", "input": "20_stretched", "output": "30_starless", "stars_output": "31_stars",
     "linear_in": False, "steps": [
        {"id": "sxt", "op": "sxt", "unscreen": True},
    ]},
    {"stage": "starless", "input": "30_starless", "output": "40_starless_final", "linear_in": False, "steps": [
        {"id": "lhe", "op": "lhe", "params": {"radius": 162, "slopeLimit": 1.3, "amount": 0.8}},
        {"id": "sat", "op": "saturation", "boost": 0.72, "mask": "lum", "maskClip": 0.10, "passes": 2, "rgb": {}},
        {"id": "ht", "op": "ht", "shadows": "auto", "clipFraction": 0.0004, "midtones": 0.46},
        {"id": "nxt2", "op": "nxt", "params": {"denoise": 0.65, "denoise_color": 0.90, "iterations": 2}},
        {"id": "usm", "op": "usm", "params": {"sigma": 2.0, "amount": 0.6}},
    ]},
    {"stage": "stars_color", "input": "31_stars", "output": "41_stars_final", "linear_in": False, "steps": [
        {"id": "star_sat", "op": "saturation", "boost": 0.56, "mask": False},
        {"id": "scnr", "op": "scnr", "params": {"amount": 0.81}},
    ]},
    {"stage": "combine", "input": "40_starless_final", "aux": {"stars": "41_stars_final"}, "output": "50_final",
     "linear_in": False, "final": True, "steps": [
        {"id": "recombine", "op": "recombine", "mode": "screen", "starsAmount": 1.0},
    ]},
]

# Video ep2 (M31): GC treats a frame-filling galaxy as background -> DBE avoiding the galaxy; BNCC white reference
# on the galaxy body with Structure Detection off (SPCC preferred when it works); lighter linear NXT (high SNR);
# EZ HDR for the core; LHE through a RangeSelection mask; contrast HT then a second saturation pass.
GALAXY_EP2 = [
    {"stage": "linear", "input": "master", "output": "10_linear", "linear_in": True, "steps": [
        {"id": "locate", "op": "locate_object"},
        {"id": "bg", "op": "find_background"},
        {"id": "dbe", "op": "dbe_auto", "degree": 2, "objectScale": 1.8, "nx": 24, "ny": 16,
         "saveModel": "{previews}/10_dbe_model.jpg"},
        {"id": "bg2", "op": "find_background"},
        {"id": "cc", "op": "color_calibration", "bncc": {"whiteROI": "object", "structureDetection": False}},
        {"id": "pv_cc", "op": "preview", "path": "{previews}/10a_after_cc.jpg", "size": 1600},
        {"id": "bxt", "op": "bxt", "params": {}},
        {"id": "nxt", "op": "nxt", "params": {"denoise": 0.25, "denoise_color": 0.40, "iterations": 2}},
    ]},
    {"stage": "stretch", "input": "10_linear", "output": "20_stretched", "linear_in": True, "steps": [
        {"id": "stretch", "op": "stretch", "method": "ez_soft", "targetMedian": 0.20, "expandLow": 0.05,
         "aggressiveness": 5},
    ]},
    {"stage": "stars", "input": "20_stretched", "output": "30_starless", "stars_output": "31_stars",
     "linear_in": False, "steps": [
        {"id": "sxt", "op": "sxt", "unscreen": True},
    ]},
    {"stage": "starless", "input": "30_starless", "output": "40_starless_final", "linear_in": False, "steps": [
        {"id": "hdr", "op": "hdr", "layers": 5, "amount": 0.3},
        {"id": "lhe", "op": "lhe", "params": {"radius": "auto", "slopeLimit": 1.3, "amount": 0.8},
         "mask": "range", "rangeLow": 0.16, "rangeSmoothness": 65},
        {"id": "sat", "op": "saturation", "boost": 0.72, "mask": "lum", "maskClip": 0.10},
        {"id": "ht", "op": "ht", "shadows": "auto", "clipFraction": 0.00015, "midtones": 0.43},
        {"id": "sat2", "op": "saturation", "boost": 0.66, "mask": "lum", "maskClip": 0.10},
        {"id": "nxt2", "op": "nxt", "params": {"denoise": 0.55, "denoise_color": 0.80, "iterations": 2}},
        {"id": "usm", "op": "usm", "params": {"sigma": 2.0, "amount": 0.59}},
    ]},
    {"stage": "stars_color", "input": "31_stars", "output": "41_stars_final", "linear_in": False, "steps": [
        {"id": "star_sat", "op": "saturation", "boost": 0.54, "mask": False},
        {"id": "scnr", "op": "scnr", "params": {"amount": 0.53}},
    ]},
    {"stage": "combine", "input": "40_starless_final", "aux": {"stars": "41_stars_final"}, "output": "50_final",
     "linear_in": False, "final": True, "steps": [
        {"id": "recombine", "op": "recombine", "mode": "screen", "starsAmount": 1.0},
    ]},
]

# OSC + multiband (Antlia Quad Band, Ha+[NII]+[SII] / [OIII]) nebulae. Provisional until a narrowband tutorial
# video is added: BNCC instead of broadband SPCC, LHE scaled to the object, stronger non-linear NXT for the
# usually lower SNR, magenta removal on narrowband stars. See knowledge/filters.md.
MULTIBAND_NEB = [
    {"stage": "linear", "input": "master", "output": "10_linear", "linear_in": True, "steps": [
        {"id": "locate", "op": "locate_object", "optional": True},
        {"id": "bg", "op": "find_background"},
        {"id": "gc", "op": "gradient_correction", "params": {}, "saveModel": "{previews}/10_gc_model.jpg"},
        {"id": "bg2", "op": "find_background"},
        {"id": "cc", "op": "color_calibration", "method": "bncc"},
        {"id": "pv_cc", "op": "preview", "path": "{previews}/10a_after_cc.jpg", "size": 1600},
        {"id": "bxt", "op": "bxt", "params": {}},
        {"id": "nxt", "op": "nxt", "params": {"denoise": 0.30, "denoise_color": 0.45, "iterations": 2}},
    ]},
    {"stage": "stretch", "input": "10_linear", "output": "20_stretched", "linear_in": True, "steps": [
        {"id": "stretch", "op": "stretch", "method": "ez_soft", "targetMedian": 0.20, "expandLow": 0.05,
         "aggressiveness": 5},
    ]},
    {"stage": "stars", "input": "20_stretched", "output": "30_starless", "stars_output": "31_stars",
     "linear_in": False, "steps": [
        {"id": "sxt", "op": "sxt", "unscreen": True},
    ]},
    {"stage": "starless", "input": "30_starless", "output": "40_starless_final", "linear_in": False, "steps": [
        {"id": "lhe", "op": "lhe", "params": {"radius": "auto", "slopeLimit": 1.3, "amount": 0.7}, "radiusMax": 200},
        {"id": "sat", "op": "saturation", "boost": 0.72, "mask": "lum", "maskClip": 0.10, "passes": 2},
        {"id": "ht", "op": "ht", "shadows": "auto", "clipFraction": 0.0004, "midtones": 0.46},
        {"id": "nxt2", "op": "nxt", "params": {"denoise": 0.70, "denoise_color": 0.90, "iterations": 2}},
        {"id": "usm", "op": "usm", "params": {"sigma": 2.0, "amount": 0.5}},
    ]},
    {"stage": "stars_color", "input": "31_stars", "output": "41_stars_final", "linear_in": False, "steps": [
        {"id": "star_sat", "op": "saturation", "boost": 0.52, "mask": False},
        {"id": "scnr", "op": "scnr", "params": {"amount": 0.81}},
        {"id": "demagenta", "op": "scnr", "color": "magenta", "params": {"amount": 0.5}},
    ]},
    {"stage": "combine", "input": "40_starless_final", "aux": {"stars": "41_stars_final"}, "output": "50_final",
     "linear_in": False, "final": True, "steps": [
        {"id": "recombine", "op": "recombine", "mode": "screen", "starsAmount": 0.9},
    ]},
]

# Comets: input is astroflow.comet's comet layer (comet-aligned starless stack, linear, colour balanced on the stars,
# background already modelled per frame with the comet protected) plus its star layer (stars_linear.fits), so there is
# no gradient, colour or SXT step: the composite is stretched with exactly the comet layer's stretch and the stars are
# the screen-inverse difference (SXT would take the bright coma for a star). A few short frames -> noise is the main
# enemy (stronger linear NXT). Mid-April 2026 references of C/2025 R3: compact cyan-green coma, narrow blue ion tail
# with streamers, dark neutral sky -> strong stretch, then a black point that darkens the sky; LHE only through a
# luminance mask; no SCNR (the coma is green).
COMET = [
    {"stage": "linear", "input": "master", "output": "10_linear", "linear_in": True, "steps": [
        {"id": "bg", "op": "find_background"},
        {"id": "nxt", "op": "nxt", "params": {"denoise": 0.45, "denoise_color": 0.60, "iterations": 2}},
    ]},
    {"stage": "stretch", "input": "10_linear", "aux": {"comp": "stars_linear.fits"}, "output": "30_starless",
     "stars_output": "31_stars", "linear_in": True, "steps": [
        {"id": "compose", "op": "pixelmath", "target": "comp", "expression": "$T + main"},
        {"id": "stretch", "op": "stretch", "method": "ez_soft", "targetMedian": 0.20, "expandLow": 0.05,
         "aggressiveness": 5, "alsoOn": ["comp"]},
        {"id": "split", "op": "split_stars", "composite": "comp"},
    ]},
    {"stage": "starless", "input": "30_starless", "output": "40_starless_final", "linear_in": False, "steps": [
        # noise first: the black point and the saturation boost would otherwise clip / amplify the noisy blue channel
        {"id": "nxt2", "op": "nxt", "params": {"denoise": 0.60, "denoise_color": 0.90, "iterations": 2}},
        {"id": "lhe", "op": "lhe", "params": {"radius": 64, "slopeLimit": 1.5, "amount": 0.35}, "mask": "lum",
         "maskClip": 0.10},
        {"id": "sat", "op": "saturation", "boost": 0.80, "mask": "lum", "maskClip": 0.05, "passes": 2, "rgb": {}},
        {"id": "ht", "op": "ht", "shadows": "sky", "skyTarget": 0.09, "midtones": 0.48},   # references' sky ~0.09
    ]},
    {"stage": "stars_color", "input": "31_stars", "output": "41_stars_final", "linear_in": False, "steps": [
        {"id": "star_sat", "op": "saturation", "boost": 0.55, "mask": False},
    ]},
    {"stage": "combine", "input": "40_starless_final", "aux": {"stars": "41_stars_final"}, "output": "50_final",
     "linear_in": False, "final": True, "steps": [
        {"id": "recombine", "op": "recombine", "mode": "screen", "starsAmount": 1.0},
    ]},
]

RECIPES = {"osc_broadband_nebula": NEBULA_EP1, "osc_galaxy": GALAXY_EP2, "osc_multiband_nebula": MULTIBAND_NEB,
           "comet": COMET}


# --------------------------------------------------------------------------- state

class Work:
    def __init__(self, target_dir, recipe=None):
        self.target = Path(target_dir)
        self.session = objects.session_info(self.target)
        if recipe is None:
            recipe = objects.recipe_for(self.target.name, filter_class=self.session.get("filter_class"))[0]                 or "osc_broadband_nebula"
        self.dir = self.target / "Post"
        self.previews = self.dir / "previews"
        self.metrics = self.dir / "metrics"
        for d in (self.dir, self.previews, self.metrics):
            d.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / "state.json"
        self.state = json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.exists() else {}
        self.state.setdefault("recipe", recipe)
        self.state.setdefault("stages", {})
        self.state.setdefault("history", [])
        self.recipe = RECIPES[self.state["recipe"]]
        names = self.stage_names()                 # drop records of stages an older recipe version had
        self.state["stages"] = {k: v for k, v in self.state["stages"].items() if k in names}

    def save(self):
        jsonfile.write(self.state_path, self.state)

    def use_recipe(self, name):
        """Switch to another recipe and save: stage records of the old one no longer apply (their files stay)."""
        if self.state.get("recipe") != name:
            self.state["recipe"], self.recipe, self.state["stages"] = name, RECIPES[name], {}
        self.save()

    def master(self):
        if self.state.get("master"):
            return Path(self.state["master"])
        ms = wbpp.masters(self.target)
        if not ms:
            raise FileNotFoundError(f"no WBPP master in {self.target / 'Output' / 'master'}; run wbpp first")
        self.state["master"] = ms[0].as_posix()
        return ms[0]

    def checkpoint(self, name):
        if name == "master":
            return self.master()
        return self.dir / (name if Path(name).suffix.lower() in (".xisf", ".fits", ".fit", ".tif") else f"{name}.xisf")

    def stage(self, name):
        for s in self.recipe:
            if s["stage"] == name:
                return s
        raise KeyError(f"no stage {name} in recipe {self.state['recipe']}")

    def stage_names(self):
        return [s["stage"] for s in self.recipe]


def _fmt(obj, mapping):
    if isinstance(obj, str):
        return obj.format(**mapping)
    if isinstance(obj, dict):
        return {k: _fmt(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_fmt(v, mapping) for v in obj]
    return obj


def params_path(target_dir):
    """The user's saved parameter edits for a target (edited in the app: services/recipes.py)."""
    return Path(target_dir) / "Post" / "params.json"


def saved_overrides(target_dir):
    """{stage: {step_id: override}} the user saved for this target. Every run applies them (from the app, the agent or
    the command line); overrides given for one run go on top."""
    p = params_path(target_dir)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def merge_overrides(base, extra):
    """Per-step overrides of one stage, `extra` winning; nested `params` are merged key by key."""
    out = copy.deepcopy(base or {})
    for sid, ov in (extra or {}).items():
        step = out.setdefault(sid, {})
        for k, v in ov.items():
            if k == "params" and isinstance(v, dict):
                step.setdefault("params", {}).update(v)
            else:
                step[k] = v
    return out


def merge_step(step, override):
    """Overrides may set top-level step keys or nested `params`; `{"enabled": false}` drops the step."""
    s = copy.deepcopy(step)
    for k, v in (override or {}).items():
        if k == "params" and isinstance(v, dict):
            s.setdefault("params", {}).update(v)
        else:
            s[k] = v
    return s


def solve_hints(target_dir):
    """RA/Dec/focal/pixel size from a raw light, for plate solving when the master has no solution."""
    from astropy.io import fits
    lights = sorted((Path(target_dir) / "Light").glob("*.fit*"))
    if not lights:
        return {}
    h = fits.getheader(lights[0])
    out = {}
    for k_src, k_dst in (("RA", "ra"), ("DEC", "dec"), ("FOCALLEN", "focal"), ("XPIXSZ", "pixelSize")):
        if k_src in h:
            out[k_dst] = float(h[k_src])
    return out


# --------------------------------------------------------------------------- running

def run_stage(work, name, overrides=None, timeout=3600):
    """Run one stage. overrides: {step_id: {...}}, on top of the user's saved edits. Returns the stage record stored in
    state.json."""
    spec = work.stage(name)
    overrides = merge_overrides(saved_overrides(work.target).get(name), overrides)
    prev = {"previews": work.previews.as_posix(), "metrics": work.metrics.as_posix(), "post": work.dir.as_posix()}
    steps = []
    for st in spec["steps"]:
        s = merge_step(st, overrides.get(st["id"]))
        if s.pop("enabled", True) is False:
            continue
        if s["op"] in ("color_calibration", "plate_solve"):
            s.setdefault("solve", {}).update({k: v for k, v in solve_hints(work.target).items() if k not in s["solve"]})
        if s["op"] == "locate_object":
            cat = objects.lookup(work.state.get("object_name") or work.target.name) or {}
            for k in ("ra", "dec", "diameter", "axisRatio", "posAngle"):
                if k not in s and cat.get(k) is not None:
                    s[k] = cat[k]
            if "ra" not in s:
                continue   # not in the catalogue: object-aware steps fall back to whole-image behaviour
        if s["op"] == "lhe" and s.get("params", {}).get("radius") == "auto":
            semi = (work.state.get("object") or {}).get("semiMajorPx")
            cap = s.pop("radiusMax", 512)
            s["params"]["radius"] = int(min(cap, max(24, round(0.35 * semi)))) if semi else 162
        s.pop("radiusMax", None)
        steps.append(_fmt(s, prev))

    out_name = spec["output"]
    job = {"input": work.checkpoint(spec["input"]).as_posix(), "linear": spec.get("linear_in", False),
           "colorCalibrated": work.state.get("colorCalibrated", False), "unscreen": work.state.get("unscreen"),
           "steps": steps,
           "save": [{"window": "main", "path": (work.dir / f"{out_name}.xisf").as_posix()}],
           "previews": [{"window": "main", "path": (work.previews / f"{out_name}.jpg").as_posix(), "size": 1600}],
           "metrics": [{"window": "main", "path": (work.metrics / f"{out_name}.tif").as_posix(), "size": 2048}]}
    if spec.get("aux"):
        job["aux"] = {k: work.checkpoint(v).as_posix() for k, v in spec["aux"].items()}
    if spec.get("stars_output"):
        so = spec["stars_output"]
        job["save"].append({"window": "stars", "path": (work.dir / f"{so}.xisf").as_posix()})
        job["previews"].append({"window": "stars", "path": (work.previews / f"{so}.jpg").as_posix(), "size": 1600,
                                "linear": False})
    if spec.get("final"):
        stem = work.dir / f"{work.target.name}_{datetime.now():%Y%m%d}"
        job["save"] += [{"window": "main", "path": f"{stem.as_posix()}.tif", "bits": 16},
                        {"window": "main", "path": f"{stem.as_posix()}.jpg", "bits": 8},
                        {"window": "main", "path": f"{stem.as_posix()}.png", "bits": 8}]
        job["previews"].append({"window": "main", "path": (work.previews / f"{out_name}_2k.jpg").as_posix(),
                                "size": 2048})

    t0 = time.time()
    res = pi.run_job(job, timeout=timeout, label=f"{work.target.name.replace(' ', '')}-{name}")
    for f in res.get("saved", []):
        if f.lower().endswith(".png"):
            _fix_png(f)
    m = None
    if res.get("metrics"):
        m = metrics.analyze(res["metrics"][0], linear=res.get("linear"))
    rec = {"stage": name, "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "seconds": round(time.time() - t0, 1), "overrides": overrides, "steps": res["steps"],
           "previews": res.get("previews", []), "saved": res.get("saved", []), "metrics": m,
           "stats": res.get("stats"), "noise": res.get("noise"), "steps_spec": steps}
    work.state["stages"][name] = rec
    work.state["history"].append({"stage": name, "time": rec["time"], "overrides": overrides})
    if res.get("colorCalibrated"):
        work.state["colorCalibrated"] = True
    for st in res["steps"]:
        if st["op"] == "locate_object" and st.get("info") and not st["info"].get("skipped"):
            work.state["object"] = st["info"]
    if res.get("unscreen") is not None:
        work.state["unscreen"] = res["unscreen"]
    # a re-run invalidates everything downstream
    names = work.stage_names()
    for later in names[names.index(name) + 1:]:
        work.state["stages"].pop(later, None)
    work.save()
    return rec


def _fix_png(path):
    """PixInsight writes 8-bit PNGs with an alpha channel; store plain RGB (smaller, opens everywhere), keep the ICC."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(path)
    if im.mode in ("RGBA", "LA"):
        icc = im.info.get("icc_profile")
        rgb = im.convert("RGB" if im.mode == "RGBA" else "L")
        rgb.save(path, "PNG", icc_profile=icc, compress_level=6)


def export_final(target_dir, formats=("png",), bits=8):
    """Re-export the finished image (Post/50_final.xisf) in other formats without re-running any stage."""
    work = Work(target_dir)
    src = work.dir / "50_final.xisf"
    if not src.exists():
        raise FileNotFoundError(f"{src} does not exist; run the combine stage first")
    stem = work.dir / f"{work.target.name}_{datetime.now():%Y%m%d}"
    job = {"input": src.as_posix(), "linear": False, "steps": [],
           "save": [{"window": "main", "path": f"{stem.as_posix()}.{ext}", "bits": bits} for ext in formats]}
    res = pi.run_job(job, timeout=1800, label=f"{work.target.name.replace(' ', '')}-export")
    for f in res.get("saved", []):
        if f.lower().endswith(".png"):
            _fix_png(f)
    return res.get("saved", [])


def locate(target_dir):
    """Project the catalogue position/size into the image (needs a plate-solved checkpoint) and store it in state."""
    work = Work(target_dir)
    cat = objects.lookup(work.target.name)
    if not cat:
        raise ValueError(f"{work.target.name} is not in the catalogue")
    src = work.dir / "10_linear.xisf"
    if not src.exists():
        src = work.master()
    step = {"op": "locate_object", **{k: cat[k] for k in ("ra", "dec", "diameter", "axisRatio", "posAngle")}}
    res = pi.run_job({"input": Path(src).as_posix(), "linear": True, "steps": [step]}, timeout=600,
                     label=f"{work.target.name.replace(' ', '')}-locate")
    work.state["object"] = res["steps"][0]["info"]
    work.save()
    return work.state["object"]


def export_crop(target_dir, width, height, center=None, formats=("png", "jpg")):
    """Extra export of the finished image cropped around the object (catalogue position from locate_object, or
    `center` (x, y) in pixels). The full-frame finals are kept; files get a `_crop` suffix."""
    work = Work(target_dir)
    src = work.dir / "50_final.xisf"
    if not src.exists():
        raise FileNotFoundError(f"{src} does not exist; run the combine stage first")
    if center is None:
        obj = work.state.get("object") or {}
        if "cx" not in obj:
            raise ValueError("no object position recorded (locate_object did not run); pass center=(x, y)")
        center = (obj["cx"], obj["cy"])
    W, H = work.state["stages"]["combine"]["stats"]["width"], work.state["stages"]["combine"]["stats"]["height"]
    width, height = min(width, W), min(height, H)
    x0 = int(min(max(0, center[0] - width / 2), W - width))
    y0 = int(min(max(0, center[1] - height / 2), H - height))
    stem = work.dir / f"{work.target.name}_{datetime.now():%Y%m%d}_crop"
    job = {"input": src.as_posix(), "linear": False,
           "steps": [{"op": "crop", "rect": [x0, y0, x0 + int(width), y0 + int(height)]}],
           "save": [{"window": "main", "path": f"{stem.as_posix()}.{ext}", "bits": 8} for ext in formats],
           "previews": [{"window": "main", "path": (work.previews / "50_final_crop.jpg").as_posix(), "size": 1600}]}
    res = pi.run_job(job, timeout=1800, label=f"{work.target.name.replace(' ', '')}-crop")
    for f in res.get("saved", []):
        if f.lower().endswith(".png"):
            _fix_png(f)
    return res.get("saved", []) + res.get("previews", [])


def run(target_dir, recipe=None, start=None, only=None, overrides=None, master=None):
    """master: start image when it is not a WBPP master (e.g. astroflow.comet's comet_linear.fits)."""
    work = Work(target_dir, recipe)
    if master:
        work.state["master"] = Path(master).as_posix()
    names = work.stage_names()
    todo = [only] if only else names[names.index(start):] if start else \
        [n for n in names if n not in work.state["stages"]]
    out = []
    for i, n in enumerate(todo):
        jobctx.check_cancelled()
        jobctx.emit("stage.started", stage=n, index=i, total=len(todo), target=work.target.name)
        out.append(run_stage(work, n, (overrides or {}).get(n)))
        jobctx.emit("stage.finished", stage=n, index=i, total=len(todo), seconds=out[-1]["seconds"],
                    previews=out[-1].get("previews", []))
    return out


def parse_sets(sets):
    """--set stage.step.param=value  (value parsed as JSON when possible)."""
    ov = {}
    for s in sets or []:
        key, val = s.split("=", 1)
        try:
            val = json.loads(val)
        except json.JSONDecodeError:
            pass
        parts = key.split(".")
        stage, step = parts[0], parts[1]
        d = ov.setdefault(stage, {}).setdefault(step, {})
        if len(parts) == 4 and parts[2] == "params":
            d.setdefault("params", {})[parts[3]] = val
        else:
            d[parts[2]] = val
    return ov


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target")
    ap.add_argument("--recipe", choices=sorted(RECIPES), help="default: chosen from the target type (objects.py)")
    ap.add_argument("--stage", help="run only this stage")
    ap.add_argument("--from", dest="start", help="run this stage and everything after it")
    ap.add_argument("--set", action="append", help="override, e.g. starless.sat.boost=0.65 or linear.nxt.params.denoise=0.25")
    ap.add_argument("--master", help="start image when it is not a WBPP master (e.g. Post/comet_linear.fits)")
    a = ap.parse_args()
    for rec in run(a.target, a.recipe, a.start, a.stage, parse_sets(a.set), a.master):
        print(json.dumps({k: rec[k] for k in ("stage", "seconds", "previews", "metrics")}, ensure_ascii=False, indent=1))
