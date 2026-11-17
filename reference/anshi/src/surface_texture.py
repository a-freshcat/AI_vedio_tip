# -*- coding: utf-8 -*-
"""Shared procedural surface texture primitives with deterministic RNG support."""
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, rotate as nd_rotate


def texture_field(rng, shape, sigma):
    """Generate a centered, tanh-normalized Gaussian noise field in [-1, 1]."""
    field = gaussian_filter(rng.standard_normal(shape, dtype=np.float32), sigma=sigma)
    centered = field - field.mean()
    return np.tanh(centered / max(float(centered.std()) * 1.35, 1e-6))


def rotated_texture_field(rng, shape, sigma_along, sigma_across, angle_deg):
    """Generate an anisotropic texture field aligned along angle_deg (0=E-W, +angle=CCW in lower-origin coords)."""
    height, width = shape
    pad = int(np.ceil(np.hypot(height, width))) + int(np.ceil(4.0 * max(sigma_along, sigma_across))) + 8
    noise = rng.standard_normal((pad, pad), dtype=np.float32)
    smoothed = gaussian_filter(noise, sigma=(sigma_across, sigma_along))
    rotated = nd_rotate(smoothed, angle=-float(angle_deg), axes=(1, 0), reshape=False, order=1, mode="reflect")
    y0 = (pad - height) // 2
    x0 = (pad - width) // 2
    crop = rotated[y0 : y0 + height, x0 : x0 + width]
    centered = crop - crop.mean()
    return np.tanh(centered / max(float(centered.std()) * 1.35, 1e-6))


def resize_field(field, shape):
    """Bicubic resample a float32 2D scalar field to (height, width)."""
    height, width = shape
    source = Image.fromarray(field.astype(np.float32))
    return np.asarray(source.resize((width, height), Image.Resampling.BICUBIC))


def steerable_slope_fields(rng, shape, gx, gy, sigma_along=8.0, sigma_across=1.5):
    """Build variance-normalized (downslope, contour) anisotropic fields aligned to local slope (gx, gy)."""
    mag = np.hypot(gx, gy) + 1e-7
    ux = gx / mag
    uy = gy / mag

    angles = (0.0, 45.0, 90.0, 135.0)
    basis = [rotated_texture_field(rng, shape, sigma_along=sigma_along, sigma_across=sigma_across, angle_deg=a) for a in angles]

    w_slope = []
    w_contour = []
    for a in angles:
        rad = np.deg2rad(a)
        c, s = float(np.cos(rad)), float(np.sin(rad))
        proj_slope = (ux * c + uy * s) ** 2
        proj_cont = (-uy * c + ux * s) ** 2
        w_slope.append(proj_slope * proj_slope)
        w_contour.append(proj_cont * proj_cont)

    norm_s = np.sqrt(sum(w * w for w in w_slope) + 1e-8)
    norm_c = np.sqrt(sum(w * w for w in w_contour) + 1e-8)
    downslope = sum((w / norm_s) * b for w, b in zip(w_slope, basis))
    contour = sum((w / norm_c) * b for w, b in zip(w_contour, basis))
    return downslope, contour
