"""
SYNTHETIC fingerprint-like images for pipeline and infrastructure testing.

These images are generated from random parameters. They are NOT biometric
data, do not belong to any person, and MUST NOT be used to claim
identification accuracy on real fingerprints. Their only purposes are:

* proving that extraction, serialization, persistence, reload and matching
  work end-to-end with the real SourceAFIS engine;
* producing templates with realistic minutia counts so that gallery memory
  and matching latency can be measured at scale.

Model: the phase model of fingerprints (K. G. Larkin & P. A. Fletcher, "A
coherent framework for fingerprint analysis: are fingerprints holograms?",
Optics Express 15(14), 2007). A ridge pattern is cos(psi_c + psi_s), where
psi_c is a smooth global phase (whorl/loop/arch-like family plus low-frequency
bending) and psi_s is a sum of spiral phases whose singular points are the
minutiae (ridge endings/bifurcations).

A "finger" is a set of random parameters. An "impression" renders the finger
with a random rotation, translation, small elastic warp, contrast change,
noise and partial capture area, so two impressions of one synthetic finger
behave like a genuine pair and different synthetic fingers like impostors.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np

WIDTH = 320
HEIGHT = 400
RIDGE_PERIOD_PX = 9.0  # ~ 500 dpi


@dataclass(frozen=True)
class SyntheticFinger:
    seed: int
    center: tuple[float, float]
    aspect: float
    linear: float
    bend: np.ndarray        # (k, 4): amplitude, fx, fy, phase
    minutiae: np.ndarray    # (n, 3): x, y, polarity (+1/-1)
    mask_axes: tuple[float, float]


def make_finger(seed: int) -> SyntheticFinger:
    rng = np.random.default_rng(seed)
    cx = WIDTH / 2 + rng.uniform(-30, 30)
    cy = HEIGHT * rng.uniform(0.35, 0.55)
    bend = np.column_stack([
        rng.uniform(1.0, 4.0, 4),            # amplitude (radians)
        rng.uniform(-1, 1, 4) / 180.0,       # spatial frequency x
        rng.uniform(-1, 1, 4) / 180.0,       # spatial frequency y
        rng.uniform(0, 2 * np.pi, 4),
    ])
    n = int(rng.integers(35, 60))
    pts: list[tuple[float, float, float]] = []
    attempts = 0
    while len(pts) < n and attempts < 5000:
        attempts += 1
        x = rng.uniform(25, WIDTH - 25)
        y = rng.uniform(25, HEIGHT - 25)
        if ((x - WIDTH / 2) / (WIDTH * 0.46)) ** 2 + ((y - HEIGHT / 2) / (HEIGHT * 0.47)) ** 2 > 1:
            continue
        if any((x - px) ** 2 + (y - py) ** 2 < 18 ** 2 for px, py, _ in pts):
            continue
        pts.append((x, y, float(rng.choice([-1.0, 1.0]))))
    return SyntheticFinger(
        seed=seed,
        center=(cx, cy),
        aspect=float(rng.uniform(0.6, 1.4)),
        linear=float(rng.uniform(0.0, 0.85)),
        bend=bend,
        minutiae=np.array(pts, dtype=np.float64),
        mask_axes=(WIDTH * rng.uniform(0.40, 0.48), HEIGHT * rng.uniform(0.42, 0.49)),
    )


def _box_blur(img: np.ndarray) -> np.ndarray:
    p = np.pad(img, 1, mode="edge")
    return (p[:-2, :-2] + p[:-2, 1:-1] + p[:-2, 2:] + p[1:-1, :-2] + p[1:-1, 1:-1] + p[1:-1, 2:]
            + p[2:, :-2] + p[2:, 1:-1] + p[2:, 2:]) / 9.0


def render_impression(finger: SyntheticFinger, impression: int, variation: float = 1.0) -> np.ndarray:
    """Render one impression as an (HEIGHT, WIDTH) uint8 array (dark ridges on light background)."""
    rng = np.random.default_rng((finger.seed * 1_000_003 + impression) & 0xFFFFFFFF)
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float64)

    # Impression geometry: output pixel -> finger coordinates.
    angle = np.deg2rad(rng.uniform(-12, 12) * variation)
    tx, ty = rng.uniform(-18, 18, 2) * variation
    cos_a, sin_a = np.cos(angle), np.sin(angle)
    ox, oy = WIDTH / 2, HEIGHT / 2
    u = cos_a * (xx - ox) - sin_a * (yy - oy) + ox + tx
    v = sin_a * (xx - ox) + cos_a * (yy - oy) + oy + ty
    warp_amp = rng.uniform(0.5, 3.0) * variation
    wf = rng.uniform(1 / 260, 1 / 140, 2)
    wp = rng.uniform(0, 2 * np.pi, 2)
    u = u + warp_amp * np.sin(v * wf[0] * 2 * np.pi + wp[0])
    v = v + warp_amp * np.sin(u * wf[1] * 2 * np.pi + wp[1])

    cx, cy = finger.center
    r = np.sqrt(((u - cx) * finger.aspect) ** 2 + (v - cy) ** 2)
    psi = 2 * np.pi / RIDGE_PERIOD_PX * (r + finger.linear * (v - cy) * 1.2)
    for amp, fx, fy, ph in finger.bend:
        psi += amp * np.sin(2 * np.pi * (fx * u + fy * v) + ph)
    # Sum of +/- arg(z - z_n) equals arg(prod (z - z_n)^(+/-1)) modulo 2*pi, and psi is
    # only used inside cos(), so one angle() of a complex product replaces n arctan2 calls.
    # Factors are scaled by 1/400 to stay well inside complex128 range.
    z = (u + 1j * v) / 400.0
    num = np.ones_like(z)
    den = np.ones_like(z)
    for mx, my, pol in finger.minutiae:
        factor = z - complex(mx, my) / 400.0
        if pol > 0:
            num *= factor
        else:
            den *= factor
    psi += np.angle(num * np.conj(den))

    ridges = 0.5 + 0.5 * np.cos(psi)
    # Pressure / ridge thickness variation.
    gamma = rng.uniform(0.7, 1.4)
    ridges = ridges ** gamma

    # Capture area: soft elliptical mask in finger coordinates, randomly shifted.
    ax, ay = finger.mask_axes
    shift = rng.uniform(-15, 15, 2) * variation
    d = ((u - WIDTH / 2 - shift[0]) / ax) ** 2 + ((v - HEIGHT / 2 - shift[1]) / ay) ** 2
    mask = np.clip((1.0 - d) * 6.0, 0.0, 1.0)

    contrast = rng.uniform(0.65, 0.95)
    img = 1.0 - contrast * ridges * mask          # 1 = white background, ridges dark
    img = _box_blur(img)
    img += rng.normal(0, rng.uniform(0.02, 0.06), img.shape)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)
