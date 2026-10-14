"""Looking after targets: disk space and cleaning up, archiving, several nights stacked as one, saved styles, share
pictures and processing everything."""
import json
import os
import shutil
import time
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits
from PIL import Image

from astroflow import framecheck, multinight, pipeline, settings, share, storage, wbpp
from astroflow.services import actions, presets, recipes, targets


@pytest.fixture
def root(tmp_settings):
    tmp, _ = tmp_settings
    s = settings.get()
    s.astro_root = (tmp / "Astro").as_posix()
    settings.save(s)
    return tmp / "Astro"


def frame(path, **header):
    path.parent.mkdir(parents=True, exist_ok=True)
    hdu = fits.PrimaryHDU(np.zeros((4, 6), dtype=np.uint16))
    for k, v in header.items():
        hdu.header[k.replace("_", "-")] = v
    hdu.writeto(path)
    return path


def write(path, size=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


def processed_target(root, night="2026May17", name="M8"):
    """A target after WBPP and the recipe: raw frames, WBPP's single frames and masters, stage checkpoints, finals."""
    d = root / "In Processing" / night / name
    for sub in ("Light", "Dark", "Flat"):
        frame(d / sub / f"{sub}_1.fit", IMAGETYP=sub)
    for sub in ("calibrated", "debayered", "registered"):
        write(d / "Output" / sub / "Light_1_c.xisf", 1000)
    write(d / "Output" / "master" / "masterLight_BIN-1_autocrop.xisf", 300)
    write(d / "Output" / "logs" / "wbpp.log", 5)
    for n in ("10_linear", "20_stretched", "30_starless", "31_stars", "40_starless_final", "41_stars_final", "50_final"):
        write(d / "Post" / f"{n}.xisf", 100)
    Image.new("RGB", (60, 40), (40, 10, 10)).save(d / "Post" / f"{name}_20260518.png")
    state = {"recipe": "osc_broadband_nebula", "master": (d / "Output" / "master" / "masterLight_BIN-1_autocrop.xisf").as_posix(),
             "stages": {s["stage"]: {"previews": [(d / "Post" / "previews" / f"{s['output']}.jpg").as_posix()]}
                        for s in pipeline.RECIPES["osc_broadband_nebula"]}}
    write(d / "Post" / "state.json").write_text(json.dumps(state), encoding="utf-8")
    write(d / "Post" / "previews" / "50_final.jpg", 10)
    return d


# ----------------------------------------------------------------------------------------------- disk space

def test_usage_and_cleaning_keep_what_cannot_be_made_again(root):
    d = processed_target(root)
    u = storage.usage(d)
    parts = {p["id"]: p for p in u["parts"]}
    assert parts["wbpp_frames"]["bytes"] == 3000 and parts["checkpoints"]["bytes"] == 600
    assert u["removable"] == 3600 and parts["masters"]["bytes"] == 305
    assert storage.clean(d, log=lambda line: None) == 3600
    assert sorted(p.name for p in (d / "Output").iterdir()) == ["logs", "master"]
    assert sorted(p.name for p in (d / "Post").glob("*.xisf")) == ["50_final.xisf"]
    assert len(list((d / "Light").iterdir())) == 1 and (d / "Post" / "M8_20260518.png").exists()
    assert storage.usage(d)["removable"] == 0


def test_a_stage_whose_input_was_cleaned_reruns_what_made_it(root):
    d = processed_target(root)
    storage.clean(d, log=lambda line: None)
    w = pipeline.Work(d)
    assert pipeline.with_missing_inputs(w, ["starless"]) == ["linear", "stretch", "stars", "starless"]
    assert pipeline.with_missing_inputs(w, ["linear"]) == ["linear"]


def test_a_comet_keeps_its_registered_frames(root):
    """The comet stack is made from them: it can always be made again without WBPP."""
    d = root / "In Processing" / "2026Apr10" / "C2025-R3"
    write(d / "Output" / "registered" / "a_r.xisf", 10)
    write(d / "Output" / "calibrated" / "a_c.xisf", 10)
    assert [p.name for p in storage.removable_paths(d)["wbpp_frames"]] == ["calibrated"]
    write(d / "Post" / "comet_stack.fits", 10)
    write(d / "Post" / "frames" / "a.fits", 10)
    rem = storage.removable_paths(d)
    assert [p.name for p in rem["wbpp_frames"]] == ["calibrated"] and rem["checkpoints"][0].name == "frames"


def test_cleaning_removes_only_what_wbpp_makes(root):
    d = processed_target(root)
    write(d / "Output" / "comet_aligned" / "mine.xisf", 50)                     # the user's own work
    write(d / "Output" / "notes.txt", 5)
    storage.clean(d, log=lambda line: None)
    assert sorted(p.name for p in (d / "Output").iterdir()) == ["comet_aligned", "logs", "master", "notes.txt"]


def test_archive_moves_the_target_and_its_records(root):
    d = processed_target(root)
    processed_target(root, name="M20")
    write(d.parent / "session.json").write_text('{"filter_class": "osc_multiband"}', encoding="utf-8")
    dest = storage.archive(d, log=lambda line: None)
    assert dest == root / "Processed" / "2026May17" / "M8" and not d.exists()
    state = json.loads((dest / "Post" / "state.json").read_text(encoding="utf-8"))
    assert state["master"].startswith(dest.as_posix())
    assert (dest.parent / "session.json").exists() and (d.parent / "session.json").exists()   # M20 still uses it
    assert targets.summary(dest)["filter_class"] == "osc_multiband"
    storage.archive(root / "In Processing" / "2026May17" / "M20", log=lambda line: None)
    assert not (root / "In Processing" / "2026May17").exists()                                 # the night is done
    with pytest.raises(ValueError):
        storage.archive(dest)


# ----------------------------------------------------------------------------------------------- several nights

def night(root, night_name, name="M101", flats=("f1",), darks=("d1", "d2")):
    d = root / "In Processing" / night_name / name
    for i in range(2):
        frame(d / "Light" / f"Light_{night_name}_{i}.fit", IMAGETYP="Light")
    for f in flats:
        frame(d / "Flat" / f"Flat_{night_name}_{f}.fit", IMAGETYP="Flat")
    for k in darks:
        frame(d / "Dark" / f"Dark_{k}.fit", IMAGETYP="Dark")
    (d / "calibration_manifest.txt").write_text("[lights]\nWARNING: 缺少偏置\n", encoding="utf-8")
    write(d.parent / "session.json").write_text('{"filter_class": "osc_broadband"}', encoding="utf-8")
    return d


def test_nights_are_combined_with_their_own_flats(root):
    a, b = night(root, "2026May17"), night(root, "2026May20")
    assert [n["night"] for n in multinight.candidates("M101")] == ["2026May17", "2026May20"]
    dest = multinight.combine([b, a], log=lambda line: None)
    assert dest == root / "In Processing" / "Multi-night" / "M101"
    names = sorted(p.relative_to(dest).as_posix() for k in multinight.KINDS for p in (dest / k).rglob("*.fit"))
    assert names == ["Dark/Dark_d1.fit", "Dark/Dark_d2.fit",                     # the same darks: shared
                     "Flat/NIGHT_2026May17/Flat_2026May17_f1.fit", "Flat/NIGHT_2026May20/Flat_2026May20_f1.fit",
                     "Light/NIGHT_2026May17/Light_2026May17_0.fit", "Light/NIGHT_2026May17/Light_2026May17_1.fit",
                     "Light/NIGHT_2026May20/Light_2026May20_0.fit", "Light/NIGHT_2026May20/Light_2026May20_1.fit"]
    s = targets.summary(dest)
    assert (s["nights"], s["night"], s["lights"], s["flats"]) == (["2026May17", "2026May20"], "", 4, 2)
    assert targets.calibration_warnings(dest) == ["2026May17：缺少偏置", "2026May20：缺少偏置"]
    args = wbpp.wbpp_args(dest)
    assert "keywords=NIGHT pre" in args and f"dir={(dest / 'Light').as_posix()}" in args
    assert "keywords=NIGHT pre" not in wbpp.wbpp_args(a)
    from astroflow import organize
    assert dest not in organize.staged_targets()                                  # it links frames, never gets any


def test_combining_again_follows_the_nights(root):
    a, b = night(root, "2026May17"), night(root, "2026May20", darks=("d3",))
    dest = multinight.combine([a, b], log=lambda line: None)
    assert (dest / "Dark" / "NIGHT_2026May20" / "Dark_d3.fit").exists()          # different darks: per night
    excluded = dest / "Excluded" / "Light" / "NIGHT_2026May17" / "Light_2026May17_0.fit"
    excluded.parent.mkdir(parents=True)
    (dest / "Light" / "NIGHT_2026May17" / "Light_2026May17_0.fit").rename(excluded)
    c = night(root, "2026May21")
    multinight.combine([a, b, c], log=lambda line: None)
    lights = sorted(p.name for p in (dest / "Light").rglob("*.fit"))
    assert "Light_2026May17_0.fit" not in lights and len(lights) == 5             # the excluded frame stays out
    multinight.combine([a, c], log=lambda line: None)
    assert not (dest / "Light" / "NIGHT_2026May20").exists()
    assert [n["night"] for n in multinight.info(dest)["nights"]] == ["2026May17", "2026May21"]
    with pytest.raises(ValueError):
        multinight.combine([a], log=lambda line: None)


# ----------------------------------------------------------------------------------------------- styles

def test_a_style_saved_from_one_target_applies_to_another(root):
    m101, m51 = processed_target(root, name="M101"), processed_target(root, name="M51")
    recipes.set_field(m101, "starless", "sat", "boost", 0.9)
    recipes.set_field(m101, "linear", "nxt", "params.denoise", 0.2)
    with pytest.raises(ValueError):
        presets.save("空", m51, "osc_galaxy")                                   # nothing edited yet
    p = presets.save("我的星系", m101, "osc_galaxy")
    assert (p["edits"], p["source"]) == (2, "M101")
    presets.apply("我的星系", m51, "osc_galaxy")
    assert recipes.overrides(m51) == {"starless": {"sat": {"boost": 0.9}}, "linear": {"nxt": {"params": {"denoise": 0.2}}}}
    with pytest.raises(ValueError):
        presets.apply("我的星系", m51, "osc_broadband_nebula")
    assert [x["name"] for x in presets.list_presets("osc_galaxy")] == ["我的星系"]
    assert presets.list_presets("comet") == []
    presets.delete("我的星系")
    assert presets.list_presets() == []


# ----------------------------------------------------------------------------------------------- share pictures

def test_share_crop_keeps_the_shape_and_never_upscales():
    assert share.crop_box((6000, 4000), "3:4") == (1500, 0, 4500, 4000)
    assert share.crop_box((6000, 4000), "16:9", [0, 0, 1, 1]) == (0, 312, 6000, 3688)
    x0, y0, x1, y1 = share.crop_box((6000, 4000), "1:1", [0.9, 0.9, 1.0, 1.0])
    assert x1 - x0 == y1 - y0 and x1 <= 6000 and y1 <= 4000
    assert share.output_size((0, 0, 3000, 4000), "3:4") == (1620, 2160)
    assert share.output_size((0, 0, 600, 800), "3:4") == (600, 800)


def test_share_picture_is_written_with_its_caption(root):
    d = processed_target(root)
    img = Image.new("RGB", (900, 600), (5, 5, 10))
    img.paste((200, 60, 80), (650, 200, 800, 400))                               # the nebula, off centre
    img.save(d / "Post" / "M8_20260518.png")
    crop = share.default_crop(d, "3:4")
    assert crop[0] > 0.3                                                         # moved towards the bright part
    cap = share.suggest(d, {"exposures_s": {300.0: 11}, "total_h": 0.92, "camera": "ZWO ASI2600MC Air"}, ["2026May17"])
    assert cap[0] == "M8 礁湖星云" and "11 × 300 s（55 分钟）" in cap[1] and cap[2] == "2026-05-17"
    plain = share.render(d, {"aspect": "3:4", "crop": crop})
    signed = share.render(d, {"aspect": "3:4", "crop": crop, "caption": cap, "signature": "© Ming"})
    assert plain.size == signed.size == (450, 600)
    assert np.asarray(plain).tobytes() != np.asarray(signed).tobytes()
    out = share.export(d, {"aspect": "16:9", "caption": cap, "signature": "© Ming"})
    assert out.parent == d / "Post" / "share" and Image.open(out).size == (900, 506)
    assert out.as_posix() not in targets.finals(d)                              # not mistaken for a final


# ----------------------------------------------------------------------------------------------- everything

def test_process_everything_knows_what_each_target_needs(root):
    done = processed_target(root, name="M8")
    fresh = root / "In Processing" / "2026May17" / "M101"
    frame(fresh / "Light" / "L.fit", IMAGETYP="Light")
    unknown = root / "In Processing" / "2026May17" / "Sh2-155"
    frame(unknown / "Light" / "L.fit", IMAGETYP="Light")
    comet = root / "In Processing" / "2026Apr10" / "C2025-R3"
    frame(comet / "Light" / "L.fit", IMAGETYP="Light")
    steps = {Path(t["path"]).name: actions.batch_step(t) for t in targets.list_targets()}
    assert steps == {"M8": ([], "已出图"), "M101": (["stack", "process"], None),
                     "Sh2-155": ([], "认不出是什么天体，先在“处理流程”里选配方"),
                     "C2025-R3": (["stack", "comet", "process"], None)}
    assert done.exists()


def test_a_multi_night_target_takes_no_space_for_its_frames(root):
    a, b = night(root, "2026May17"), night(root, "2026May20")
    dest = multinight.combine([a, b], log=lambda line: None)
    frames = next(p for p in storage.usage(dest)["parts"] if p["id"] == "frames")
    assert frames["files"] == 8 and frames["bytes"] == 0                         # all hard links to the nights
    assert next(p for p in storage.usage(a)["parts"] if p["id"] == "frames")["bytes"] > 0


def test_process_everything_leaves_nights_to_their_multi_night_target(root):
    a, b = night(root, "2026May17"), night(root, "2026May20")
    multinight.combine([a, b], log=lambda line: None)
    steps = {(Path(t["path"]).parent.name, t["name"]): actions.batch_step(t) for t in targets.list_targets()}
    assert steps[("Multi-night", "M101")] == (["stack", "process"], None)
    assert steps[("2026May17", "M101")][1].startswith("已合并")


def test_combining_never_touches_frames_it_did_not_link(root):
    a, b = night(root, "2026May17"), night(root, "2026May20")
    own = frame(multinight.combined_dir("M101") / "Light" / "mine.fit", IMAGETYP="Light")   # a folder made by hand
    with pytest.raises(FileExistsError):
        multinight.combine([a, b], log=lambda line: None)
    assert own.exists()


def test_combining_keeps_frames_of_nights_no_longer_on_disk(root):
    a, b, c = night(root, "2026May17"), night(root, "2026May20"), night(root, "2026May21")
    dest = multinight.combine([a, b], log=lambda line: None)
    storage.archive(a, log=lambda line: None)                                   # night A leaves In Processing
    multinight.combine([b, c], log=lambda line: None)                           # later: night C added
    lights = sorted(p.parent.name for p in (dest / "Light").rglob("*.fit"))
    assert lights.count("NIGHT_2026May17") == 2                                 # A's frames are still stacked
    assert multinight.info(dest)["nights"][0] == {**multinight.info(dest)["nights"][0], "missing": True}


def test_a_dropped_frame_without_another_copy_is_kept(root, monkeypatch):
    """Without hard links (exFAT) the combined target holds copies; one whose night lost the original is moved to
    Excluded, never deleted."""
    monkeypatch.setattr(multinight.os, "link", lambda src, dst: (_ for _ in ()).throw(OSError("no hard links")))
    a, b = night(root, "2026May17"), night(root, "2026May20")
    dest = multinight.combine([a, b], log=lambda line: None)
    (a / "Light" / "Light_2026May17_0.fit").unlink()                            # the original is gone
    c = night(root, "2026May21")
    shutil.rmtree(b)
    multinight.combine([a, c], log=lambda line: None)
    kept = dest / "Excluded" / "Light" / "NIGHT_2026May17" / "Light_2026May17_0.fit"
    assert kept.exists()                                                        # the last copy survived
    assert (dest / "Light" / "NIGHT_2026May20").exists()                        # night B vanished: its frames stay


def test_a_combining_cut_short_can_be_run_again(root, monkeypatch):
    a, b = night(root, "2026May17"), night(root, "2026May20")
    calls = []

    def flaky_link(src, dst, drop):
        calls.append(dst)
        if len(calls) == 3:
            raise KeyboardInterrupt("app closed")
        return real_link(src, dst, drop)

    real_link = multinight._link
    monkeypatch.setattr(multinight, "_link", flaky_link)
    with pytest.raises(KeyboardInterrupt):
        multinight.combine([a, b], log=lambda line: None)
    monkeypatch.setattr(multinight, "_link", real_link)
    dest = multinight.combine([a, b], log=lambda line: None)                   # recognised as ours: finishes
    assert multinight.info(dest)["complete"] is True and len(list((dest / "Light").rglob("*.fit"))) == 4


def test_restacking_makes_the_old_stages_stale(root):
    d = processed_target(root)
    state = json.loads((d / "Post" / "state.json").read_text(encoding="utf-8"))
    for rec in state["stages"].values():
        rec["time"] = "2026-05-18T10:00:00+00:00"
    (d / "Post" / "state.json").write_text(json.dumps(state), encoding="utf-8")
    master = d / "Output" / "master" / "masterLight_BIN-1_autocrop.xisf"
    old = time.mktime((2026, 5, 18, 0, 0, 0, 0, 0, -1))
    os.utime(master, (old, old))
    assert len(targets.summary(d)["stages_done"]) == 6
    os.utime(master, None)                                                     # WBPP ran again: a new master
    assert targets.summary(d)["stages_done"] == []
    assert pipeline.Work(d).state["stages"] == {}


def test_process_everything_restacks_after_frames_were_left_out(root):
    d = processed_target(root)
    master = d / "Output" / "master" / "masterLight_BIN-1_autocrop.xisf"
    state = json.loads((d / "Post" / "state.json").read_text(encoding="utf-8"))
    for rec in state["stages"].values():
        rec["time"] = "2000-01-01T00:00:00+00:00"
    (d / "Post" / "state.json").write_text(json.dumps(state), encoding="utf-8")
    os.utime(master, (time.mktime((1999, 1, 1, 0, 0, 0, 0, 0, -1)),) * 2)
    assert actions.batch_step(targets.summary(d)) == ([], "已出图")
    framecheck.exclude(d, ["Light_1.fit"])
    assert actions.batch_step(targets.summary(d)) == (["stack", "process"], None)


def test_excluding_never_overwrites(root):
    d = root / "In Processing" / "2026May17" / "M8"
    frame(d / "Light" / "a.fit", IMAGETYP="Light")
    frame(d / "Excluded" / "Light" / "a.fit", IMAGETYP="Light", OBJECT="older")
    assert framecheck.exclude(d, ["a.fit"]) == 0
    assert (d / "Light" / "a.fit").exists()
    assert fits.getheader(d / "Excluded" / "Light" / "a.fit")["OBJECT"] == "older"
