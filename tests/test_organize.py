"""Importing frames: recognised by their headers in any layout, each target with matching calibration frames."""
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from astroflow import organize, settings

QUIET = {"log": lambda line: None}
ASI = {"INSTRUME": "ZWO ASI2600MC Air", "GAIN": 100, "OFFSET": 50, "XBINNING": 1}
NIKON = {"INSTRUME": "Nikon DSC D5100 (PTP mode)", "ISO": "3200", "SITELONG": -87.96, "XBINNING": 1}


def frame(path, **header):
    """A tiny FITS frame; header keys with '_' are written with '-' (SET_TEMP -> SET-TEMP)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    hdu = fits.PrimaryHDU(np.zeros((4, 6), dtype=np.uint16))
    for key, value in header.items():
        hdu.header[key.replace("_", "-")] = value
    hdu.writeto(path)
    return path


@pytest.fixture
def astro(tmp_settings):
    tmp, _ = tmp_settings
    s = settings.get()
    s.astro_root = (tmp / "Astro").as_posix()
    settings.save(s)
    return tmp / "Astro"


def _rows(sources=None, refresh=False):
    plan, notes = organize.build_plan(sources=sources, refresh=refresh)
    return plan, organize.summary(plan), notes


def test_frame_type_words():
    assert [organize.type_from_keyword(v) for v in ("Light Frame", "LIGHT", "Flat Field", "DARKFLAT", "Flat Dark",
                                                   "Bias Frame", "Offset", "Dark", "")] == \
        ["light", "light", "flat", "darkflat", "darkflat", "bias", "bias", "dark", None]
    assert [organize.type_from_name(n) for n in ("Light_M51_300.0s.fit", "Darks", "dark_flats", "LIGHT", "BIAS",
                                                 "Flatiron_01.fit", "Lightroom", "M51")] == \
        ["light", "dark", "darkflat", "light", "bias", None, None, None]


def test_dslr_folder_with_its_own_calibration(astro, tmp_path):
    """The case that failed: a DSLR session (ISO, no temperature) whose Dark/Bias/Flat sit next to the lights."""
    src = tmp_path / "Processed" / "Apr28" / "M51"
    for i in range(3):
        frame(src / "Light" / f"Light_M51_300.0s_Bin1_ISO3200_20250427-22{30 + i}09_000{i}.fit",
              IMAGETYP="Light", OBJECT="M51", EXPTIME=300.0, **NIKON)
        frame(src / "Dark" / f"Dark_300.0s_Bin1_ISO3200_20250428-00{30 + i}53_000{i}.fit",
              IMAGETYP="Dark", EXPTIME=300.0, **NIKON)
        frame(src / "Bias" / f"Bias_1.0ms_Bin1_ISO3200_20250428-02{10 + i}20_000{i}.fit",
              IMAGETYP="Bias", EXPTIME=0.001, **NIKON)
        frame(src / "Flat" / f"Flat_191.7ms_Bin1_ISO100_20250428-05{50 + i}45_000{i}.fit",
              IMAGETYP="Flat", EXPTIME=0.1917, **{**NIKON, "ISO": "100"})
    frame(src / "Output" / "calibrated" / "Light_M51_c.fit", IMAGETYP="Light", OBJECT="M51", EXPTIME=300.0,
          DATE_OBS="2025-04-28T03:28:04", **NIKON)                         # a WBPP product, not a raw frame
    frame(src / "masterDark_300s.fit", IMAGETYP="Master Dark", EXPTIME=300.0, DATE_OBS="2025-04-28T05:00:00", **NIKON)

    plan, (row,), notes = _rows([src])
    assert (row["kind"], row["target"], row["night"]) == ("target", "M51", "2025-04-27")
    assert [row[k]["count"] for k in ("lights", "darks", "bias", "flats")] == [3, 3, 3, 3]
    assert {row[k]["origin"] for k in ("darks", "bias", "flats")} == {"import"}
    assert row["darks"]["detail"] == "3 × 300 s · ISO 3200" and row["flats"]["detail"] == "3 × 192 ms · ISO 100"
    assert row["warnings"] == [] and notes == [] and row["to_copy"] == 12

    organize.apply_plan(plan, move_lights=False, **QUIET)
    dest = astro / "In Processing" / "2025Apr27" / "M51"
    assert sorted(p.name for p in dest.iterdir()) == ["Bias", "Dark", "Flat", "Light", "calibration_manifest.txt"]
    assert len(list((src / "Light").iterdir())) == 3                         # copied: the originals stay
    again = _rows([src])[1][0]
    assert (again["exists"], again["to_copy"]) == (True, 0)                  # importing again copies nothing


def test_asiair_autorun_export(astro, tmp_path):
    auto = tmp_path / "card" / "Autorun"
    cooled = {**ASI, "SET_TEMP": -10.0, "CCD_TEMP": -10.1}
    for i in range(2):
        frame(auto / "Light" / "M8" / f"Light_M8_300.0s_Bin1_gain100_20260517-23{10 + i}00_000{i}.fit",
              IMAGETYP="Light", OBJECT="M 8", EXPTIME=300.0, **cooled)
        frame(auto / "Dark" / f"Dark_300.0s_Bin1_gain100_20260518-01{10 + i}00_000{i}.fit", IMAGETYP="Dark",
              EXPTIME=300.0, **cooled)
        frame(auto / "Dark" / f"Dark_120.0s_Bin1_gain100_20260518-01{20 + i}00_000{i}.fit", IMAGETYP="Dark",
              EXPTIME=120.0, **cooled)
        frame(auto / "Flat" / f"Flat_2.0s_Bin1_gain100_20260518-02{10 + i}00_000{i}.fit", IMAGETYP="Flat",
              EXPTIME=2.0, **cooled)
        frame(auto / "Bias" / f"Bias_1.0ms_Bin1_gain100_20260518-02{20 + i}00_000{i}.fit", IMAGETYP="Bias",
              EXPTIME=0.001, **cooled)
    frame(auto / "Preview" / "Preview_M8_5.0s_20260517-220000.fit", IMAGETYP="Light", OBJECT="M8", EXPTIME=5.0,
          **cooled)

    _, (row,), notes = _rows([auto])
    assert (row["target"], row["night"]) == ("M8", "2026-05-17")              # 'M 8' -> 'M8'; after midnight -> evening
    assert row["darks"]["detail"] == "2 × 300 s · 增益 100 · -10 °C"          # the 120 s darks are not for these lights
    assert [row[k]["count"] for k in ("bias", "flats")] == [2, 2] and row["warnings"] == []
    assert any("2 × 120 s" in n and "没有用上" in n for n in notes)
    assert any("预览" in n for n in notes)


def test_nina_layout_mono_filters_and_dark_flats(astro, tmp_path):
    night = tmp_path / "NINA" / "NGC 7000" / "2024-01-05"
    mono = {"INSTRUME": "ZWO ASI294MM Pro", "GAIN": 120, "OFFSET": 30, "SET_TEMP": -10.0}
    for i, filt in enumerate(("Ha", "Ha", "OIII")):
        frame(night / "LIGHT" / f"2024-01-05_21-3{i}-12_{filt}_-10.00_300.00s_000{i}.fits", IMAGETYP="LIGHT",
              FILTER=filt, EXPTIME=300.0, **mono)                             # no OBJECT: the folder names it
    frame(night / "DARK" / "2024-01-06_06-00-00_-10.00_300.00s_0001.fits", IMAGETYP="DARK", EXPTIME=300.0, **mono)
    frame(night / "FLAT" / "2024-01-06_07-00-00_Ha_1.50s_0001.fits", IMAGETYP="FLAT", FILTER="Ha", EXPTIME=1.5,
          **mono)
    frame(night / "DARKFLAT" / "2024-01-06_07-10-00_1.50s_0001.fits", IMAGETYP="DARKFLAT", EXPTIME=1.5, **mono)

    _, (row,), _ = _rows([night.parent])
    assert (row["target"], row["night"]) == ("NGC 7000", "2024-01-05")
    assert row["flats"]["detail"] == "1 × 1.5 s · 增益 120 · -10 °C · Ha"
    assert row["darks"]["count"] == 2                                        # the dark and the dark flat
    assert "缺少这一晚的平场：2024-01-05，滤镜 OIII" in row["warnings"]
    assert not any("偏置" in w for w in row["warnings"])                     # dark flats calibrate the flats


def test_library_fallback_takes_the_closest_set_point(astro, tmp_path):
    lib = astro / "Dark Library"
    for t, n in ((-10.0, 3), (-15.0, 2)):
        for i in range(n):
            frame(lib / f"{t:g}" / f"Dark_300.0s_{t:g}_20260101-01000{i}.fit", IMAGETYP="Dark", EXPTIME=300.0,
                  SET_TEMP=t, **ASI)
    frame(astro / "Bias Library" / "Bias_20260101-020000.fit", IMAGETYP="Bias", EXPTIME=0.001, SET_TEMP=-10.0, **ASI)

    def plan_for(set_temp):
        src = tmp_path / f"night{set_temp:g}"
        frame(src / f"Light_M42_300.0s_20260301-21{abs(int(set_temp)):02d}00_0001.fit", IMAGETYP="Light",
              OBJECT="M42", EXPTIME=300.0, SET_TEMP=set_temp, **ASI)
        return _rows([src])[1][0]

    row = plan_for(-10.0)
    assert (row["darks"]["count"], row["darks"]["origin"], row["bias"]["origin"]) == (3, "library", "library")
    assert "缺少这一晚的平场：2026-03-01" in row["warnings"]
    row = plan_for(-9.5)
    assert row["darks"]["detail"] == "3 × 300 s · 增益 100 · -10 °C"
    assert any("容差内" in w for w in row["warnings"])
    row = plan_for(-12.0)
    assert row["darks"]["count"] == 0 and any(w.startswith("缺少暗场") for w in row["warnings"])


def test_frames_without_imagetyp_take_the_folder_name_and_keep_it(astro, tmp_path):
    src = tmp_path / "dslr" / "Orion"
    common = {"INSTRUME": "Canon EOS 6D", "ISO": "1600", "EXPTIME": 120.0}
    frame(src / "Lights" / "IMG_0001.fit", OBJECT="M42", DATE_LOC="2026-01-10T21:00:00", **common)
    frame(src / "Darks" / "IMG_0101.fit", DATE_LOC="2026-01-10T23:30:00", **common)
    plan, (row,), _ = _rows([src])
    assert (row["lights"]["count"], row["darks"]["count"]) == (1, 1)
    organize.apply_plan(plan, move_lights=False, **QUIET)
    copied = astro / "In Processing" / "2026Jan10" / "M42" / "Dark" / "IMG_0101.fit"
    assert fits.getheader(copied)["IMAGETYP"] == "Dark"                       # WBPP sorts frames by this keyword
    assert "IMAGETYP" not in fits.getheader(src / "Darks" / "IMG_0101.fit")  # the original is untouched


def test_calibration_only_folder_goes_to_the_library_and_completes_targets(astro, tmp_path):
    target = astro / "In Processing" / "2026Oct09" / "IC 1805"
    cooled = {**ASI, "SET_TEMP": -10.0}
    frame(target / "Light" / "Light_IC1805_300.0s_20261009-220000_0001.fit", IMAGETYP="Light", OBJECT="IC 1805",
          EXPTIME=300.0, **cooled)
    shot_later = tmp_path / "ASIAIR" / "Dark"
    for i in range(2):
        frame(shot_later / f"Dark_300.0s_Bin1_gain100_20261012-10{i}000_000{i}.fit", IMAGETYP="Dark", EXPTIME=300.0,
              **cooled)

    plan, rows, _ = _rows([shot_later])
    assert [(r["kind"], r["target"]) for r in rows] == [("library", "校准帧库"), ("fill", "IC 1805")]
    assert rows[1]["darks"]["origin"] == "import" and rows[1]["to_copy"] == 2
    organize.apply_plan(plan, move_lights=False, **QUIET)
    assert len(list((astro / "Dark Library" / "300s" / "-10degree").glob("*.fit"))) == 2
    assert len(list((target / "Dark").glob("*.fit"))) == 2
    assert "from=import" in (target / "calibration_manifest.txt").read_text(encoding="utf-8")
    assert [r["kind"] for r in _rows([shot_later])[1]] == ["library"]       # the target has its darks now
    assert _rows([astro / "Dark Library"])[1] == []                          # the library is not added to itself


def test_refresh_completes_staged_targets_from_the_library(astro):
    target = astro / "In Processing" / "2026Oct09" / "NGC 246"
    frame(target / "Light" / "Light_NGC246_300.0s_20261009-230000_0001.fit", IMAGETYP="Light", OBJECT="NGC 246",
          EXPTIME=300.0, SET_TEMP=-10.0, **ASI)
    frame(astro / "Dark Library" / "Dark_300.0s_20261010-090000_0001.fit", IMAGETYP="Dark", EXPTIME=300.0,
          SET_TEMP=-10.0, **ASI)
    _, rows, _ = _rows(refresh=True)
    assert [(r["kind"], r["darks"]["origin"]) for r in rows] == [("fill", "library")]


def test_one_object_typed_differently_on_two_nights_is_one_target():
    def name(obj):
        return organize.target_of({"object": obj, "path": Path("x/y.fits"), "root": Path("x")})
    assert {name(o) for o in ("M 42", "m42", "Messier 42", "M42")} == {"M42"}
    assert name("ngc 6334") == "NGC 6334" and name("NGC6334") == "NGC6334" and name("sh2-240") == "Sh2-240"
    assert name("IC1805 Heart") == "IC1805 Heart" and name("Comet C/2025 R3") == "Comet C2025 R3"
