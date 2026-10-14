"""Narrowband data (videos ep4, ep5): mono H / O / S masters, a colour camera's two dual-band filter sets stacked apart,
the recipes chosen from them; and frames whose paths PixInsight's command line would garble."""
import json

import numpy as np
from astropy.io import fits

from astroflow import dualband, multinight, organize, pipeline, settings, wbpp
from astroflow.services import targets

MONO = "masterLight_BIN-1_6248x4176_EXPOSURE-300.00s_FILTER-{}_mono.xisf"
OSC = "masterLight_BIN-1_6248x4176_EXPOSURE-300.00s_FILTER-NoFilter_RGB_BAND-{}.xisf"


def masters(d, names):
    m = d / "Output" / "master"
    m.mkdir(parents=True, exist_ok=True)
    for n in names:
        (m / n).write_bytes(b"x")
    return d


def stages(d):
    return [s["stage"] for s in pipeline.recipe_stages(pipeline.Work(d).state["recipe"], d)]


def test_mono_lines_choose_the_palette_and_rgb_brings_its_own_stars(tmp_path):
    hoo = masters(tmp_path / "NGC 6992", [MONO.format(c) for c in "HO"])
    assert pipeline.default_recipe(hoo) == ("mono_hoo_nebula", "supernova_remnant")
    assert "rgb_stars" not in stages(hoo)
    masters(hoo, [MONO.format(c) for c in "RGB"])                     # R, G, B shot too: their stars replace the HOO ones
    assert "rgb_stars" in stages(hoo) and pipeline.detected_class(hoo) == "mono_hoo"
    sho = masters(tmp_path / "M16", [MONO.format(c) for c in ("SII", "Ha", "OIII")])
    assert pipeline.default_recipe(sho) == ("mono_sho_nebula", "emission_nebula")
    assert pipeline.Work(sho).master().name == MONO.format("Ha")          # H is what the others are registered onto


def test_two_dual_band_masters_make_sho(tmp_path):
    d = masters(tmp_path / "C 50", [OSC.format("HO"), OSC.format("SO"), OSC.format("HO").replace(".xisf", "_autocrop.xisf")])
    found = dualband.masters(d)
    assert set(found) == {"HO", "SO"} and found["HO"].name.endswith("_autocrop.xisf")
    assert pipeline.default_recipe(d)[0] == "osc_sho_nebula" and targets.summary(d)["filter_class"] == "osc_sho"
    assert pipeline.Work(d).checkpoint("master:SO").name == OSC.format("SO")


def night(root, name, filter_class):
    d = root / "In Processing" / name / "NGC 7000"
    for kind in ("Light", "Flat"):
        p = d / kind / f"{kind}_{name}.fit"
        p.parent.mkdir(parents=True, exist_ok=True)
        fits.PrimaryHDU(np.zeros((4, 6), np.uint16)).writeto(p)
    (d.parent / "session.json").write_text(json.dumps({"filter_class": filter_class}), encoding="utf-8")
    return d


def test_nights_through_two_dual_band_filters_are_stacked_per_filter(tmp_settings):
    tmp, _ = tmp_settings
    s = settings.get()
    s.astro_root = (tmp / "Astro").as_posix()
    settings.save(s)
    a = night(tmp / "Astro", "2026Nov29", "osc_multiband")
    b = night(tmp / "Astro", "2026Nov30", "osc_so")
    dest = multinight.combine([a, b], log=lambda line: None)
    names = sorted(p.relative_to(dest).as_posix() for k in ("Light", "Flat") for p in (dest / k).rglob("*.fit"))
    assert names == ["Flat/BAND_HO/NIGHT_2026Nov29/Flat_2026Nov29.fit", "Flat/BAND_SO/NIGHT_2026Nov30/Flat_2026Nov30.fit",
                     "Light/BAND_HO/NIGHT_2026Nov29/Light_2026Nov29.fit", "Light/BAND_SO/NIGHT_2026Nov30/Light_2026Nov30.fit"]
    assert "keywords=NIGHT pre;BAND post" in wbpp.wbpp_args(dest)
    assert pipeline.default_recipe(dest)[0] == "osc_sho_nebula"           # before stacking: from session.json
    c = night(tmp / "Astro", "2026Dec01", "osc_multiband")                 # the same filter every night: one master
    one = multinight.combine([a, c], log=lambda line: None)
    assert not multinight.has_bands(one) and "keywords=NIGHT pre" in wbpp.wbpp_args(one)


def test_frames_with_non_ascii_paths_reach_wbpp_through_ascii_links(tmp_path, monkeypatch):
    d = tmp_path / "天文" / "M42"
    for name in ("M 42_LIGHT_L_300.00s_-10.00℃_0000.fits", "M 42_LIGHT_L_300.00s_-10.00℃_0001.fits"):
        p = d / "Light" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    monkeypatch.setattr(wbpp.sys, "platform", "win32")
    monkeypatch.setattr(wbpp, "_stage_root", lambda target: tmp_path / "stage")
    with wbpp._ascii_input(d) as (root, output):
        assert str(root).isascii() and str(output).isascii()
        assert sorted(p.name for p in (root / "Light").iterdir()) == ["M 42_LIGHT_L_300.00s_-10.00C_0000.fits",
                                                                        "M 42_LIGHT_L_300.00s_-10.00C_0001.fits"]
        assert all(a in wbpp.wbpp_args(d, frames_root=root, output=output)[1] for a in ("dir=", "/Light"))
        (output / "master").mkdir(parents=True)
        (output / "master" / "masterLight_BIN-1_FILTER-L_mono.xisf").write_bytes(b"m")
    assert (d / "Output" / "master" / "masterLight_BIN-1_FILTER-L_mono.xisf").exists()   # WBPP's work moved in
    assert not (tmp_path / "stage").exists() or not any((tmp_path / "stage").iterdir())
    assert (d / "Light" / "M 42_LIGHT_L_300.00s_-10.00℃_0000.fits").exists()               # the originals untouched


def test_ascii_paths_go_to_wbpp_as_they_are(tmp_path):
    d = tmp_path / "M42"
    (d / "Light").mkdir(parents=True)
    (d / "Light" / "L_0001.fits").write_bytes(b"x")
    with wbpp._ascii_input(d) as (root, output):
        assert (root, output) == (d, d / "Output")


def test_flats_far_from_half_full_scale_are_flagged(tmp_path):
    def flats(level):
        out = []
        for i in range(3):
            p = tmp_path / f"flat_{level}_{i}.fits"
            fits.PrimaryHDU(np.full((40, 60), int(level * 65535), np.uint16)).writeto(p)
            out.append({"path": p})
        return out
    assert abs(organize._flat_level(flats(0.5)) - 0.5) < 0.01
    assert organize._flat_level(flats(0.1)) < organize.FLAT_LEVEL[0]
    raw12 = flats(0.03)
    for f in raw12:                                    # 12-bit values never scaled to 16 bits: the share means nothing
        fits.PrimaryHDU(np.full((40, 60), 1200, np.uint16)).writeto(f["path"], overwrite=True)
    assert organize._flat_level(raw12) is None
