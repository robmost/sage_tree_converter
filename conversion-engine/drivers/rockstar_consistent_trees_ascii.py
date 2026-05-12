"""
rockstar_consistent_trees_ascii.py — Driver for Rockstar + Consistent Trees ASCII format.

Input:  a directory containing tree_*.dat files from Consistent Trees.
Output: a single SAGE LHaloTree HDF5 or binary file.

File structure of each tree_*.dat:
  <N_trees_in_file>           ← integer on its own line (skipped)
  #scale(0) id(1) ...         ← column-name comment (ignored by parser)
  #Omega_M = ...; h0 = ...    ← cosmology header (parsed for particle mass)
  ...more comments...
  #tree <Tree_root_ID>        ← tree-block delimiter
  <halo row 0>                ← 59 space-separated values (depth-first order)
  <halo row 1>
  ...
  #tree <next_Tree_root_ID>
  ...

Column layout (0-based, 59 total):
  0  scale      6  upid     12 rs      18 y    24 Jy   30 Orig_halo_ID
  1  id         7  desc_pid 13 vrms    19 z    25 Jz   31 Snap_num
  2  desc_scale 8  phantom  14 mmp?    20 vx   26 Spin 32 Next_coprog_DFI
  3  desc_id    9  sam_mvir 15 scl_MM  21 vy   27 bf_ID 33 Last_prog_DFI
  4  num_prog   10 mvir     16 vmax    22 vz   28 DFI  34 Last_mainleaf_DFI
  5  pid        11 rvir     17 x       23 Jx   29 Tree_root_ID
  35 Tidal_Force 36 Tidal_ID 37 Rs_Klypin 38 Mvir_all 39 M200b 40 M200c
  41 M500c 42 M2500c 43 Xoff 44 Voff 45 Spin_Bullock 46 b_to_a 47 c_to_a
  48 A[x] 49 A[y] 50 A[z] 51 b_to_a(500c) 52 c_to_a(500c) 53-55 A(500c)
  56 T/|U| 57 M_pe_Behroozi 58 M_pe_Diemer

Pointer reconstruction (all O(N) or O(N log N)):
  Halos within each #tree block are in depth-first order.
  Descendant:         desc_id → tree-local index via id→idx dict
  FirstProgenitor:    halos[i+1] if halos[i+1].desc_id == halos[i].id
  NextProgenitor:     Next_coprog_DFI looked up in dfi→local_index dict (DFIs are global,
                      not sequential within a tree block)
  FirstHaloInFOFGroup: upid → tree-local index; self if upid==-1 or cross-forest
  NextHaloInFOFGroup: group by (snap, central), sort by mvir desc, singly-linked list

Field conversions:
  SubhaloLen   = round(mvir / particle_mass)   [estimated; see known_caveats]
  SubhaloSpin  = [Jx, Jy, Jz] / mvir           [(Mpc/h)(km/s) specific j]
  Group_M_*    = M200c / M200b / mvir * 1e-10   [Msun/h → 1e10 Msun/h]
"""

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import h5py
import numpy as np
from tqdm import tqdm
from utils import binary_writer, hdf5_writer

# ---------------------------------------------------------------------------
# Column indices (0-based)
# ---------------------------------------------------------------------------
_C_ID = 1
_C_DESC_ID = 3
_C_UPID = 6
_C_MVIR = 10
_C_VRMS = 13
_C_VMAX = 16
_C_X, _C_Y, _C_Z = 17, 18, 19
_C_VX, _C_VY, _C_VZ = 20, 21, 22
_C_JX, _C_JY, _C_JZ = 23, 24, 25
_C_DFI = 28
_C_SNAP_NUM = 31
_C_NEXT_COPROG_DFI = 32
_C_M200B = 39
_C_M200C = 40

_NCOLS_MIN = (
    59  # minimum expected; some outputs (e.g. Shin-Uchuu) add extra trailing columns
)
_RHO_CRIT0_H2 = 2.775e11  # h^2 Msun / Mpc^3
_N_SIDE_DEFAULT = 2048  # BolshoiP default


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def _discover_tree_files(input_path: str) -> list[Path]:
    """Return sorted list of tree_*.dat files from input_path."""
    p = Path(input_path)
    if p.is_file():
        return [p]
    if p.is_dir():
        pattern = re.compile(r"^tree_\d+_\d+_\d+\.dat$")
        found = sorted(f for f in p.iterdir() if pattern.match(f.name))
        if not found:
            raise ValueError(f"No tree_*.dat files found in '{input_path}'.")
        return found
    raise ValueError(f"'{input_path}' is neither a file nor a directory.")


# ---------------------------------------------------------------------------
# Header / cosmology parsing
# ---------------------------------------------------------------------------


def _parse_cosmology(header_text: str) -> tuple[float, float]:
    """Return (omega_m, box_size_mpc_per_h) from file comment header."""
    omega_m, box_size = 0.307115, 250.0
    m = re.search(r"Omega_M\s*=\s*([\d.]+)", header_text)
    if m:
        omega_m = float(m.group(1))
    m = re.search(r"box size\s*=\s*([\d.]+)", header_text)
    if m:
        box_size = float(m.group(1))
    return omega_m, box_size


def _compute_particle_mass(
    omega_m: float, box_size: float, n_side: int = _N_SIDE_DEFAULT
) -> float:
    """Dark matter particle mass in Msun/h.

    Derived from: m_p = Omega_M * rho_crit0 * L_box^3 / N_particles
    where L_box is in Mpc/h and rho_crit0 = 2.775e11 h^2 Msun/Mpc^3,
    giving units of Msun/h after the h factors cancel.
    """
    return omega_m * _RHO_CRIT0_H2 * (box_size**3) / (float(n_side) ** 3)


# ---------------------------------------------------------------------------
# Streaming tree parser
# ---------------------------------------------------------------------------


def _read_header_text(filepath: Path) -> str:
    """Return the concatenated comment lines before the first #tree marker."""
    lines: list[str] = []
    with open(filepath, "r") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#tree"):
                break
            if line.startswith("#"):
                lines.append(line)
    return "\n".join(lines)


def _generate_trees(
    filepath: Path,
    n_trees_limit: int | None,
):
    """Generator: yield one (N, _NCOLS) float64 ndarray per tree block.

    Memory-efficient: only one tree's data is in memory at a time.
    """
    current_rows: list[list[float]] = []
    first_noncomment_seen = False
    n_yielded = 0

    with open(filepath, "r") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue

            if line.startswith("#tree"):
                if current_rows:
                    yield np.array(current_rows, dtype=np.float64)
                    current_rows = []
                    n_yielded += 1
                    if n_trees_limit is not None and n_yielded >= n_trees_limit:
                        return
                continue

            if line.startswith("#"):
                continue

            if not first_noncomment_seen:
                first_noncomment_seen = True
                continue

            try:
                current_rows.append([float(v) for v in line.split()])
            except ValueError as exc:
                print(
                    f"ERROR: failed to parse data row in '{filepath}': {line!r} — {exc}",
                    file=sys.stderr,
                )
                sys.exit(1)

    if current_rows and (n_trees_limit is None or n_yielded < n_trees_limit):
        yield np.array(current_rows, dtype=np.float64)


def _stream_trees(
    filepath: Path,
    n_trees_limit: int | None,
) -> tuple[list[np.ndarray], str]:
    """Stream a tree_*.dat file and return (tree_arrays, header_text).

    Each element of tree_arrays is a 2-D float64 ndarray of shape (N_halos, _NCOLS).
    header_text contains all comment lines before the first #tree marker.
    Stops after n_trees_limit trees if given (None = all trees).
    """
    trees: list[np.ndarray] = []
    header_lines: list[str] = []
    current_rows: list[list[float]] = []
    first_noncomment_seen = False
    past_first_tree = False

    with open(filepath, "r") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue

            if line.startswith("#tree"):
                # Flush the completed tree block
                if current_rows:
                    trees.append(np.array(current_rows, dtype=np.float64))
                    current_rows = []
                    if n_trees_limit is not None and len(trees) >= n_trees_limit:
                        return trees, "\n".join(header_lines)
                past_first_tree = True
                continue

            if line.startswith("#"):
                if not past_first_tree:
                    header_lines.append(line)
                continue

            # First non-comment, non-blank line = total-tree-count integer; skip it
            if not first_noncomment_seen:
                first_noncomment_seen = True
                continue

            # Halo data row
            try:
                current_rows.append([float(v) for v in line.split()])
            except ValueError as exc:
                print(
                    f"ERROR: failed to parse data row in '{filepath}': {line!r} — {exc}",
                    file=sys.stderr,
                )
                sys.exit(1)

    # Flush the final tree block
    if current_rows and (n_trees_limit is None or len(trees) < n_trees_limit):
        trees.append(np.array(current_rows, dtype=np.float64))

    return trees, "\n".join(header_lines)


# ---------------------------------------------------------------------------
# Pointer reconstruction
# ---------------------------------------------------------------------------


def _reconstruct_pointers(halos: np.ndarray) -> dict[str, np.ndarray]:
    """Build all five LHaloTree pointer arrays for one tree block.

    Parameters
    ----------
    halos : ndarray, shape (N, _NCOLS), dtype float64
        Halo data for one #tree block in depth-first order.

    Returns
    -------
    dict with int32 arrays of length N:
      Descendant, FirstProgenitor, NextProgenitor,
      FirstHaloInFOFGroup, NextHaloInFOFGroup
    Sentinel value for "no link" is -1.
    """
    n = len(halos)
    ids = halos[:, _C_ID].astype(np.int64)
    desc_ids = halos[:, _C_DESC_ID].astype(np.int64)
    upids = halos[:, _C_UPID].astype(np.int64)
    dfis = halos[:, _C_DFI].astype(np.int64)
    next_coprog_dfis = halos[:, _C_NEXT_COPROG_DFI].astype(np.int64)
    snaps = halos[:, _C_SNAP_NUM].astype(np.int32)
    mvirs = halos[:, _C_MVIR]

    # O(N) dicts for fast lookups
    id_to_idx: dict[int, int] = {int(ids[i]): i for i in range(n)}
    # DFIs are NOT sequential within a tree block (they are global indices assigned
    # across the whole forest). Build an explicit dfi→local_index map.
    dfi_to_idx: dict[int, int] = {int(dfis[i]): i for i in range(n)}

    # ---- Descendant --------------------------------------------------------
    desc = np.full(n, -1, dtype=np.int32)
    for i in range(n):
        did = int(desc_ids[i])
        if did != -1:
            desc[i] = id_to_idx.get(did, -1)

    # ---- FirstProgenitor ---------------------------------------------------
    # In depth-first order: halos[i+1] is the first progenitor of halos[i]
    # iff halos[i+1].desc_id == halos[i].id.
    fp = np.full(n, -1, dtype=np.int32)
    for i in range(n - 1):
        if int(desc_ids[i + 1]) == int(ids[i]):
            fp[i] = i + 1

    # ---- NextProgenitor ----------------------------------------------------
    # Next_coprogenitor_DFI is the global DFI of the next sibling progenitor.
    # DFIs are NOT sequential within a tree block, so look up via dfi_to_idx dict.
    # If the DFI is absent (cross-forest reference), NextProgenitor stays -1.
    nxt_prog = np.full(n, -1, dtype=np.int32)
    for i in range(n):
        nc_dfi = int(next_coprog_dfis[i])
        if nc_dfi != -1:
            nxt_prog[i] = dfi_to_idx.get(nc_dfi, -1)

    # ---- FirstHaloInFOFGroup -----------------------------------------------
    # upid is the most massive DIRECT host, which may be an intermediate satellite
    # (sub-subhalo case). SAGE requires all halos to point to the ULTIMATE central
    # (the one at the top of the upid chain with upid == -1).
    # Use iterative path-compression traversal: O(N * alpha(N)).
    _UNVISITED = -2
    fhifof = np.full(n, _UNVISITED, dtype=np.int32)

    for start in range(n):
        if fhifof[start] != _UNVISITED:
            continue
        path: list[int] = []
        current = start
        while True:
            if fhifof[current] != _UNVISITED:
                root = int(fhifof[current])
                break
            upid = int(upids[current])
            if upid == -1:
                fhifof[current] = current
                root = current
                break
            parent = id_to_idx.get(upid, -1)
            if parent == -1:
                # Cross-forest reference: treat this halo as its own central
                fhifof[current] = current
                root = current
                break
            path.append(current)
            current = parent
        # Path compression: all halos visited point directly to root
        for h in path:
            fhifof[h] = root

    # ---- NextHaloInFOFGroup ------------------------------------------------
    # Group halos by (snap, central_idx); sort each group by mvir descending;
    # build singly-linked list: central → sat_0 → sat_1 → ... → -1.
    nhifof = np.full(n, -1, dtype=np.int32)
    groups: dict[tuple[int, int], list[tuple[float, int]]] = defaultdict(list)
    for i in range(n):
        key = (int(snaps[i]), int(fhifof[i]))
        groups[key].append((float(mvirs[i]), i))

    for members in groups.values():
        members.sort(key=lambda x: x[0], reverse=True)  # mvir descending
        idxs = [idx for _, idx in members]
        for j in range(len(idxs) - 1):
            nhifof[idxs[j]] = idxs[j + 1]
        # idxs[-1] stays at -1 (already initialised)

    return {
        "Descendant": desc,
        "FirstProgenitor": fp,
        "NextProgenitor": nxt_prog,
        "FirstHaloInFOFGroup": fhifof,
        "NextHaloInFOFGroup": nhifof,
    }


# ---------------------------------------------------------------------------
# Public read_trees() — load input without writing output
# ---------------------------------------------------------------------------


def read_trees(
    input_path: str,
    n_trees: int | None = None,
) -> dict[int, dict]:
    """Read Consistent Trees ASCII files into the SAGE LHaloTree schema.

    Reuses _discover_tree_files, _read_header_text, _parse_cosmology,
    _generate_trees, and _reconstruct_pointers without writing any output.
    Used by semantic validation to load the original input data as the
    reference (input) column.

    Returns
    -------
    dict[int, dict[str, np.ndarray]]
        tree_idx (0-based, matching convert() write order) → field dict.
        SubhaloPos in kpc/h, SubhaloSpin in (kpc/h)(km/s), masses in 1e10 Msun/h.
    """
    tree_files = _discover_tree_files(input_path)
    header_text = _read_header_text(tree_files[0])
    omega_m, box_size = _parse_cosmology(header_text)
    particle_mass_msun_per_h = _compute_particle_mass(
        omega_m, box_size, _N_SIDE_DEFAULT
    )

    result: dict[int, dict] = {}
    global_tree_idx = 0
    remaining = n_trees

    for tf in tree_files:
        limit = remaining
        for halos in tqdm(
            _generate_trees(tf, limit), desc="Reading trees", unit="tree"
        ):
            n = len(halos)
            if n == 0 or halos.shape[1] < _NCOLS_MIN:
                continue

            ptrs = _reconstruct_pointers(halos)
            mvir = halos[:, _C_MVIR]
            jx, jy, jz = halos[:, _C_JX], halos[:, _C_JY], halos[:, _C_JZ]
            with np.errstate(invalid="ignore", divide="ignore"):
                inv_mvir = np.where(mvir > 0, 1.0 / mvir, 0.0)
            spin = np.column_stack([jx * inv_mvir, jy * inv_mvir, jz * inv_mvir])

            result[global_tree_idx] = {
                **ptrs,
                "SubhaloLen": np.round(mvir / particle_mass_msun_per_h).astype(
                    np.int32
                ),
                "SnapNum": halos[:, _C_SNAP_NUM].astype(np.int32),
                "SubhaloIDMostBound": np.full(n, -1, dtype=np.int64),
                "FileNr": np.full(n, -1, dtype=np.int32),
                "Group_M_Crit200": (halos[:, _C_M200C] * 1e-10).astype(np.float32),
                "Group_M_Mean200": (halos[:, _C_M200B] * 1e-10).astype(np.float32),
                "Group_M_TopHat200": (mvir * 1e-10).astype(np.float32),
                "SubhaloVMax": halos[:, _C_VMAX].astype(np.float32),
                "SubhaloVelDisp": (halos[:, _C_VRMS] / np.sqrt(3.0)).astype(np.float32),
                "SubhaloPos": (
                    np.column_stack(
                        [
                            halos[:, _C_X],
                            halos[:, _C_Y],
                            halos[:, _C_Z],
                        ]
                    )
                    * 1000.0
                ).astype(np.float32),
                "SubhaloVel": np.column_stack(
                    [
                        halos[:, _C_VX],
                        halos[:, _C_VY],
                        halos[:, _C_VZ],
                    ]
                ).astype(np.float32),
                "SubhaloSpin": (spin * 1000.0).astype(np.float32),
            }
            global_tree_idx += 1

        if remaining is not None:
            remaining -= global_tree_idx
            if remaining <= 0:
                break

    return result


# ---------------------------------------------------------------------------
# Main convert function
# ---------------------------------------------------------------------------


def convert(
    input_path: str,
    output_path: str,
    n_trees: int | None = None,
    particle_mass: float | None = None,
    output_format: str = "lhalo_hdf5",
) -> None:
    """Convert Consistent Trees ASCII files to SAGE LHaloTree HDF5 or binary format.

    Parameters
    ----------
    input_path : str
        Path to a single tree_*.dat file, or a directory containing them.
    output_path : str
        Path for the output file.
    n_trees : int or None
        If given, convert only the first n_trees trees (Stage 2 test mode).
    particle_mass : float or None
        Dark matter particle mass in Msun/h. When supplied, overrides the value
        computed from the file header cosmology and _N_SIDE_DEFAULT. Use this
        when the simulation N_particles differs from the driver default (2048³).
    output_format : str
        'lhalo_hdf5' (default) writes HDF5 via utils.hdf5_writer.
        'lhalo_binary' writes SAGE binary (TreeType=0) via utils.binary_writer.
        Binary output accumulates all field dicts in memory before writing,
        because the binary header must physically precede all halo data.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    try:
        # ------------------------------------------------------------------
        # 1. Discover input files and read cosmology from the first file header
        # ------------------------------------------------------------------
        tree_files = _discover_tree_files(input_path)
        print(f"Found {len(tree_files)} tree file(s): {[f.name for f in tree_files]}")

        header_text = _read_header_text(tree_files[0])
        omega_m, box_size = _parse_cosmology(header_text)
        if particle_mass is not None:
            particle_mass_msun_per_h = particle_mass
            print(
                f"Particle mass: {particle_mass_msun_per_h:.3e} Msun/h (user-supplied override)"
            )
        else:
            particle_mass_msun_per_h = _compute_particle_mass(
                omega_m, box_size, _N_SIDE_DEFAULT
            )
            print(
                f"Particle mass computed from header (n_side={_N_SIDE_DEFAULT}): "
                f"{particle_mass_msun_per_h:.3e} Msun/h — "
                f"use --particle-mass to override if N_particles differs"
            )
        particle_mass_1e10 = particle_mass_msun_per_h * 1e-10
        print(
            f"Cosmology: Omega_M={omega_m}, box_size={box_size} Mpc/h, "
            f"particle_mass={particle_mass_msun_per_h:.3e} Msun/h "
            f"({particle_mass_1e10:.4f} × 10^10 Msun/h)"
        )

        # ------------------------------------------------------------------
        # 2. Conversion: parse trees and write output.
        #    lhalo_hdf5:   streaming — write each tree immediately, header last.
        #                  Peak memory = O(max single tree size).
        #    lhalo_binary: accumulate all field dicts, then write header + trees.
        #                  The binary header must physically precede halo data,
        #                  so counts must be known before any halo data is written.
        #                  Peak memory = O(total halos) ≈ output file size.
        # ------------------------------------------------------------------
        tree_n_halos: list[int] = []
        global_tree_idx = 0
        remaining = n_trees

        if output_format == "lhalo_binary":
            all_fields: list[dict] = []

            for tf in tree_files:
                limit = remaining
                for halos in tqdm(
                    _generate_trees(tf, limit),
                    desc="Reading trees (binary mode)",
                    unit="tree",
                ):
                    n = len(halos)
                    if n == 0:
                        print(
                            f"ERROR: tree {global_tree_idx} has zero halos.",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    if halos.shape[1] < _NCOLS_MIN:
                        print(
                            f"ERROR: tree {global_tree_idx}: expected at least {_NCOLS_MIN} columns, "
                            f"got {halos.shape[1]}.",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    ptrs = _reconstruct_pointers(halos)
                    mvir = halos[:, _C_MVIR]
                    jx, jy, jz = halos[:, _C_JX], halos[:, _C_JY], halos[:, _C_JZ]
                    with np.errstate(invalid="ignore", divide="ignore"):
                        inv_mvir = np.where(mvir > 0, 1.0 / mvir, 0.0)
                    spin = np.column_stack(
                        [jx * inv_mvir, jy * inv_mvir, jz * inv_mvir]
                    )

                    fields = {
                        **ptrs,
                        "SubhaloLen": np.round(mvir / particle_mass_msun_per_h).astype(
                            np.int32
                        ),
                        "SnapNum": halos[:, _C_SNAP_NUM].astype(np.int32),
                        "SubhaloIDMostBound": np.full(n, -1, dtype=np.int64),
                        "FileNr": np.full(n, -1, dtype=np.int32),
                        "Group_M_Crit200": (halos[:, _C_M200C] * 1e-10).astype(
                            np.float32
                        ),
                        "Group_M_Mean200": (halos[:, _C_M200B] * 1e-10).astype(
                            np.float32
                        ),
                        "Group_M_TopHat200": (mvir * 1e-10).astype(np.float32),
                        "SubhaloVMax": halos[:, _C_VMAX].astype(np.float32),
                        "SubhaloVelDisp": (halos[:, _C_VRMS] / np.sqrt(3.0)).astype(
                            np.float32
                        ),
                        "SubhaloPos": (
                            np.column_stack(
                                [
                                    halos[:, _C_X],
                                    halos[:, _C_Y],
                                    halos[:, _C_Z],
                                ]
                            )
                            * 1000.0
                        ).astype(np.float32),
                        "SubhaloVel": np.column_stack(
                            [
                                halos[:, _C_VX],
                                halos[:, _C_VY],
                                halos[:, _C_VZ],
                            ]
                        ).astype(np.float32),
                        "SubhaloSpin": (spin * 1000.0).astype(np.float32),
                    }

                    all_fields.append(fields)
                    tree_n_halos.append(n)
                    global_tree_idx += 1

                if remaining is not None:
                    remaining -= global_tree_idx
                    if remaining <= 0:
                        break

            n_trees_total = global_tree_idx
            if n_trees_total == 0:
                print("ERROR: no trees found in input.", file=sys.stderr)
                sys.exit(1)

            total_halos = sum(tree_n_halos)
            print(f"\nConverted {n_trees_total} trees, {total_halos} halos total.")

            with open(output_path, "wb") as f:
                binary_writer.write_header(
                    f,
                    particle_mass=particle_mass_1e10,
                    n_trees=n_trees_total,
                    total_halos=total_halos,
                    n_output_files=1,
                    tree_n_halos=tree_n_halos,
                )
                for idx, flds in enumerate(
                    tqdm(all_fields, desc="Writing binary trees", unit="tree")
                ):
                    binary_writer.write_tree(f, idx, flds)

        elif output_format == "lhalo_hdf5":
            with h5py.File(output_path, "w") as f:
                for tf in tree_files:
                    limit = remaining
                    for halos in tqdm(
                        _generate_trees(tf, limit),
                        desc="Converting trees",
                        unit="tree",
                    ):
                        n = len(halos)
                        if n == 0:
                            print(
                                f"ERROR: tree {global_tree_idx} has zero halos.",
                                file=sys.stderr,
                            )
                            sys.exit(1)

                        if halos.shape[1] < _NCOLS_MIN:
                            print(
                                f"ERROR: tree {global_tree_idx}: expected at least {_NCOLS_MIN} columns, "
                                f"got {halos.shape[1]}.",
                                file=sys.stderr,
                            )
                            sys.exit(1)

                        ptrs = _reconstruct_pointers(halos)
                        mvir = halos[:, _C_MVIR]
                        jx, jy, jz = halos[:, _C_JX], halos[:, _C_JY], halos[:, _C_JZ]
                        with np.errstate(invalid="ignore", divide="ignore"):
                            inv_mvir = np.where(mvir > 0, 1.0 / mvir, 0.0)
                        spin = np.column_stack(
                            [jx * inv_mvir, jy * inv_mvir, jz * inv_mvir]
                        )

                        fields = {
                            **ptrs,
                            "SubhaloLen": np.round(
                                mvir / particle_mass_msun_per_h
                            ).astype(np.int32),
                            "SnapNum": halos[:, _C_SNAP_NUM].astype(np.int32),
                            "SubhaloIDMostBound": np.full(n, -1, dtype=np.int64),
                            "FileNr": np.full(n, -1, dtype=np.int32),
                            "Group_M_Crit200": (halos[:, _C_M200C] * 1e-10).astype(
                                np.float32
                            ),
                            "Group_M_Mean200": (halos[:, _C_M200B] * 1e-10).astype(
                                np.float32
                            ),
                            "Group_M_TopHat200": (mvir * 1e-10).astype(np.float32),
                            "SubhaloVMax": halos[:, _C_VMAX].astype(np.float32),
                            "SubhaloVelDisp": (halos[:, _C_VRMS] / np.sqrt(3.0)).astype(
                                np.float32
                            ),
                            "SubhaloPos": (
                                np.column_stack(
                                    [
                                        halos[:, _C_X],
                                        halos[:, _C_Y],
                                        halos[:, _C_Z],
                                    ]
                                )
                                * 1000.0
                            ).astype(np.float32),
                            "SubhaloVel": np.column_stack(
                                [
                                    halos[:, _C_VX],
                                    halos[:, _C_VY],
                                    halos[:, _C_VZ],
                                ]
                            ).astype(np.float32),
                            "SubhaloSpin": (spin * 1000.0).astype(np.float32),
                        }

                        hdf5_writer.write_tree(f, global_tree_idx, fields)
                        tree_n_halos.append(n)
                        global_tree_idx += 1

                    if remaining is not None:
                        remaining -= global_tree_idx
                        if remaining <= 0:
                            break

                n_trees_total = global_tree_idx
                if n_trees_total == 0:
                    print("ERROR: no trees found in input.", file=sys.stderr)
                    sys.exit(1)

                total_halos = sum(tree_n_halos)
                print(f"\nConverted {n_trees_total} trees, {total_halos} halos total.")

                # Write header after all trees so counts are exact
                hdf5_writer.write_header(
                    f,
                    particle_mass=particle_mass_1e10,
                    n_trees=n_trees_total,
                    total_halos=total_halos,
                    n_output_files=1,
                    tree_n_halos=tree_n_halos,
                )

        else:
            print(f"ERROR: unknown output_format '{output_format}'.", file=sys.stderr)
            sys.exit(1)

    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: conversion failed — {exc}", file=sys.stderr)
        if os.path.exists(output_path):
            os.remove(output_path)
        sys.exit(1)
