"""Tools the agent can call. Each returns JSON-serialisable data; long outputs are trimmed for the LLM.

Scripts do what is deterministic (run PixInsight, compute metrics, fetch references); anything that needs
judgement (is this gradient model clean? is the colour right? is it better than before?) goes to the LLM,
either the planner itself or `look` (vision model) with the previews and reference images.
"""
import json
import re
import time
from contextlib import contextmanager
from pathlib import Path

from .. import config, metrics, objects, pipeline, references, wbpp
from ..i18n import tr
from ..services import actions, targets
from . import skills

REGISTRY = {}


def tool(description, **params):
    """Register a function as an LLM tool. params: name -> (json type, description, required?)."""
    def deco(fn):
        props, req = {}, []
        for name, spec in params.items():
            typ, desc = spec[0], spec[1]
            props[name] = {"type": typ, "description": desc} if typ != "object" else {"type": "object", "description": desc}
            if typ == "array":
                props[name]["items"] = {"type": "object"}
            if len(spec) < 3 or spec[2]:
                req.append(name)
        REGISTRY[fn.__name__] = {"fn": fn, "schema": {"type": "function", "function": {
            "name": fn.__name__, "description": description,
            "parameters": {"type": "object", "properties": props, "required": req}}}}
        return fn
    return deco


def schemas():
    return [t["schema"] for t in REGISTRY.values()]


class ToolContext:
    """What the tools need from the agent session running them: the LLM (for `look`) and the PixInsight job budget."""

    def __init__(self, llm=None, max_pi_jobs=30):
        self.llm = llm
        self.max_pi_jobs = max_pi_jobs
        self.pi_jobs = 0

    def spend(self):
        self.pi_jobs += 1
        if self.pi_jobs > self.max_pi_jobs:
            raise RuntimeError(f"PixInsight job budget ({self.max_pi_jobs}) exhausted for this run; call finish.")


_ctx = ToolContext()


@contextmanager
def bound(ctx):
    """Run tools with this session's context (one agent session runs at a time)."""
    global _ctx
    previous, _ctx = _ctx, ctx
    try:
        yield ctx
    finally:
        _ctx = previous


def call(name, args):
    if name not in REGISTRY:
        raise KeyError(f"unknown tool {name}")
    return REGISTRY[name]["fn"](**args)


def resolve(target):
    p = Path(target)
    if p.is_dir():
        return p
    hits = [d for d in config.IN_PROCESSING.glob("*/*") if d.is_dir() and objects.norm(d.name) == objects.norm(target)]
    if not hits:
        raise FileNotFoundError(f"target {target} not found under {config.IN_PROCESSING}")
    return sorted(hits)[-1]


def _inside(root, path):
    """`path` resolved, if it lies inside `root`, else None. File names come from the model, and the model reads web
    content (reference titles): a name like '../.env' must not reach files outside the folder meant."""
    p, r = Path(path).resolve(), Path(root).resolve()
    return p if p.is_relative_to(r) else None


# ----------------------------------------------------------------------------------------------- discovery

@tool("List every target under 'In Processing' with its status (lights, calibration, WBPP master, post stages done).")
def list_targets():
    return targets.list_targets()


@tool("Inspect one target: acquisition summary from FITS headers, calibration warnings, catalogue data, "
      "object type and suggested recipe, current pipeline state and metrics, the user's saved parameter edits "
      "(applied to every run), available knowledge.",
      target=("string", "target name (e.g. 'M8', 'NGC 6334') or full path"))
def inspect_target(target):
    d = resolve(target)
    info = targets.detail(d)
    w = pipeline.Work(d) if (d / "Post" / "state.json").exists() else None
    stages = {k: {"metrics": v.get("metrics"), "previews": v.get("previews"), "overrides": v.get("overrides")}
              for k, v in (w.state.get("stages", {}) if w else {}).items()}
    kn = config.KNOWLEDGE / "targets" / references.slug(d.name)
    return {"path": info["path"], "session": info["session"], "acquisition": info["acquisition"],
            "calibration_warnings": info["calibration_warnings"],
            "calibration_counts": {k: info[k] for k in ("darks", "bias", "flats")},
            "catalogue": info["catalogue"], "type": info["type"], "suggested_recipe": info["recipe"],
            "master": [p.as_posix() for p in wbpp.masters(d)],
            "pipeline": {"recipe": w.state.get("recipe") if w else None, "stages": stages,
                         "object_px": w.state.get("object") if w else None},
            "user_params": pipeline.saved_overrides(d),
            "knowledge": {"target_notes": (kn / "notes.md").exists(), "references": (kn / "refs.json").exists(),
                          "agent_notes": (kn / "agent_notes.md").exists()}}


# ----------------------------------------------------------------------------------------------- skills & knowledge

@tool("Load a skill: distilled know-how for one kind of task (see the skill index in the system prompt). Returns the "
      "instructions and the skill's reference files (read them with read_skill_file when the instructions say so).",
      name=("string", "skill name from the index"))
def load_skill(name):
    s = skills.find(name)
    return {"skill": s.name, "instructions": s.body, "files": s.files()}


@tool("Read one reference file of a skill (a path listed by load_skill, e.g. 'references/checks.md').",
      name=("string", "skill name"), path=("string", "file path inside the skill"))
def read_skill_file(name, path):
    return {"skill": name, "path": path, "text": skills.read_file(name, path)[:20000]}


@tool("Read the knowledge base. name: '' to list documents; 'ep1' (OSC broadband nebula video workflow), "
      "'ep2' (OSC galaxy workflow), 'filters' (what the night's filter means for processing, e.g. multiband), "
      "'comets' (comet stacking method and lessons), 'steps' (every PixInsight step and its parameters), 'checklists' "
      "(what good looks like at each stage), 'pitfalls', or 'targets/<NAME>' (reference notes for a target), "
      "'targets/<NAME>/agent' (lessons from earlier runs).",
      name=("string", "document name, '' to list"))
def read_knowledge(name=""):
    k = config.KNOWLEDGE
    alias = {"ep1": "videos/ep1-osc-broadband-nebula.md", "ep2": "videos/ep2-osc-galaxy.md",
             "ep3": "videos/ep3-mono-lrgb-broadband.md", "ep4a": "videos/ep4a-mono-hoo.md",
             "ep4b": "videos/ep4b-osc-ho-dualband.md", "ep5a": "videos/ep5a-mono-sho.md", "ep5b": "videos/ep5b-osc-sho.md",
             "ep6": "videos/ep6-multinight-selection.md",
             "steps": "pipeline_steps.md", "checklists": "checklists.md", "pitfalls": "pitfalls.md",
             "filters": "filters.md", "comets": "comets.md"}
    if not name:
        docs = sorted(p.relative_to(k).as_posix() for p in k.rglob("*.md"))
        return {"documents": docs, "aliases": alias}
    m = re.match(r"targets/(.+?)(/agent)?$", name)
    if m:
        f = k / "targets" / references.slug(m.group(1)) / ("agent_notes.md" if m.group(2) else "notes.md")
    else:
        f = _inside(k, k / alias.get(name, name))
        if f is None:
            return {"error": f"{name} is not in the knowledge base"}
    if not f.is_file():
        return {"error": f"{name} does not exist (list the documents with name='')"}
    return {"document": f.resolve().relative_to(k.resolve()).as_posix(), "text": f.read_text(encoding="utf-8")[:20000]}


@tool("Show a recipe: its stages and every step with default parameters (ids are what run_stage overrides use).",
      recipe=("string", "recipe name: " + " | ".join(pipeline.RECIPES)))
def show_recipe(recipe):
    return pipeline.RECIPES[recipe]


@tool("Fetch (if needed) and summarise top-rated AstroBin works of the target: best (IOTD/Top Pick) and peer "
      "(colour-sensor, broadband) groups, with numeric fingerprints and the reference notes if written.",
      target=("string", "target name"), refresh=("boolean", "re-download even if cached", False))
def get_references(target, refresh=False):
    d = resolve(target)
    doc = actions.references_for(d, refresh=refresh)

    def short(e):
        return {k: e.get(k) for k in ("title", "author", "likes", "iotd", "top_pick", "integration_h", "url", "file")}
    fp = {g: metrics.summarize([e["fingerprint"] for e in doc.get(g, []) if e.get("fingerprint")])
          for g in ("best", "peer")}
    notes = config.KNOWLEDGE / "targets" / references.slug(d.name) / "notes.md"
    return {"peer_mode": doc.get("peer_mode", "broadband"), "best": [short(e) for e in doc.get("best", [])],
            "peer": [short(e) for e in doc.get("peer", [])], "fingerprint_medians": fp,
            "notes": notes.read_text(encoding="utf-8")[:8000] if notes.exists() else None}


# ----------------------------------------------------------------------------------------------- doing

@tool("Import a folder of raw frames (any capture program or layout; types read from FITS headers) into "
      "In Processing/<night>/<target>, each target with matching darks/bias/flats: from the folder itself first, else "
      "from the calibration library. A folder with calibration frames only goes to the library and completes the "
      "targets that lack them. source: the folder (default: new folders put in the data root). Default is a dry run "
      "that returns the plan; apply=true executes it (only when the user's task asks for it). refresh=true gives "
      "staged targets the library frames they lack.",
      apply=("boolean", "execute the plan", False), refresh=("boolean", "complete staged targets from the library", False),
      source=("string", "folder to import instead of the data root", False),
      copy=("boolean", "copy lights instead of moving them", False))
def organize(apply=False, refresh=False, source=None, copy=False):
    from .. import organize as org
    plan, notes = org.build_plan(sources=[source] if source else None, refresh=refresh)
    log = []
    if apply:
        org.apply_plan(plan, move_lights=not copy, log=log.append)
    return {"applied": apply, "plan": org.summary(plan), "notes": notes, "log": log[-50:]}


@tool("Calibrate/register/integrate the target with WBPP (headless, 5-20 min). Only needed when no master exists.",
      target=("string", "target name"))
def stack(target):
    d = resolve(target)
    if wbpp.masters(d):
        return {"skipped": "master already exists", "masters": [p.as_posix() for p in wbpp.masters(d)]}
    _ctx.spend()
    r = wbpp.run(d)
    r["highlights"] = r.get("highlights", [])[-15:]
    return r


@tool("Comet targets only: stack WBPP's registered frames twice - on the stars and on the moving nucleus - with "
      "per-frame background, photometric scaling, cloud and satellite-trail rejection and StarXTerminator star "
      "removal (10-15 min). Produces Post/comet_stack.fits (comet layer) + Post/stars_linear.fits, then run the "
      "'comet' recipe with run_stage(recipe='comet'). Look at Post/weights.jpg via look(images=['weights']) if needed.",
      target=("string", "target name or folder"),
      reuse_sxt=("boolean", "reuse the star removal of an earlier run (after changing later steps)", False))
def comet_stack(target, reuse_sxt=False):
    d = resolve(target)
    _ctx.spend()
    return actions.comet_stack(d, reuse_sxt=reuse_sxt)


def _compact_stage(rec):
    steps = []
    for s in rec["steps"]:
        info = json.dumps(s.get("info"), ensure_ascii=False, default=str)
        steps.append({"op": s["op"], "seconds": round(s["seconds"], 1), "info": info[:700]})
    return {"stage": rec["stage"], "seconds": rec["seconds"], "steps": steps, "metrics": rec.get("metrics"),
            "previews": rec.get("previews"), "noise": rec.get("noise")}


@tool("Run one pipeline stage of the target's recipe in headless PixInsight and return per-step info, metrics "
      "and preview paths. Re-running a stage discards later stages. The user's saved parameter edits (user_params "
      "in inspect_target) always apply; overrides go on top of them: {step_id: {param: value, "
      "'params': {...}, 'enabled': false}}; extra_steps: steps appended at the end of the stage (same format as "
      "the recipe, e.g. {'id':'sat3','op':'saturation','boost':0.58}); replace_steps: a full step list to use "
      "instead of the recipe's (advanced). Use read_knowledge('steps') for every op and parameter.",
      target=("string", "target name"), stage=("string", "stage name (see show_recipe)"),
      overrides=("object", "per-step overrides keyed by step id", False),
      extra_steps=("array", "steps appended to the stage", False),
      replace_steps=("array", "replacement step list", False),
      recipe=("string", "only for the first stage: force a recipe (" + " | ".join(pipeline.RECIPES) + ")", False))
def run_stage(target, stage, overrides=None, extra_steps=None, replace_steps=None, recipe=None):
    d = resolve(target)
    w = pipeline.Work(d, recipe)
    if recipe:
        w.use_recipe(recipe)
    spec = w.stage(stage)
    if replace_steps or extra_steps:
        spec = dict(spec)
        steps = list(replace_steps) if replace_steps else list(spec["steps"])
        steps += list(extra_steps or [])
        for i, s in enumerate(steps):
            s.setdefault("id", f"x{i}")
        spec["steps"] = steps
        w.recipe = [spec if s["stage"] == stage else s for s in w.recipe]
    for earlier in pipeline.with_missing_inputs(w, [stage])[:-1]:   # its input was cleaned up to free disk space
        _ctx.spend()
        pipeline.run_stage(w, earlier)
    _ctx.spend()
    rec = pipeline.run_stage(w, stage, overrides or {})
    return _compact_stage(rec)


# ----------------------------------------------------------------------------------------------- judging

VISION_SYSTEM = ("你是资深深空天文摄影后期评审，熟悉 PixInsight 和彩色相机(OSC)宽带成像。根据图像客观地回答问题，"
                 "指出具体问题位置和程度，不要客套。若要求 JSON，只输出 JSON。")


def _preview_path(d, name):
    if name.startswith("ref:"):        # ref:peer_00 / ref:best_02
        root = config.KNOWLEDGE / "targets" / references.slug(d.name) / "refs"
        p = root / f"{name[4:]}.jpg"
    else:
        root = d / "Post"
        fname = name if name.endswith(".jpg") else f"{name}.jpg"
        p = root / "previews" / fname
        if not p.exists():                      # files written next to the checkpoints (e.g. comet weights.jpg)
            p = root / fname
    p = _inside(root, p)
    if p is None or not p.is_file():
        raise FileNotFoundError(f"no image {name} in {root}")
    return p


@tool("Let the vision model look at images and answer a question (your eyes). images: preview names from "
      "Post/previews without .jpg (e.g. '10_gc_model', '10a_after_cc', '10_linear', '20_stretched', '30_starless', "
      "'31_stars', '40_starless_final', '50_final_2k') and/or reference thumbnails 'ref:peer_00', 'ref:best_01'. "
      "Ask concrete questions (e.g. 'Does the gradient model contain the shape of the galaxy?', 'Is the "
      "background neutral grey? Any colour cast?', 'Compare our image with the references: saturation, contrast, "
      "background darkness, star colour; what should change?'). Set want_json for structured verdicts.",
      target=("string", "target name"), images=("array", "list of image names (strings)"),
      question=("string", "what to judge"), want_json=("boolean", "ask for a JSON answer", False))
def look(target, images, question, want_json=False):
    d = resolve(target)
    imgs = [(n if isinstance(n, str) else n.get("name"), _preview_path(d, n if isinstance(n, str) else n.get("name")))
            for n in images]
    q = question + ("\n只输出一个 JSON 对象。" if want_json else "")
    ans = _ctx.llm.look(imgs, q, system=VISION_SYSTEM, want_json=want_json)
    return {"answer": ans}


@tool("Numeric comparison of a stage result (nonlinear stages) with the reference fingerprints: background level, "
      "median brightness, contrast, saturation, hue mix. Positive delta = ours is higher than the references.",
      target=("string", "target name"), stage=("string", "stage whose metrics to compare, e.g. 'combine'"),
      group=("string", "'peer' (same kind of equipment, default) or 'best'", False))
def compare_with_references(target, stage, group="peer"):
    d = resolve(target)
    w = pipeline.Work(d)
    rec = w.state["stages"].get(stage)
    if not rec:
        return {"error": f"stage {stage} has not run"}
    if rec.get("metrics", {}).get("linear"):
        return {"error": "linear data cannot be compared with finished references; use a nonlinear stage"}
    fps = references.fingerprints(d.name, group)
    if not fps:
        get_references(d.name)
        fps = references.fingerprints(d.name, group)
    # compare on the 8-bit preview, like the 8-bit reference thumbnails
    prev = [p for p in rec.get("previews", []) if p.endswith(".jpg") and "_stars" not in p]
    ours = metrics.analyze(prev[-1]) if prev else rec["metrics"]
    out = metrics.compare(ours, fps)
    out["subject_chroma"] = _chroma_vs_refs(d, w, prev[-1] if prev else None, group)
    return out


def _chroma_vs_refs(d, w, preview, group):
    """Subject colourfulness (Lab chroma, 90th percentile) ours vs references - the number for 'saturated enough?'.
    Ours: inside the catalogue ellipse when the object is small in our frame, else the whole frame. References: the
    larger of whole-frame and central-region values (their framing varies; the subject is the most colourful part)."""
    if not preview:
        return None
    cat = objects.lookup(d.name) or {}
    obj = w.state.get("object") or {}
    small = obj["fillFraction"] < 0.15 if obj.get("fillFraction") is not None else (cat.get("diameter") or 999) < 20
    stats = (w.state.get("stages", {}).get("combine") or w.state.get("stages", {}).get("starless") or {}).get("stats") or {}
    region = None
    if small and obj.get("cx") and stats.get("width"):
        region = (obj["cx"] / stats["width"], obj["cy"] / stats["height"], 1.3 * obj["semiMajorPx"] / stats["width"])
    ours = metrics.subject_chroma(preview, region)
    doc = references.load(d.name) or {}
    vals = []
    for e in doc.get(group, []):
        if e.get("file"):
            best = max((metrics.subject_chroma(e["file"], reg).get("chroma") or 0)
                       for reg in (None, (0.5, 0.5, 0.25), (0.5, 0.5, 0.1)))   # tiny targets in wide references
            if best > 0:
                vals.append(best)
    import statistics
    med = statistics.median(vals) if vals else None
    ratio = round(ours["chroma"] / med, 2) if med and ours.get("chroma") is not None else None
    return {"ours": ours.get("chroma"), "refs_median": med, "refs": vals, "ratio": ratio,
            "guide": "ratio 0.8-1.2 is on target; below 0.8 raise saturation (boost/passes) - colour noise is NXT's job"}


@tool("Extra export of the finished image cropped around the object (keeps the full-frame finals). Use for small "
      "targets that are lost in the full field (e.g. planetary nebulae). width/height in pixels of the full image "
      "(1.38\"/px: 1000 px ~ 23').",
      target=("string", "target name"), width=("integer", "crop width in px"), height=("integer", "crop height in px"))
def export_crop(target, width, height):
    _ctx.spend()
    return {"files": pipeline.export_crop(resolve(target), int(width), int(height))}


# ----------------------------------------------------------------------------------------------- memory & report

@tool("Record a lesson for this target (or 'general') that future runs should know, e.g. which parameters worked.",
      target=("string", "target name or 'general'"), text=("string", "the lesson, concise"))
def remember(target, text):
    if target == "general":
        f = config.KNOWLEDGE / "agent_lessons.md"
    else:
        f = config.KNOWLEDGE / "targets" / references.slug(resolve(target).name) / "agent_notes.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(f"- {time.strftime('%Y-%m-%d')}: {text.strip()}\n")
    return {"saved": f.as_posix()}


@tool("Finish the target: write Post/report.md (decisions, parameters, issues, comparison with references) and mark "
      "it finished. Call when the final image is acceptable or the budget is exhausted.",
      target=("string", "target name"), summary=("string", "what was done and why (Chinese)"),
      issues=("string", "remaining problems / what the user should check or reshoot", False))
def finish(target, summary, issues=""):
    d = resolve(target)
    w = pipeline.Work(d)
    if (d / "Post" / "50_final.xisf").exists() and not list((d / "Post").glob(f"{d.name}_*.png")):
        pipeline.export_final(d, ("png",))   # the user wants a PNG of every finished image
    finals = sorted(str(p) for p in (d / "Post").glob(f"{d.name}_*.*") if p.suffix.lower() in (".jpg", ".png", ".tif"))
    lines = [tr("# {target} 后期报告", target=d.name), "", tr("- 配方: {recipe}", recipe=w.state.get("recipe")),
             tr("- 完成时间: {time}", time=time.strftime("%Y-%m-%d %H:%M")),
             tr("- 成品: {files}", files=", ".join(finals) or tr("无")), "", tr("## 总结"), summary, ""]
    if issues:
        lines += [tr("## 待确认 / 问题"), issues, ""]
    lines += [tr("## 各阶段参数与指标"), ""]
    for name, rec in w.state.get("stages", {}).items():
        m = rec.get("metrics") or {}
        lines.append(f"### {name}  ({rec.get('seconds')} s)")
        lines.append(f"- overrides: `{json.dumps(rec.get('overrides'), ensure_ascii=False)}`")
        keep = {k: m.get(k) for k in ("background_level", "background_cast", "lum_median", "contrast_p99_p10",
                                      "signal_saturation_mean", "signal_hue_mix", "noise_hf") if k in m}
        lines.append(f"- metrics: `{json.dumps(keep, ensure_ascii=False)}`")
        lines.append("")
    rp = d / "Post" / "report.md"
    rp.write_text("\n".join(lines), encoding="utf-8")
    w.state["finished"] = time.strftime("%Y-%m-%d %H:%M")
    w.save()
    return {"report": rp.as_posix(), "finals": finals}
