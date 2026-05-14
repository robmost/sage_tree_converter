"""
subfind_gadget4_hdf5.py — Gadget-4 built-in SubLink merger tree HDF5 driver (v4).

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
   c. Resolve same-snapshot desc links (iterative, ≤10 hops).
   d. Sort halos: SnapNum descending, SubhaloLen descending → halo 0 = z=0 central.
   e. Remap desc indices through the sort permutation (pre-sort → post-sort).
   f. Reconstruct FirstProgenitor/NextProgenitor by inverting Descendant (O(N log N)).
   g. Reconstruct FOF pointers from (SnapNum, GroupNr) (O(N log N)).
   h. Apply unit conversions (×1000 for pos/spin).
3. Write one HDF5 Tree<idx> group per Gadget-4 tree.

Unit conventions
----------------
  SubhaloPos  : Mpc/h → kpc/h (×1000)
  SubhaloSpin : (Mpc/h)(km/s) → (kpc/h)(km/s) (×1000)
  Group_M_Crit200 : 10^10 Msun/h → direct copy
  SubhaloVel  : km/s → direct copy
"""

import os
import sys
import warnings

import h5py
import numpy as np
from tqdm import tqdm

from utils import binary_writer, hdf5_writer

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

    # Sort: SnapNum descending, SubhaloLen descending → halo 0 = z=0 central
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
    particle_mass: float | None = None,
    output_format: str = "lhalo_hdf5",
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
    particle_mass : float or None
        Dark matter particle mass in 10^10 Msun/h. Estimated if None.
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

            if particle_mass is None:
                sample_size = min(100_000, int(_ds(th, "SubhaloLen").shape[0]))
                sub_mass_s = _load_arr(th, "SubhaloMass", slice(sample_size)).copy()
                sub_len_s = _load_arr(th, "SubhaloLen", slice(sample_size)).copy()
                particle_mass = _estimate_particle_mass(sub_mass_s, sub_len_s)
                warnings.warn(
                    f"particle_mass not provided; estimated from SubhaloMass/SubhaloLen: "
                    f"{particle_mass:.4e} × 10^10 Msun/h. "
                    "Pass --particle-mass to override.",
                    stacklevel=2,
                )

            print(
                f"Gadget-4 trees: {n_g4_trees}; writing {n_to_write}.",
                file=sys.stderr,
            )

            tree_n_halos = lengths[:n_to_write].astype(np.int32)
            total_halos_out = int(tree_n_halos.sum())

            if output_format == "lhalo_hdf5":
                with h5py.File(output_path, "w") as out_f:
                    hdf5_writer.write_header(
                        out_f,
                        particle_mass=particle_mass,
                        n_trees=n_to_write,
                        total_halos=total_halos_out,
                        n_output_files=1,
                        tree_n_halos=tree_n_halos,
                    )
                    for tree_idx in tqdm(range(n_to_write), desc="Converting trees"):
                        fields = _process_tree(th, int(starts[tree_idx]), int(lengths[tree_idx]))
                        hdf5_writer.write_tree(out_f, tree_idx, fields)

            elif output_format == "lhalo_binary":
                with open(output_path, "wb") as out_f:
                    binary_writer.write_header(
                        out_f,
                        particle_mass=particle_mass,
                        n_trees=n_to_write,
                        total_halos=total_halos_out,
                        n_output_files=1,
                        tree_n_halos=tree_n_halos,
                    )
                    for tree_idx in tqdm(range(n_to_write), desc="Converting trees"):
                        fields = _process_tree(th, int(starts[tree_idx]), int(lengths[tree_idx]))
                        binary_writer.write_tree(out_f, tree_idx, fields)

            else:
                print(f"ERROR: unknown output_format '{output_format}'.", file=sys.stderr)
                sys.exit(1)

    except SystemExit:
        raise
    except Exception as exc:
        import traceback

        print(f"ERROR: conversion failed — {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        if os.path.exists(output_path):
            os.remove(output_path)
        sys.exit(1)


def read_trees(
    input_path: str,
    n_trees: int | None = None,
) -> dict[int, dict]:
    """Read trees into SAGE LHaloTree schema without writing output.

    Applies the same per-tree processing as convert() so tree_idx values match.
    Called by semantic validation to load the original data as the reference column.

    Returns
    -------
    dict[int, dict[str, np.ndarray]]
        tree_idx (0-based) → field dict. SubhaloPos in kpc/h,
        SubhaloSpin in (kpc/h)(km/s), masses in 10^10 Msun/h.
    """
    result: dict[int, dict] = {}
    with h5py.File(input_path, "r") as in_f:
        tt: h5py.Group = in_f["TreeTable"]  # type: ignore[assignment]
        starts = _load_arr(tt, "StartOffset").astype(np.int64)
        lengths = _load_arr(tt, "Length").astype(np.int64)
        n_g4_trees = int(len(starts))
        n_to_read = min(n_trees, n_g4_trees) if n_trees is not None else n_g4_trees

        th: h5py.Group = in_f["TreeHalos"]  # type: ignore[assignment]
        for tree_idx in tqdm(range(n_to_read), desc="Reading trees"):
            result[tree_idx] = _process_tree(th, int(starts[tree_idx]), int(lengths[tree_idx]))

    return result
