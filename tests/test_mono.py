"""Mono-camera targets: one WBPP master per filter, and the mono LRGB recipes that start from them."""
import os
import time

from astroflow import mono, pipeline, storage
from astroflow.services import targets

MASTER = "masterLight_BIN-1_6248x4176_EXPOSURE-300.00s_FILTER-{}_{}.xisf"


def stacked(d, filters, kind="mono", autocrop=False):
    m = d / "Output" / "master"
    m.mkdir(parents=True, exist_ok=True)
    for f in filters:
        (m / MASTER.format(f, kind)).write_bytes(b"x")
        if autocrop:
            (m / MASTER.format(f, kind).replace(".xisf", "_autocrop.xisf")).write_bytes(b"x")
    return d


def test_filter_names_map_to_channels():
    assert [mono.channel(f) for f in ("L", "Lum", "Luminance", "Red", "ZWO G", "Antlia V-Pro B", "Duo", "")] == \
        ["L", "L", "L", "R", "G", "B", None, None]
    assert [mono.channel(f) for f in ("Ha", "H-alpha", "Ha 7nm", "OIII", "O3", "Antlia SII 3nm", "S2")] == \
        ["H", "H", "H", "O", "O", "S", "S"]


def test_masters_by_channel_prefer_autocrop_and_skip_other_filters(tmp_path):
    d = stacked(tmp_path / "M51", ["Lum", "Red", "Green", "Blue"], autocrop=True)
    stacked(d, ["Ha", "Duo"])
    found = mono.masters(d)
    assert sorted(found) == ["B", "G", "H", "L", "R"] and found["L"].name.endswith("_autocrop.xisf")
    assert mono.is_rgb(found)


def test_colour_camera_masters_are_not_mono(tmp_path):
    d = stacked(tmp_path / "M51", ["NoFilter"], kind="RGB")
    assert mono.masters(d) == {} and not pipeline.is_mono(d)
    assert pipeline.default_recipe(d) == ("osc_galaxy", "galaxy")


def test_mono_masters_choose_the_mono_recipe_by_object_type(tmp_path):
    assert pipeline.default_recipe(stacked(tmp_path / "M51", "LRGB")) == ("mono_lrgb_galaxy", "galaxy")
    assert pipeline.default_recipe(stacked(tmp_path / "M8", "RGB")) == ("mono_lrgb_nebula", "emission_nebula")
    unknown = stacked(tmp_path / "Field 7", "LRGB")
    assert pipeline.default_recipe(unknown)[0] is None                # the user picks one of the mono recipes
    assert pipeline.Work(unknown).state["recipe"] == "mono_lrgb_nebula"
    s = targets.summary(unknown)
    assert s["filter_class"] == "mono_lrgb" and s["master"]


def test_a_mono_stage_reads_each_filter_and_writes_rgb_and_l(tmp_path, monkeypatch):
    d = stacked(tmp_path / "M51", "RGB")                              # no L: the runner makes it from R, G and B
    w = pipeline.Work(d)
    assert w.master().name == MASTER.format("R", "mono") and w.checkpoint("master:G").name == MASTER.format("G", "mono")
    sent = {}

    def fake_run_job(job, **kw):
        sent.update(job)
        return {"steps": [], "saved": [], "previews": []}

    monkeypatch.setattr(pipeline.pi, "run_job", fake_run_job)
    pipeline.run_stage(w, "channels")
    assert sorted(sent["aux"]) == ["B", "G"] and sent["input"].endswith(MASTER.format("R", "mono"))
    assert {s["window"]: s["path"].rsplit("/", 1)[1] for s in sent["save"]} == {"main": "10_rgb.xisf", "L": "10_lum.xisf"}
    bg = next(s for s in sent["steps"] if s["id"] == "dbe")
    assert bg["each"] == ["L", "main", "G", "B"] and bg["saveModel"].endswith("10_dbe_model_{window}.jpg")


def test_mono_checkpoints_are_rebuilt_and_cleaned_like_the_others(tmp_path):
    w = pipeline.Work(stacked(tmp_path / "M51", "LRGB"))
    assert pipeline.with_missing_inputs(w, ["stretch"]) == ["channels", "color", "lum", "stretch"]
    assert {"10_rgb.xisf", "10_lum.xisf", "11_rgb.xisf", "11_lum.xisf"} <= storage._checkpoint_names()


def test_a_new_stack_of_any_filter_makes_the_stages_stale(tmp_path):
    d = stacked(tmp_path / "M51", "LRGB")
    old = time.time() - 3600
    for p in (d / "Output" / "master").iterdir():
        os.utime(p, (old, old))
    ran = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(old + 60))
    state = {"recipe": "mono_lrgb_galaxy", "stages": {"channels": {"time": ran}}}
    assert not pipeline.stages_stale(d, state)
    (d / "Output" / "master" / MASTER.format("B", "mono")).write_bytes(b"y")     # B stacked again
    assert pipeline.stages_stale(d, state)
