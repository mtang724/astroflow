"""Fast synthetic tests for the comet stacker's building blocks (no PixInsight, no real data)."""
import math

import numpy as np
import pytest

from astroflow import comet, objects

RNG = np.random.default_rng(7)


def _gauss(shape, cx, cy, sigma, amp):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return amp * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma ** 2))


def test_detect_trails_finds_one_line_without_duplicates():
    shape = (600, 900)
    res = RNG.normal(0, 1.0, shape).astype(np.float32)
    t, rho = math.radians(70), 400.0                      # x cos t + y sin t = rho
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    res[np.abs(xx * math.cos(t) + yy * math.sin(t) - rho) < 1.5] += 8.0       # bright 3-px trail
    lines = comet.detect_trails(res, np.ones(shape, bool))
    assert len(lines) == 1
    t_found, rho_found, snr, hw = lines[0]
    assert abs(math.degrees(t_found) - 70) < 0.3
    assert abs(rho_found - rho) < 8
    assert snr > 8 and 6 <= hw <= 30


def test_detect_trails_ignores_pure_noise():
    res = RNG.normal(0, 1.0, (400, 400)).astype(np.float32)
    assert comet.detect_trails(res, np.ones(res.shape, bool)) == []


def test_repair_starless_keeps_coma_and_removes_star():
    shape = (3, 500, 500)
    nucleus = (250.0, 250.0)
    coma = _gauss(shape[1:], *nucleus, 30, 0.5)
    star = _gauss(shape[1:], 400, 120, 1.5, 0.8)
    noise = RNG.normal(0, 0.01, shape)
    original = (coma + star + noise).astype(np.float32)
    # what SXT does: star gone, inner coma partly gone, background lowered a little by noise smoothing
    sxt = (0.6 * coma + noise - 0.003).astype(np.float32)
    repaired = sxt.copy()
    comet.repair_starless(repaired, original, nucleus, block=16, radius=150, star_size=15, core=10)
    assert abs(float(np.median((repaired - original)[:, :100, :100]))) < 1e-3            # no background offset
    assert repaired[1, 250, 300] == pytest.approx(original[1, 250, 300], abs=0.02)        # coma back
    assert repaired[1, 120, 400] - (repaired[1, 120, 390] + repaired[1, 120, 410]) / 2 < 0.1   # star stays out


def test_weighted_stack_rejects_outlier_and_fills_holes():
    shape = (3, 20, 20)
    datas = [np.full(shape, v, np.float32) for v in (1.0, 1.0, 1.0, 1.0)]
    datas[0][:, 5, 5] = 50.0                                # hot pixel / trail in one frame
    weights = [np.ones(shape[1:], np.float32) for _ in datas]
    for w in weights:
        w[0, 0] = 0                                         # nobody covers (0, 0) ...
    fallback = [np.ones(shape[1:], np.float32) for _ in datas]   # ... except the fallback weights
    stack, info = comet.weighted_stack(datas, weights, fallback, k=4.0, sigmas=[0.1] * 4)
    assert stack[0, 5, 5] == pytest.approx(1.0)
    assert info["rejected"] >= 1
    assert stack[0, 0, 0] == pytest.approx(1.0) and info["holes"] == 0


def test_transparency_map_pulls_sparse_areas_to_clear():
    xs, ys = np.array([80]), np.array([80])
    m = comet.transparency_map(xs, ys, np.array([0.3]), (40, 40), scale=8, smooth=5, prior_stars=3.0)
    assert m[10, 10] == pytest.approx((0.3 + 3) / (1 + 3), abs=0.02)   # one dim star, weighed against the prior
    assert m[0, 39] == pytest.approx(1.0, abs=0.05)                    # far from any star: "clear"


@pytest.mark.parametrize("name,expected", [
    ("C/2025 R3", "comet"), ("C2025-R3", "comet"), ("12P/Pons-Brooks", "comet"), ("Comet Lemmon", "comet"),
    ("M 101", "galaxy"), ("IC 1805", "emission_nebula"), ("C 14", "unknown"),
])
def test_comet_names(name, expected):
    assert objects.object_type(name) == expected
