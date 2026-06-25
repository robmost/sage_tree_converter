"""Tests for utils.sim_params.estimate_particle_mass."""

import numpy as np

from utils.sim_params import estimate_particle_mass


def test_estimate_recovers_constant_ratio():
    length = np.array([10, 20, 50, 100], dtype=np.int64)
    mass = length * 0.5  # exact particle mass 0.5
    assert estimate_particle_mass(mass, length) == 0.5


def test_estimate_ignores_nonpositive_length():
    length = np.array([0, -5, 100], dtype=np.int64)
    mass = np.array([999.0, 999.0, 30.0])  # only the last is usable -> 0.3
    assert estimate_particle_mass(mass, length) == 0.3


def test_estimate_returns_zero_when_no_usable_halo():
    length = np.array([0, 0], dtype=np.int64)
    mass = np.array([10.0, 20.0])
    assert estimate_particle_mass(mass, length) == 0.0


def test_estimate_samples_largest_by_length():
    # Small halos carry a biased ratio; the largest-by-length halos set the estimate.
    length = np.array([5, 5, 5, 1000, 2000], dtype=np.int64)
    mass = np.array([50.0, 50.0, 50.0, 100.0, 200.0])  # big halos -> ratio 0.1
    assert estimate_particle_mass(mass, length, n_sample=2) == 0.1


def test_estimate_clamps_nonpositive_n_sample():
    # n_sample <= 0 must not select the whole array; it clamps to the single largest.
    length = np.array([5, 5, 1000], dtype=np.int64)
    mass = np.array([50.0, 50.0, 100.0])  # largest-by-length ratio = 0.1
    assert estimate_particle_mass(mass, length, n_sample=0) == 0.1
    assert estimate_particle_mass(mass, length, n_sample=-3) == 0.1
