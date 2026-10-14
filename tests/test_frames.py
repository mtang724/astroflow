"""Frames of any kind (FITS, camera RAW) and checking single frames: star size and count are measured right, bad frames
are flagged, excluded frames leave the stack and come back."""
import struct
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from astroflow import framecheck, frameio, organize, settings
from astroflow.services import targets

RAF_SAMPLE = Path("F:/AstroPhotograph/Processed/Aug17/MilkyWay/Lights/DSCF3982.RAF")


def star_field(path, sigma=2.0, stars=300, sky=2000.0, seed=0, shape=(600, 900), header=None):
    """A mono 16-bit frame with Gaussian stars of this sigma (native pixels) on a noisy sky."""
    rng = np.random.default_rng(seed)
    img = np.full(shape, sky, np.float64)
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    pos = np.random.default_rng(1).uniform([20, 20], [shape[0] - 20, shape[1] - 20], (stars, 2))
    flux = np.random.default_rng(2).uniform(4000, 40000, stars)
    for (y, x), f in zip(pos, flux, strict=True):
        y0, x0 = int(y), int(x)
        sl = (slice(y0 - 12, y0 + 13), slice(x0 - 12, x0 + 13))
        img[sl] += f * np.exp(-((yy[sl] - y) ** 2 + (xx[sl] - x) ** 2) / (2 * sigma ** 2))
    img = rng.poisson(img).astype(np.float64) + rng.normal(0, 8, shape)
    hdu = fits.PrimaryHDU(np.clip(img, 0, 65535).astype(np.uint16))
    for k, v in (header or {}).items():
        hdu.header[k] = v
    path.parent.mkdir(parents=True, exist_ok=True)
    hdu.writeto(path, overwrite=True)
    return path


# ----------------------------------------------------------------------------------------------- RAW files

def _tiff(make, model, order="<"):
    """A minimal TIFF block whose first IFD holds Make and Model."""
    strings = make.encode() + b"\0" + model.encode() + b"\0"
    ifd = 8
    data = ifd + 2 + 2 * 12 + 4
    head = (b"II" if order == "<" else b"MM") + struct.pack(order + "HI", 42, ifd)
    entries = struct.pack(order + "H", 2)
    entries += struct.pack(order + "HHII", 0x010F, 2, len(make) + 1, data)
    entries += struct.pack(order + "HHII", 0x0110, 2, len(model) + 1, data + len(make) + 1)
    return head + entries + struct.pack(order + "I", 0) + strings


def test_camera_names_from_raw_headers(tmp_path):
    cases = {"a.nef": _tiff("NIKON CORPORATION", "NIKON D5100"),
             "b.cr2": _tiff("Canon", "Canon EOS 6D", ">"),
             "c.arw": _tiff("SONY", "ILCE-7M3"),
             "d.raf": b"FUJIFILMCCD-RAW 0201FF383501" + b"X-T30".ljust(32, b"\0") + b"\0" * 64,
             "e.cr3": b"\0\0\0\x18ftypcrx " + b"\0" * 12 + b"\0\0\0\x60CMT1" + _tiff("Canon", "Canon EOS R6"),
             "f.dng": b"not a tiff at all"}
    names = {}
    for name, data in cases.items():
        (tmp_path / name).write_bytes(data)
        names[name] = frameio.camera_name(tmp_path / name)
    assert names == {"a.nef": "NIKON D5100", "b.cr2": "Canon EOS 6D", "c.arw": "SONY ILCE-7M3",
                     "d.raf": "FUJIFILM X-T30", "e.cr3": "Canon EOS R6", "f.dng": ""}
    assert frameio.is_frame("x.NEF") and frameio.is_frame("x.fits") and not frameio.is_frame("x.jpg")


@pytest.mark.skipif(not RAF_SAMPLE.exists(), reason="needs the Fujifilm RAW sample")
def test_real_fujifilm_raw():
    h = frameio.header(RAF_SAMPLE)
    assert (h["INSTRUME"], h["EXPTIME"], h["ISO"], h["CFATYPE"]) == ("FUJIFILM X-T30", 15.0, 1600, "X-TRANS")
    assert h["DATE-LOC"] == "2025-08-18T00:39:33"                   # the camera's clock: local time
    img, b = frameio.read_luminance(RAF_SAMPLE)
    assert b == 3 and img.shape == (4170 // 3, 6246 // 3) and 0 < float(np.median(img)) < 0.1


def test_raw_frames_are_imported_by_folder_name(tmp_settings, tmp_path, monkeypatch):
    """A memory card: RAW files say nothing about their type; the folders do. Copies are byte for byte."""
    tmp, _ = tmp_settings
    s = settings.get()
    s.astro_root = (tmp / "Astro").as_posix()
    settings.save(s)
    card = tmp_path / "card" / "Orion"
    meta = {"INSTRUME": "FUJIFILM X-T30", "ISO": 1600, "NAXIS1": 6246, "NAXIS2": 4170}
    times = {"Lights": "2025-01-10T22:{:02d}:00", "Darks": "2025-01-11T01:{:02d}:00", "Flats": "2025-01-11T07:{:02d}:00"}
    for folder in times:
        for i in range(3):
            (card / folder).mkdir(parents=True, exist_ok=True)
            (card / folder / f"DSCF{folder[0]}{i}.RAF").write_bytes(f"{folder}{i}".encode())
    real_header = frameio.header

    def fake_header(path):
        if not frameio.is_raw(path):
            return real_header(path)
        folder = Path(path).parent.name
        i = int(Path(path).stem[-1])
        return {**meta, "EXPTIME": 0.01 if folder == "Flats" else 120.0, "DATE-LOC": times[folder].format(i)}

    monkeypatch.setattr(frameio, "header", fake_header)
    plan, notes = organize.build_plan(sources=[card])
    (row,) = organize.summary(plan)
    assert (row["target"], row["night"]) == ("Orion", "2025-01-10")
    assert [row[k]["count"] for k in ("lights", "darks", "flats")] == [3, 3, 3] and notes == []
    assert row["lights"]["detail"] == "3 × 120 s · ISO 1600"
    organize.apply_plan(plan, move_lights=False, log=lambda line: None)
    dest = tmp / "Astro" / "In Processing" / "2025Jan10" / "Orion"
    assert (dest / "Dark" / "DSCFD0.RAF").read_bytes() == b"Darks0"     # no header written into a RAW file
    assert targets.summary(dest)["lights"] == 3


# ----------------------------------------------------------------------------------------------- frame check

def test_star_size_and_count_are_measured(tmp_path):
    m, thumb = framecheck.measure(star_field(tmp_path / "a.fits", sigma=2.0))
    assert abs(m["fwhm_px"] - 2.3548 * 2.0) / (2.3548 * 2.0) < 0.15
    assert 200 <= m["stars"] <= 320 and m["ecc"] < 0.5
    assert thumb.dtype == np.uint8 and max(thumb.shape) <= framecheck.THUMB_SIDE
    blurred, _ = framecheck.measure(star_field(tmp_path / "b.fits", sigma=3.5))
    assert blurred["fwhm_px"] > 1.5 * m["fwhm_px"]


@pytest.fixture
def target(tmp_path):
    d = tmp_path / "In Processing" / "2026Jan01" / "M42"
    hdr = {"XPIXSZ": 3.76, "FOCALLEN": 560.0, "EXPTIME": 120.0}
    for i in range(6):
        star_field(d / "Light" / f"L{i}.fits", seed=i, header={**hdr, "DATE-OBS": f"2026-01-01T20:0{i}:00"})
    star_field(d / "Light" / "L6_cloud.fits", seed=6, stars=60, header={**hdr, "DATE-OBS": "2026-01-01T20:06:00"})
    star_field(d / "Light" / "L7_soft.fits", seed=7, sigma=3.6, header={**hdr, "DATE-OBS": "2026-01-01T20:07:00"})
    star_field(d / "Light" / "L8_moon.fits", seed=8, sky=4000, header={**hdr, "DATE-OBS": "2026-01-01T20:08:00"})
    return d


def test_bad_frames_are_flagged_and_can_be_excluded(target):
    r = framecheck.analyze(target, workers=2)
    flagged = {f["name"]: f["flags"] for f in r["frames"] if f["flags"]}
    assert set(flagged) == {"L6_cloud.fits", "L7_soft.fits", "L8_moon.fits"}
    assert "云" in flagged["L6_cloud.fits"][0] and "大" in flagged["L7_soft.fits"][0] and "亮" in flagged["L8_moon.fits"][0]
    assert r["fwhm_unit"] == "arcsec" and abs(r["summary"]["fwhm"] - 4.71 * 1.3848) < 1.0
    assert all(Path(f["thumb"]).exists() for f in r["frames"])
    assert (r["summary"]["total"], r["summary"]["suspicious"]) == (9, 3)

    framecheck.exclude(target, ["L6_cloud.fits", "L8_moon.fits", "../outside.fits"])
    assert sorted(p.name for p in (target / "Excluded" / "Light").iterdir()) == ["L6_cloud.fits", "L8_moon.fits"]
    assert targets.summary(target)["lights"] == 7
    r = framecheck.report(target)
    assert r["summary"]["excluded"] == 2 and r["summary"]["total"] == 9
    assert {f["name"] for f in r["frames"] if f["excluded"]} == {"L6_cloud.fits", "L8_moon.fits"}
    again = framecheck.analyze(target)                                   # nothing new to measure
    assert again["summary"]["measured"] == 9

    framecheck.restore(target, ["L8_moon.fits"])
    assert (target / "Light" / "L8_moon.fits").exists() and targets.summary(target)["lights"] == 8


def test_excluding_after_stacking_asks_for_a_new_stack(target):
    framecheck.analyze(target, workers=1)
    master = target / "Output" / "master" / "masterLight_BIN-1.xisf"
    master.parent.mkdir(parents=True)
    master.write_bytes(b"")
    assert framecheck.report(target)["restack"] is False
    import os
    import time
    os.utime(master, (time.time() - 60, time.time() - 60))
    framecheck.exclude(target, ["L6_cloud.fits"])
    assert framecheck.report(target)["restack"] is True


def test_cancelling_a_check_keeps_what_was_measured(target):
    from astroflow import jobctx
    ctx = jobctx.JobContext(emit=lambda kind, data: ctx.cancel() if kind == "frames.progress" else None)
    with jobctx.use(ctx), pytest.raises(jobctx.Cancelled):
        framecheck.analyze(target, workers=1)
    measured = framecheck.report(target)["summary"]["measured"]
    assert 1 <= measured < 9                                                     # kept, and stopped early
    assert framecheck.analyze(target, workers=2)["summary"]["measured"] == 9    # the rest later


def test_a_frame_that_disappears_does_not_fail_the_check(target, monkeypatch):
    real = framecheck.measure

    def vanishing(path):
        if path.name == "L3.fits":
            raise FileNotFoundError("moved away")
        return real(path)

    monkeypatch.setattr(framecheck, "measure", vanishing)
    r = framecheck.analyze(target, workers=2)
    bad = next(f for f in r["frames"] if f["name"] == "L3.fits")
    assert not bad["measured"] and "moved away" in bad["error"] and r["summary"]["measured"] == 8
