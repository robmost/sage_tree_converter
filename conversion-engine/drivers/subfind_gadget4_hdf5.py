"""
subfind_gadget4_hdf5.py - Gadget-4 built-in SubLink merger tree HDF5 driver (v4).

Format summary
--------------
All halos are stored in flat /TreeHalos datasets of length Nhalos_Total.
Tree boundaries are encoded in /TreeTable (StartOffset, Length).

TreeDescendant convention (critical)
--------------------------------------
TreeDescendant values are TREE-LOCAL offsets (in [0, Length) or -1).
They are NOT global indices into the flat TreeHalos array.
One Gadget-4 TreeTable entry = one SAGE tree group. No cross-tree forest
reconstruction is needed or correct.

Same-snapshot descendants
--------------------------
Gadget-4 records intra-snapshot FOF mergers by pointing TreeDescendant at
a halo in the SAME snapshot. These links violate LHaloTree's strict
"Descendant snapshot > progenitor snapshot" rule and are resolved by
following the chain forward until a cross-snapshot hop or -1 is reached
(up to 10 hops per halo).

Processing strategy (v4)
-------------------------
1. Load TreeTable: StartOffset and Length for all Gadget-4 trees.
2. For each Gadget-4 tree (start, n):
   a. Load the slice TreeHalos[start : start+n].
   b. Clamp out-of-range desc values to -1 (defensive).
   c. Resolve same-snapshot desc links (iterative, <=10 hops).
   d. Sort halos: SnapNum descending, SubhaloLen descending -> halo 0 = z=0 central.
   e. Remap desc indices through the sort permutation (pre-sort -> post-sort).
   f. Reconstruct FirstProgenitor/NextProgenitor by inverting Descendant (O(N log N)).
   g. Reconstruct FOF pointers from (SnapNum, GroupNr) (O(N log N)).
   h. Apply unit conversions (x1000 for pos/spin).
3. Write one HDF5 Tree<idx> group per Gadget-4 tree.

Unit conventions
----------------
  SubhaloPos  : Mpc/h -> kpc/h (x1000)
  SubhaloSpin : (Mpc/h)(km/s) -> (kpc/h)(km/s) (x1000)
  Group_M_Crit200 : 10^10 Msun/h -> direct copy
  SubhaloVel  : km/s -> direct copy
"""

import os
import sys
import warnings

import h5py
import numpy as np
from tqdm import tqdm

from utils.split_writer import SplitWriter

_POS_SPIN_SCALE = np.float32(1000.0)


def _ds(group: h5py.Group, key: str) -> h5py.Dataset:
    """Return the named item as a Dataset (type-narrowing helper)."""
    return group[key]  # type: ignore[return-value]


def _load_arr(group: h5py.Group, key: str, sel: slice | None = None) -> np.ndarray:
    """Load an h5py dataset field into a numpy array."""
    ds = _ds(group, key)
    return np.asarray(ds if sel is None else ds[sel])  # type: ignore[arg-type, index]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _estimate_particle_mass(sub_mass: np.ndarray, sub_len: np.ndarray) -> float:
    """Estimate DM particle mass from SubhaloMass / SubhaloLen of large halos."""
    valid = sub_len > 0
    if not valid.any():
        return 0.0
    n_sample = max(1, int(valid.sum()) // 1000)
    top_idx = np.argpartition(sub_len[valid], -n_sample)[-n_sample:]
    ratios = sub_mass[valid][top_idx].astype(np.float64) / sub_len[valid][top_idx].astype(
        np.float64
    )
    return float(np.median(ratios))


def _resolve_same_snap_desc(desc_in: np.ndarray, snap: np.ndarray) -> np.ndarray:
    """Replace same-snapshot Descendant links with the next forward-time halo.

    All indices are tree-local ([0, n) or -1). Uses the original desc_in for
    each hop so in-flight updates do not affect other halos in the same pass.
    Up to 10 iterations; residual same-snapshot links are set to -1.
    """
    snap_i = snap.astype(np.int64)
    desc_eff = desc_in.astype(np.int64)
    for _ in range(10):
        same_snap = (desc_eff >= 0) & (snap_i[desc_eff.clip(0)] == snap_i)
        if not same_snap.any():
            break
        hop = desc_eff[same_snap]
        desc_eff[same_snap] = np.where(
            hop >= 0,
            desc_in.astype(np.int64)[hop.clip(0)],
            np.int64(-1),
        )
    still_same = (desc_eff >= 0) & (snap_i[desc_eff.clip(0)] == snap_i)
    if still_same.any():
        warnings.warn(
            f"{still_same.sum()} same-snapshot Descendant links unresolved after 10 iterations"
            " - setting Descendant = -1. This indicates an unusual input artifact.",
            stacklevel=2,
        )
    desc_eff[still_same] = -1
    return desc_eff.astype(np.int32)


def _build_temporal_pointers(
    desc: np.ndarray,
    sub_len: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Reconstruct FirstProgenitor and NextProgenitor by inverting Descendant.

    Fully vectorised. O(N log N).
    """
    n = len(desc)
    fp = np.full(n, -1, dtype=np.int32)
    np_ = np.full(n, -1, dtype=np.int32)

    valid = desc >= 0
    if not valid.any():
        return fp, np_

    local_ids = np.arange(n, dtype=np.int32)
    valid_progs = local_ids[valid]
    desc_of_progs = desc[valid].astype(np.int32)
    sub_len_of_progs = sub_len[valid].astype(np.int64)

    sort_key = np.lexsort((-sub_len_of_progs, desc_of_progs))
    sorted_progs = valid_progs[sort_key]
    sorted_descs = desc_of_progs[sort_key]

    is_new_group = np.empty(len(sorted_descs), dtype=bool)
    is_new_group[0] = True
    is_new_group[1:] = sorted_descs[1:] != sorted_descs[:-1]

    fp[sorted_descs[is_new_group]] = sorted_progs[is_new_group]

    same_group = ~is_new_group[1:]
    np_[sorted_progs[:-1][same_group]] = sorted_progs[1:][same_group]

    return fp, np_


def _build_fof_pointers(
    snap: np.ndarray,
    group_nr: np.ndarray,
    sub_len: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Reconstruct FirstHaloInFOFGroup and NextHaloInFOFGroup.

    Fully vectorised. O(N log N).
    """
    n = len(snap)
    fhfof = np.full(n, -1, dtype=np.int32)
    nhfof = np.full(n, -1, dtype=np.int32)

    local_ids = np.arange(n, dtype=np.int32)
    snap_32 = snap.astype(np.int32)
    group_nr_i = group_nr.astype(np.int64)
    sub_len_i = sub_len.astype(np.int64)

    sort_key = np.lexsort((-sub_len_i, group_nr_i, snap_32))
    sorted_halos = local_ids[sort_key]
    sorted_snap = snap_32[sort_key]
    sorted_gnr = group_nr_i[sort_key]

    is_new = np.empty(n, dtype=bool)
    is_new[0] = True
    is_new[1:] = (sorted_snap[1:] != sorted_snap[:-1]) | (sorted_gnr[1:] != sorted_gnr[:-1])

    central_halos = sorted_halos[is_new]
    group_idx = np.cumsum(is_new) - 1
    fhfof[sorted_halos] = central_halos[group_idx]

    same_group = ~is_new[1:]
    nhfof[sorted_halos[:-1][same_group]] = sorted_halos[1:][same_group]

    return fhfof, nhfof


def _process_tree(th: h5py.Group, start: int, n: int) -> dict:
    """Build a SAGE LHaloTree field dict for one Gadget-4 TreeTable entry.

    Parameters
    ----------
    th : h5py.Group
        Open /TreeHalos group.
    start : int
        StartOffset for this tree (from /TreeTable/StartOffset).
    n : int
        Number of halos in this tree (from /TreeTable/Length).
    """
    sl = slice(start, start + n)

    # Load tree-local data from the flat arrays
    desc_raw = _load_arr(th, "TreeDescendant", sl).astype(np.int32)
    snap = _load_arr(th, "SnapNum", sl).astype(np.int32)
    group_nr = _load_arr(th, "GroupNr", sl).astype(np.int64)
    sub_len = _load_arr(th, "SubhaloLen", sl).astype(np.int32)
    mass = _load_arr(th, "Group_M_Crit200", sl).astype(np.float32)
    # Gadget-4 sets Group_M_Crit200 only on FOF centrals (SubRankInGr==0); broadcast
    # to all satellites in same (SnapNum, GroupNr) so the output field is semantically
    # correct. SAGE ignores this field for satellites (uses LenxPartMass instead).
    unique_key = snap.astype(np.int64) * 10_000_000 + group_nr
    keys, inverse = np.unique(unique_key, return_inverse=True)
    per_key_max = np.zeros(keys.shape[0], dtype=np.float32)
    np.maximum.at(per_key_max, inverse, mass)
    mass = per_key_max[inverse]
    pos = _load_arr(th, "SubhaloPos", sl).astype(np.float32) * _POS_SPIN_SCALE
    vel = _load_arr(th, "SubhaloVel", sl).astype(np.float32)
    vdisp = _load_arr(th, "SubhaloVelDisp", sl).astype(np.float32)
    vmax = _load_arr(th, "SubhaloVmax", sl).astype(np.float32)
    spin = _load_arr(th, "SubhaloSpin", sl).astype(np.float32) * _POS_SPIN_SCALE
    most_bound = _load_arr(th, "SubhaloIDMostbound", sl).astype(np.int64)

    # Clamp out-of-range desc values to -1 (defensive)
    desc_raw = np.where((desc_raw >= 0) & (desc_raw < n), desc_raw, np.int32(-1))

    # Resolve same-snapshot desc links (tree-local indices throughout)
    desc_eff = _resolve_same_snap_desc(desc_raw, snap)

    # Sort: SnapNum descending, SubhaloLen descending -> halo 0 = z=0 central
    sort_order = np.lexsort((-sub_len.astype(np.int64), -snap.astype(np.int64)))
    inv_sort = np.empty(n, dtype=np.int32)
    inv_sort[sort_order] = np.arange(n, dtype=np.int32)

    # Remap desc_eff (pre-sort local indices) to post-sort local indices
    desc_pre = desc_eff[sort_order]  # desc in pre-sort space for each sorted position
    valid = desc_pre >= 0
    desc_sorted = np.full(n, -1, dtype=np.int32)
    desc_sorted[valid] = inv_sort[desc_pre[valid]]

    snap_s = snap[sort_order]
    group_s = group_nr[sort_order]
    sub_len_s = sub_len[sort_order]

    fp, np_ = _build_temporal_pointers(desc_sorted, sub_len_s)
    fhfof, nhfof = _build_fof_pointers(snap_s, group_s, sub_len_s)

    return {
        "Descendant": desc_sorted,
        "FirstProgenitor": fp,
        "NextProgenitor": np_,
        "FirstHaloInFOFGroup": fhfof,
        "NextHaloInFOFGroup": nhfof,
        "SubhaloLen": sub_len_s,
        "Group_M_Crit200": mass[sort_order],
        "Group_M_Mean200": np.zeros(n, dtype=np.float32),
        "Group_M_TopHat200": np.zeros(n, dtype=np.float32),
        "SubhaloPos": pos[sort_order],
        "SubhaloVel": vel[sort_order],
        "SubhaloVelDisp": vdisp[sort_order],
        "SubhaloVMax": vmax[sort_order],
        "SubhaloSpin": spin[sort_order],
        "SubhaloIDMostBound": most_bound[sort_order],
        "SnapNum": snap_s,
        "FileNr": np.full(n, -1, dtype=np.int32),
    }


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def convert(
    input_path: str,
    output_path: str,
    n_trees: int | None = None,
    sim_params: dict | None = None,
    output_format: str = "lhalo_hdf5",
    n_output_files: int = 1,
) -> None:
    """Convert Gadget-4 SubLink HDF5 merger trees to SAGE LHaloTree format.

    One SAGE tree is produced per Gadget-4 TreeTable entry (tree-local desc).

    Parameters
    ----------
    input_path : str
        Path to the Gadget-4 merger tree HDF5 file (trees.hdf5).
    output_path : str
        Path for the output file (.hdf5 for lhalo_hdf5).
    n_trees : int or None
        If given, convert only the first n_trees Gadget-4 trees (test mode).
    sim_params : dict or None
        Simulation parameter overrides from --sim-config JSON.
        Key used: particle_mass_msun_per_h (Msun/h, converted to 10^10 Msun/h
        internally). If absent, estimated from SubhaloMass/SubhaloLen.
    output_format : str
        'lhalo_hdf5' (default) or 'lhalo_binary'.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    try:
        with h5py.File(input_path, "r") as in_f:
            tt: h5py.Group = in_f["TreeTable"]  # type: ignore[assignment]
            starts = _load_arr(tt, "StartOffset").astype(np.int64)
            lengths = _load_arr(tt, "Length").astype(np.int64)
            n_g4_trees = int(len(starts))
            n_to_write = min(n_trees, n_g4_trees) if n_trees is not None else n_g4_trees

            th: h5py.Group = in_f["TreeHalos"]  # type: ignore[assignment]

            _pm_override = (sim_params or {}).get("particle_mass_msun_per_h")
            if _pm_override is not None:
                particle_mass = float(_pm_override) * 1e-10  # Msun/h -> 10^10 Msun/h
            else:
                sample_size = min(100_000, int(_ds(th, "SubhaloLen").shape[0]))
                sub_mass_s = _load_arr(th, "SubhaloMass", slice(sample_size)).copy()
                sub_len_s = _load_arr(th, "SubhaloLen", slice(sample_size)).copy()
                particle_mass = _estimate_particle_mass(sub_mass_s, sub_len_s)
                warnings.warn(
                    f"particle_mass not provided; estimated from SubhaloMass/SubhaloLen: "
                    f"{particle_mass:.4e} x 10^10 Msun/h. "
                    "Pass --sim-config with particle_mass_msun_per_h to override.",
                    stacklevel=2,
                )

            print(
                f"Gadget-4 trees: {n_g4_trees}; writing {n_to_write}.",
                file=sys.stderr,
            )

            with SplitWriter(
                output_path=output_path,
                output_format=output_format,
                n_output_files=n_output_files,
                n_trees_total=n_to_write,
                particle_mass=particle_mass,
            ) as writer:
                for tree_idx in tqdm(range(n_to_write), desc="Converting trees"):
                    fields = _process_tree(th, int(starts[tree_idx]), int(lengths[tree_idx]))
                    writer.write_tree(fields)

            print(
                f"  Done: {n_to_write} trees. Output: {writer.output_paths}",
                file=sys.stderr,
            )

    except SystemExit:
        raise
    except Exception as exc:
        import traceback

        print(f"ERROR: conversion failed - {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
