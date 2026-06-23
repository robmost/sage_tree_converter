"""
ahf_mergetree_ascii.py - SAGE LHaloTree converter for AHF/MergerTree ASCII format.

Input:  directory containing .AHF_halos and .AHF_croco files
Output: SAGE LHaloTree HDF5 (lhalo_hdf5) or binary (lhalo_binary)

Format ID: ahf_mergetree_ascii
Schema:    format-database/ahf_mergetree_ascii.json

Halo ID encoding (SUSSING2013, MPI mode):
    ID = snap_id * 1e16 + mpi_rank * 1e10 + halo_1based_index
    (non-MPI: ID = snap_id * 1e12 + halo_1based_index; auto-detected)

AHF_halos column map (0-based):
    0  = HaloID      1  = hostHaloID    3  = Mhalo [Msun/h]
    4  = npart       5  = Xc [kpc/h]   6  = Yc     7  = Zc
    8  = VXc [km/s]  9  = VYc          10 = VZc     11 = Rhalo [kpc/h]
    16 = Vmax [km/s] 18 = sigV [km/s]  19 = lambda  21 = Lx  22 = Ly  23 = Lz

SubhaloSpin reconstruction:
    |j| = lambda * sqrt(2 * G * Mhalo * Rhalo_Mpc_h) * 1000  [(kpc/h)(km/s)]
    G   = 4.3009e-9 (Mpc/h)(km/s)^2(Msun/h)^-1
    direction = unit vector (Lx, Ly, Lz) from AHF_halos cols 21-23
"""

import os
import re
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable
from glob import glob
from pathlib import Path
from typing import NamedTuple

import numpy as np
from tqdm import tqdm

from errors import ConversionError
from utils.split_writer import SplitWriter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_G_PHYS = 4.3009e-9  # (Mpc/h)(km/s)^2(Msun/h)^-1 - for SubhaloSpin

_COL_ID = 0
_COL_HOST_ID = 1
_COL_MHALO = 3
_COL_NPART = 4
_COL_XC = 5
_COL_YC = 6
_COL_ZC = 7
_COL_VXC = 8
_COL_VYC = 9
_COL_VZC = 10
_COL_RHALO = 11
_COL_VMAX = 16
_COL_SIGV = 18
_COL_LAMBDA = 19
_COL_LX = 21
_COL_LY = 22
_COL_LZ = 23

_MAX_CHAIN_DEPTH = 2000  # guard against hostHaloID cycles


# ---------------------------------------------------------------------------
# File discovery helpers
# ---------------------------------------------------------------------------
def _snap_from_filename(filename: str) -> int:
    m = re.search(r"snap_(\d+)", os.path.basename(filename))
    if not m:
        raise ValueError(f"Cannot extract snap index from filename: {filename}")
    return int(m.group(1))


# ---------------------------------------------------------------------------
# AHF_halos parser
# ---------------------------------------------------------------------------
def _parse_halos_file(filepath: str, snap_id: int) -> list:
    """Parse one AHF_halos file; return list of halo property dicts."""
    halos = []
    with open(filepath) as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            cols = line.split()
            if len(cols) < 24:
                continue
            try:
                h = {
                    "haloID": int(cols[_COL_ID]),
                    "hostHaloID": int(cols[_COL_HOST_ID]),
                    "snap_id": snap_id,
                    "Mhalo": float(cols[_COL_MHALO]),
                    "npart": int(cols[_COL_NPART]),
                    "Xc": float(cols[_COL_XC]),
                    "Yc": float(cols[_COL_YC]),
                    "Zc": float(cols[_COL_ZC]),
                    "VXc": float(cols[_COL_VXC]),
                    "VYc": float(cols[_COL_VYC]),
                    "VZc": float(cols[_COL_VZC]),
                    "Rhalo": float(cols[_COL_RHALO]),
                    "Vmax": float(cols[_COL_VMAX]),
                    "sigV": float(cols[_COL_SIGV]),
                    "lambda": float(cols[_COL_LAMBDA]),
                    "Lx": float(cols[_COL_LX]),
                    "Ly": float(cols[_COL_LY]),
                    "Lz": float(cols[_COL_LZ]),
                }
            except (ValueError, IndexError) as exc:
                print(
                    f"WARNING: skipping malformed line in {filepath}: {exc}",
                    file=sys.stderr,
                )
                continue
            halos.append(h)
    return halos


# ---------------------------------------------------------------------------
# AHF_croco parser
# ---------------------------------------------------------------------------
def _parse_croco_file(filepath: str) -> dict:
    """Parse one AHF_croco file.

    Returns
    -------
    dict[int, list[tuple[float, int]]]
        desc_haloID -> [(merit, prog_haloID), ...] sorted by merit descending.
    """
    progenitors: dict = {}
    current_desc: int | None = None
    current_progs: list = []

    with open(filepath) as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            fields = line.split()
            if len(fields) == 3:
                # Save previous block
                if current_desc is not None and current_progs:
                    progenitors[current_desc] = sorted(current_progs, key=lambda x: -x[0])
                try:
                    current_desc = int(fields[0])
                except ValueError:
                    current_desc = None
                current_progs = []
            elif len(fields) == 4:
                # shared_part  prog_id  prog_npart  merit
                try:
                    merit = float(fields[3])
                    prog_id = int(fields[1])
                    current_progs.append((merit, prog_id))
                except ValueError:
                    pass

    # Save last block
    if current_desc is not None and current_progs:
        progenitors[current_desc] = sorted(current_progs, key=lambda x: -x[0])

    return progenitors


# ---------------------------------------------------------------------------
# Union-Find for O(N alpha(N)) tree identification
# ---------------------------------------------------------------------------
class _UnionFind:
    __slots__ = ("parent", "rank")

    def __init__(self, keys: Iterable[int]) -> None:
        self.parent = {k: k for k in keys}
        self.rank = {k: 0 for k in keys}

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            nxt = self.parent[x]
            self.parent[x] = root
            x = nxt
        return root

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1


# ---------------------------------------------------------------------------
# Pipeline - convert() runs _prepare_trees() (parse + identify + order trees)
# then _build_tree_field_dict() per tree.
# ---------------------------------------------------------------------------
class _PreparedTrees(NamedTuple):
    halo_props: dict[int, dict]
    snap_halos: dict[int, list]
    min_snap: int
    max_snap: int
    sorted_roots: list[int]
    n_trees_total: int
    n_trees_convert: int
    tree_halo_order: dict[int, list]
    haloID_to_flat: dict[int, tuple]
    progenitors: dict[int, list]
    descendants: dict[int, int]
    get_top_central: Callable[[int], int]


def _prepare_trees(input_path: str, n_trees: int | None) -> _PreparedTrees:
    """Parse AHF input, identify trees via Union-Find, order them, assign flat indices.

    Shared setup for convert(); prints discovery/parse/summary progress to stderr.
    Particle-mass estimation stays in convert().
    """
    input_dir = Path(input_path)
    halos_files = sorted(glob(str(input_dir / "*.AHF_halos")), key=_snap_from_filename)
    croco_files = sorted(glob(str(input_dir / "*.AHF_croco")), key=_snap_from_filename)

    if not halos_files:
        raise ValueError(f"No .AHF_halos files found in {input_dir}")

    snap_ids = [_snap_from_filename(f) for f in halos_files]
    min_snap = min(snap_ids)
    max_snap = max(snap_ids)

    print(
        f"  AHF_halos files : {len(snap_ids)}  (snap {min_snap}-{max_snap})",
        file=sys.stderr,
    )
    print(f"  AHF_croco files : {len(croco_files)}", file=sys.stderr)
    print("  Parsing AHF_halos ...", file=sys.stderr)

    # --- Parse halos ---
    halo_props: dict[int, dict] = {}
    snap_halos: dict[int, list] = defaultdict(list)
    for fpath, snap_id in zip(halos_files, snap_ids):
        for h in _parse_halos_file(fpath, snap_id):
            hid = h["haloID"]
            halo_props[hid] = h
            snap_halos[snap_id].append(hid)

    print(f"  Total halos loaded: {len(halo_props)}", file=sys.stderr)
    print("  Parsing AHF_croco ...", file=sys.stderr)

    # --- Parse croco ---
    progenitors: dict[int, list] = {}
    descendants: dict[int, int] = {}
    desc_merit: dict[int, float] = {}
    for fpath in croco_files:
        for desc_id, prog_list in _parse_croco_file(fpath).items():
            progenitors[desc_id] = prog_list
            for merit, prog_id in prog_list:
                if prog_id not in desc_merit or merit > desc_merit[prog_id]:
                    desc_merit[prog_id] = merit
                    descendants[prog_id] = desc_id

    # --- Union-Find: temporal links ---
    uf = _UnionFind(halo_props.keys())
    for desc_id, prog_list in progenitors.items():
        if desc_id not in halo_props:
            continue
        for _, prog_id in prog_list:
            if prog_id in halo_props:
                uf.union(desc_id, prog_id)

    # --- Union-Find: spatial links via hostHaloID chain ---
    top_central_cache: dict[int, int] = {}

    def get_top_central(hid: int) -> int:
        path = []
        cur = hid
        depth = 0
        while depth < _MAX_CHAIN_DEPTH:
            if cur in top_central_cache:
                result = top_central_cache[cur]
                break
            h = halo_props.get(cur)
            host = h["hostHaloID"] if h is not None else 0
            if host == 0 or host not in halo_props:
                top_central_cache[cur] = cur
                result = cur
                break
            path.append(cur)
            cur = host
            depth += 1
        else:
            top_central_cache[cur] = cur
            result = cur
        for p in path:
            top_central_cache[p] = result
        return result

    for snap_id, hid_list in snap_halos.items():
        for hid in hid_list:
            central = get_top_central(hid)
            if central != hid and central in halo_props:
                uf.union(hid, central)

    tree_members: dict[int, list] = defaultdict(list)
    for hid in halo_props:
        tree_members[uf.find(hid)].append(hid)

    def _tree_sort_key(root: int) -> tuple[int, float]:
        members = tree_members[root]
        snap_max_m = [
            halo_props[h]["Mhalo"] for h in members if halo_props[h]["snap_id"] == max_snap
        ]
        if snap_max_m:
            return (1, max(snap_max_m))
        return (0, max(halo_props[h]["Mhalo"] for h in members))

    sorted_roots = sorted(tree_members.keys(), key=_tree_sort_key, reverse=True)
    n_trees_total = len(sorted_roots)
    n_trees_convert = min(n_trees, n_trees_total) if n_trees is not None else n_trees_total

    print(
        f"  Trees total / converting: {n_trees_total} / {n_trees_convert}",
        file=sys.stderr,
    )

    # Assign flat indices within each tree: order = (SnapNum desc, Mhalo desc)
    tree_halo_order: dict[int, list] = {}
    haloID_to_flat: dict[int, tuple] = {}
    for tree_idx, root in enumerate(sorted_roots[:n_trees_convert]):
        members = tree_members[root]
        ordered = sorted(
            members, key=lambda h: (-halo_props[h]["snap_id"], -halo_props[h]["Mhalo"])
        )
        tree_halo_order[root] = ordered
        for flat_idx, hid in enumerate(ordered):
            haloID_to_flat[hid] = (tree_idx, flat_idx)

    return _PreparedTrees(
        halo_props=halo_props,
        snap_halos=snap_halos,
        min_snap=min_snap,
        max_snap=max_snap,
        sorted_roots=sorted_roots,
        n_trees_total=n_trees_total,
        n_trees_convert=n_trees_convert,
        tree_halo_order=tree_halo_order,
        haloID_to_flat=haloID_to_flat,
        progenitors=progenitors,
        descendants=descendants,
        get_top_central=get_top_central,
    )


def _build_tree_field_dict(tree_idx: int, root: int, ctx: _PreparedTrees) -> dict:
    """Build the SAGE LHaloTree field dict for one tree."""
    halo_props = ctx.halo_props
    descendants = ctx.descendants
    progenitors = ctx.progenitors
    haloID_to_flat = ctx.haloID_to_flat
    ordered_hids = ctx.tree_halo_order[root]
    N = len(ordered_hids)

    descendant = np.full(N, -1, dtype=np.int32)
    first_progenitor = np.full(N, -1, dtype=np.int32)
    next_progenitor = np.full(N, -1, dtype=np.int32)
    first_halo_in_fof = np.full(N, -1, dtype=np.int32)
    next_halo_in_fof = np.full(N, -1, dtype=np.int32)
    subhalo_len = np.zeros(N, dtype=np.int32)
    group_m_crit200 = np.zeros(N, dtype=np.float32)
    group_m_mean200 = np.zeros(N, dtype=np.float32)
    group_m_tophat200 = np.zeros(N, dtype=np.float32)
    subhalo_vmax = np.zeros(N, dtype=np.float32)
    subhalo_veldisp = np.zeros(N, dtype=np.float32)
    subhalo_id_mbp = np.full(N, -1, dtype=np.int64)
    snap_num = np.zeros(N, dtype=np.int32)
    subhalo_pos = np.zeros((N, 3), dtype=np.float32)
    subhalo_vel = np.zeros((N, 3), dtype=np.float32)
    subhalo_spin = np.zeros((N, 3), dtype=np.float32)
    file_nr = np.full(N, -1, dtype=np.int32)

    # --- Halo properties ---
    for flat_idx, hid in enumerate(ordered_hids):
        h = halo_props[hid]
        snap_num[flat_idx] = h["snap_id"] - ctx.min_snap
        subhalo_len[flat_idx] = h["npart"]
        group_m_crit200[flat_idx] = h["Mhalo"] * 1e-10
        subhalo_vmax[flat_idx] = h["Vmax"]
        subhalo_veldisp[flat_idx] = h["sigV"]
        subhalo_pos[flat_idx] = [h["Xc"], h["Yc"], h["Zc"]]
        subhalo_vel[flat_idx] = [h["VXc"], h["VYc"], h["VZc"]]
        # SubhaloSpin: reconstruct from lambda, Mhalo, Rhalo, unit vector
        Rhalo_Mpch = h["Rhalo"] / 1000.0
        j_sq = 2.0 * _G_PHYS * h["Mhalo"] * Rhalo_Mpch
        if j_sq > 0.0 and h["lambda"] > 0.0:
            j_mag = h["lambda"] * np.sqrt(j_sq) * 1000.0  # (kpc/h)(km/s)
        else:
            j_mag = 0.0
        subhalo_spin[flat_idx] = [j_mag * h["Lx"], j_mag * h["Ly"], j_mag * h["Lz"]]

    # --- Temporal pointers ---
    for flat_idx, hid in enumerate(ordered_hids):
        desc_id = descendants.get(hid)
        if desc_id is not None and desc_id in haloID_to_flat:
            ti, fi = haloID_to_flat[desc_id]
            if ti == tree_idx:
                descendant[flat_idx] = fi
        prog_list = progenitors.get(hid, [])
        valid = [
            (m, pid)
            for m, pid in prog_list
            if pid in haloID_to_flat and haloID_to_flat[pid][0] == tree_idx
        ]
        if not valid:
            continue
        _, first_pid = valid[0]
        first_progenitor[flat_idx] = haloID_to_flat[first_pid][1]
        for k in range(len(valid) - 1):
            fi_cur = haloID_to_flat[valid[k][1]][1]
            fi_next = haloID_to_flat[valid[k + 1][1]][1]
            next_progenitor[fi_cur] = fi_next

    # --- Spatial pointers: FirstHaloInFOFGroup / NextHaloInFOFGroup ---
    fof_groups: dict[tuple, list] = defaultdict(list)
    for flat_idx, hid in enumerate(ordered_hids):
        h = halo_props[hid]
        central = ctx.get_top_central(hid)
        fof_groups[(h["snap_id"], central)].append((h["Mhalo"], flat_idx))

    for group_members in fof_groups.values():
        group_members.sort(key=lambda x: -x[0])
        central_fi = group_members[0][1]
        for _, fi in group_members:
            first_halo_in_fof[fi] = central_fi
        for k in range(len(group_members) - 1):
            next_halo_in_fof[group_members[k][1]] = group_members[k + 1][1]

    return {
        "Descendant": descendant,
        "FirstProgenitor": first_progenitor,
        "NextProgenitor": next_progenitor,
        "FirstHaloInFOFGroup": first_halo_in_fof,
        "NextHaloInFOFGroup": next_halo_in_fof,
        "SubhaloLen": subhalo_len,
        "Group_M_Crit200": group_m_crit200,
        "Group_M_Mean200": group_m_mean200,
        "Group_M_TopHat200": group_m_tophat200,
        "SubhaloVMax": subhalo_vmax,
        "SubhaloVelDisp": subhalo_veldisp,
        "SubhaloIDMostBound": subhalo_id_mbp,
        "SnapNum": snap_num,
        "SubhaloPos": subhalo_pos,
        "SubhaloVel": subhalo_vel,
        "SubhaloSpin": subhalo_spin,
        "FileNr": file_nr,
    }


# ---------------------------------------------------------------------------
# Public convert() entry point
# ---------------------------------------------------------------------------
def convert(
    input_path: str,
    output_path: str,
    n_trees: int | None = None,
    sim_params: dict | None = None,
    output_format: str = "lhalo_hdf5",
    n_output_files: int = 1,
) -> None:
    """Convert AHF/MergerTree ASCII input to SAGE LHaloTree HDF5 or binary.

    Parameters
    ----------
    input_path : str
        Path to directory containing .AHF_halos and .AHF_croco files.
    output_path : str
        Path for the first output file (index 0).  When n_output_files > 1,
        additional files are created by replacing the trailing index token.
    n_trees : int or None
        If given, convert only the first n_trees trees (test mode).
    sim_params : dict or None
        Simulation parameter overrides from --sim-config JSON.
        Key used: particle_mass_msun_per_h (Msun/h). If absent, estimated from data.
    output_format : str
        'lhalo_hdf5' or 'lhalo_binary'.
    n_output_files : int
        Number of output files to produce (default 1).  Must be >= 1.
    """

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    try:
        ctx = _prepare_trees(input_path, n_trees)

        # Estimate particle mass (in Msun/h) if not user-supplied
        _pm_override = (sim_params or {}).get("particle_mass_msun_per_h")
        if _pm_override is None:
            top_hids = sorted(
                ctx.snap_halos[ctx.max_snap],
                key=lambda hid: ctx.halo_props[hid]["Mhalo"],
                reverse=True,
            )[:20]
            m_estimates = [
                ctx.halo_props[hid]["Mhalo"] / max(ctx.halo_props[hid]["npart"], 1)
                for hid in top_hids
            ]
            m_particle_msun = float(np.median(m_estimates)) if m_estimates else 1e7
        else:
            m_particle_msun = float(_pm_override)

        particle_mass_1e10 = m_particle_msun / 1e10
        print(
            f"  Particle mass : {m_particle_msun:.4e} Msun/h "
            f"({particle_mass_1e10:.6g} x 10^10 Msun/h)",
            file=sys.stderr,
        )

        total_halos = 0
        with SplitWriter(
            output_path=output_path,
            output_format=output_format,
            n_output_files=n_output_files,
            n_trees_total=ctx.n_trees_convert,
            particle_mass=particle_mass_1e10,
        ) as writer:
            for tree_idx, root in enumerate(
                tqdm(ctx.sorted_roots[: ctx.n_trees_convert], desc="Converting trees")
            ):
                fields = _build_tree_field_dict(tree_idx, root, ctx)
                writer.write_tree(fields)
                total_halos += len(fields["Descendant"])

        print(
            f"  Done: {ctx.n_trees_convert} trees, {total_halos} halos. "
            f"Output: {writer.output_paths}",
            file=sys.stderr,
        )

    except ConversionError:
        raise
    except SystemExit:
        raise
    except Exception as exc:
        import traceback

        traceback.print_exc(file=sys.stderr)
        print(f"ERROR: conversion failed - {exc}", file=sys.stderr)
        raise ConversionError(f"conversion failed - {exc}") from exc
