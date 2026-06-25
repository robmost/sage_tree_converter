"""Shared helpers for deriving simulation parameters from input data.

Drivers must target a *family* of simulations (shared halo finder + merger tree + file
format), not one instance, so simulation-specific constants are derived from the data or an
explicit override rather than hardcoded.
"""

from __future__ import annotations

import numpy as np


def estimate_particle_mass(
    mass: np.ndarray,
    length: np.ndarray,
    n_sample: int | None = None,
) -> float:
    """Estimate the DM particle mass as the median mass/length ratio of the largest halos.

    ``mass`` and ``length`` are per-halo arrays in consistent units (e.g. 10^10 Msun/h and
    particle count). Halos with ``length <= 0`` are ignored. The sample is the ``n_sample``
    halos with the largest ``length`` (default: one per thousand valid halos). Returns 0.0
    when no halo is usable.
    """
    mass = np.asarray(mass)
    length = np.asarray(length)
    valid = length > 0
    if not valid.any():
        return 0.0
    m = mass[valid].astype(np.float64)
    n = length[valid].astype(np.float64)
    if n_sample is None:
        n_sample = max(1, int(valid.sum()) // 1000)
    n_sample = min(int(n_sample), m.size)
    top = np.argpartition(n, -n_sample)[-n_sample:]
    return float(np.median(m[top] / n[top]))
