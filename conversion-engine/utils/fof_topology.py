"""Shared FOF-group topology helpers.

SAGE iterates a FOF group's satellites from ``Halo[FirstHaloInFOFGroup].NextHaloInFOFGroup``,
so the true central must head the chain (not merely the most massive member). These helpers
operate on index/pointer arrays and are format-agnostic.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np


def central_first(idxs: list[int], central_idx: int) -> list[int]:
    """Return ``idxs`` with ``central_idx`` at the head, preserving the rest order."""
    if not idxs or idxs[0] == central_idx:
        return idxs
    return [central_idx, *(i for i in idxs if i != central_idx)]


def build_fof_chains(
    snaps: np.ndarray,
    central_idx: np.ndarray,
    sort_value: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Build (FirstHaloInFOFGroup, NextHaloInFOFGroup) with each central heading its chain.

    ``central_idx[i]`` is the flat index of halo i's FOF central (i itself for a central).
    Within each ``(snap, central)`` group, members are ordered by ``sort_value`` descending
    and the central is forced to the head.
    """
    n = len(snaps)
    fhifof = np.asarray(central_idx).astype(np.int32)
    nhifof = np.full(n, -1, dtype=np.int32)

    groups: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i in range(n):
        groups[(int(snaps[i]), int(central_idx[i]))].append(i)

    for (_, central), members in groups.items():
        members.sort(key=lambda i: sort_value[i], reverse=True)
        ordered = central_first(members, central)
        for j in range(len(ordered) - 1):
            nhifof[ordered[j]] = ordered[j + 1]

    return fhifof, nhifof


def merge_flybys(
    fhifof: np.ndarray,
    nhifof: np.ndarray,
    mvirs: np.ndarray,
    snaps: np.ndarray,
    most_bound: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Fold extra final-snapshot FOF centrals into the most massive one (SAGE fix_flybys).

    When more than one self-pointing central exists at the final snapshot, every halo in the
    smaller groups is reassigned to the most massive central. ``fhifof`` must be
    path-compressed so a single pass catches flyby centrals and their satellites. If
    ``most_bound`` is given, the demoted centrals' real (non-negative) IDs are sign-flipped as
    a flyby marker; -1 sentinels are left untouched.

    Inputs are never mutated; returns the originals unchanged when there is one z=0 central.
    """
    n = len(snaps)
    if n == 0:
        return fhifof, nhifof, most_bound

    final_snap = int(snaps.max())
    z0_centrals = [i for i in range(n) if int(snaps[i]) == final_snap and int(fhifof[i]) == i]
    if len(z0_centrals) <= 1:
        return fhifof, nhifof, most_bound

    fhifof = fhifof.copy()
    nhifof = nhifof.copy()

    z0_arr = np.asarray(z0_centrals)
    host_idx = int(z0_arr[int(np.argmax(mvirs[z0_arr]))])
    flyby = {idx for idx in z0_centrals if idx != host_idx}

    if most_bound is not None:
        mb = most_bound.copy()
        for c in flyby:
            if mb[c] >= 0:
                mb[c] = -mb[c]
        most_bound = mb

    for i in range(n):
        if int(snaps[i]) == final_snap and int(fhifof[i]) in flyby:
            fhifof[i] = host_idx

    host_group = [i for i in range(n) if int(snaps[i]) == final_snap and int(fhifof[i]) == host_idx]
    host_group.sort(key=lambda i: float(mvirs[i]), reverse=True)
    host_group = central_first(host_group, host_idx)

    for i in host_group:
        nhifof[i] = -1
    for j in range(len(host_group) - 1):
        nhifof[host_group[j]] = host_group[j + 1]

    return fhifof, nhifof, most_bound
