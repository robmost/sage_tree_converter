"""
rockstar_consistent_trees_ascii.py — Driver for Rockstar + Consistent Trees ASCII format.

Input:  a directory containing tree_*.dat files from Consistent Trees, and optionally
        forests.list + locations.dat (standard CTrees ancillary files).
Output: a single SAGE LHaloTree HDF5 or binary file.

File structure of each tree_*.dat:
  <N_trees_in_file>           ← integer on its own line (skipped)
  #scale(0) id(1) ...         ← column-name comment (ignored by parser)
  #Omega_M = ...; h0 = ...    ← cosmology header (parsed for particle mass)
  ...more comments...
  #tree <Tree_root_ID>        ← tree-block delimiter
  <halo row 0>                ← 59+ space-separated values (depth-first order)
  <halo row 1>
  ...
  #tree <next_Tree_root_ID>
  ...

Column layout (0-based, 59 minimum; some outputs add extra trailing columns):
  0  scale      6  upid     12 rs      18 y    24 Jy   30 Orig_halo_ID
  1  id         7  desc_pid 13 vrms    19 z    25 Jz   31 Snap_num
  2  desc_scale 8  phantom  14 mmp?    20 vx   26 Spin 32 Next_coprog_DFI
  3  desc_id    9  sam_mvir 15 scl_MM  21 vy   27 bf_ID 33 Last_prog_DFI
  4  num_prog   10 mvir     16 vmax    22 vz   28 DFI  34 Last_mainleaf_DFI
  5  pid        11 rvir     17 x       23 Jx   29 Tree_root_ID
  35 Tidal_Force 36 Tidal_ID 37 Rs_Klypin 38 Mvir_all 39 M200b 40 M200c
  ...
  Extra trailing columns (e.g. Halfmass_Radius, rvmax in Shin-Uchuu / micro-uchuu)
  are silently ignored.

Pointer reconstruction (all O(N) or O(N log N)):
  Halos within each #tree block are in depth-first order.
  Descendant:         desc_id → combined-array index via id→idx dict
  FirstProgenitor:    halos[i+1] if halos[i+1].desc_id == halos[i].id
  NextProgenitor:     Next_coprog_DFI looked up in dfi→index dict (DFIs are global
                      sequential integers assigned across all tree blocks in the file)
  FirstHaloInFOFGroup: upid → combined-array index via id→idx dict; self if upid==-1
                       or cross-forest reference (upid not in combined id set)
  NextHaloInFOFGroup: group by (snap, central_idx), sort by mvir desc, singly-linked

Forest-level processing (when forests.list + locations.dat are present):
  Consistent Trees assigns each #tree block a forest ID via forests.list.  Within a
  forest, halos in different tree blocks can share a FOF group at some snapshot, so
  upid references cross tree-block boundaries.  The driver loads all available tree
  blocks for a forest together, concatenates them into one array, sorts the combined
  array by DFI unconditionally (even for single-tree forests, where file order may
  not be strict DFI order), and calls _reconstruct_pointers on the sorted array.
  Forests are processed in forests.list appearance order so that test clips
  are consistent with reference implementations.  Each .dat file is opened once and
  its handle is reused across all reads.

Field conversions:
  SubhaloLen   = round(mvir / particle_mass)   [estimated; see known_caveats]
  SubhaloSpin  = [Jx, Jy, Jz] / mvir           [(Mpc/h)(km/s) specific j]
  Group_M_*    = M200c / M200b / mvir * 1e-10   [Msun/h → 1e10 Msun/h]
"""

import os
import re
import sys
from collections import defaultdict
from collections.abc import Generator
from contextlib import ExitStack
from pathlib import Path
from typing import BinaryIO

import numpy as np
from tqdm import tqdm

from utils.split_writer import SplitWriter

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

_NCOLS_MIN = 59  # minimum expected; extra trailing columns are silently ignored
_RHO_CRIT0_H2 = 2.775e11  # h^2 Msun / Mpc^3
_N_SIDE_DEFAULT = 2048  # default particle grid size (BolshoiP / micro-uchuu)


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


def _collect_root_ids_from_files(tree_files: list[Path]) -> set[int]:
    """Scan tree files and return the set of tree root IDs found in #tree markers.

    Reads only the comment lines; halo data rows are skipped.  Used to scope
    forest.list / locations.dat loading to the trees actually present in this
    task's input files (forest-scoped loading).
    """
    root_ids: set[int] = set()
    for fp in tree_files:
        with open(fp) as fh:
            for line in fh:
                if line.startswith("#tree"):
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            root_ids.add(int(parts[1]))
                        except ValueError:
                            pass
    return root_ids


def _count_trees_quick(tree_files: list[Path], n_limit: int | None = None) -> int:
    """Count #tree markers across tree files without reading any halo data."""
    count = 0
    for fp in tree_files:
        with open(fp) as fh:
            for line in fh:
                if line.startswith("#tree"):
                    count += 1
                    if n_limit is not None and count >= n_limit:
                        return count
    return count


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


def _compute_particle_mass(omega_m: float, box_size: float, n_side: int = _N_SIDE_DEFAULT) -> float:
    """Dark matter particle mass in Msun/h.

    m_p = Omega_M * rho_crit0 * L_box^3 / N_particles
    where L_box is in Mpc/h and rho_crit0 = 2.775e11 h^2 Msun/Mpc^3.
    """
    return omega_m * _RHO_CRIT0_H2 * (box_size**3) / (float(n_side) ** 3)


def _resolve_particle_mass(
    header_text: str, sim_params: dict | None
) -> tuple[float, float, float, str]:
    """Resolve particle mass (Msun/h) and the cosmology used, shared by convert/read_trees.

    Applies the same override precedence to both code paths so SubhaloLen is
    consistent between the converted output and the semantic-validation reference.

    Returns
    -------
    (particle_mass_msun_per_h, omega_m, box_size, detail)
        ``detail`` is the parenthetical source description convert() prints; it is
        unused by read_trees().
    """
    omega_m, box_size = _parse_cosmology(header_text)
    _sp = sim_params or {}
    if _sp.get("omega_m") is not None:
        omega_m = float(_sp["omega_m"])
    if _sp.get("box_size_mpc_per_h") is not None:
        box_size = float(_sp["box_size_mpc_per_h"])
    n_side_override = _sp.get("n_particles_per_side")

    _pm_override = _sp.get("particle_mass_msun_per_h")
    if _pm_override is not None:
        return float(_pm_override), omega_m, box_size, "sim-config override"
    if n_side_override is not None:
        pm = _compute_particle_mass(omega_m, box_size, int(n_side_override))
        return pm, omega_m, box_size, f"computed, n_side={n_side_override}"
    pm = _compute_particle_mass(omega_m, box_size, _N_SIDE_DEFAULT)
    return (
        pm,
        omega_m,
        box_size,
        f"computed, n_side={_N_SIDE_DEFAULT} default — "
        "use --sim-config to override if N_particles differs",
    )


# ---------------------------------------------------------------------------
# Streaming tree parser
# ---------------------------------------------------------------------------


def _read_header_text(filepath: Path) -> str:
    """Return the concatenated comment lines before the first #tree marker."""
    lines: list[str] = []
    with open(filepath) as fh:
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
) -> Generator[np.ndarray]:
    """Yield one (N, _NCOLS) float64 ndarray per #tree block."""
    current_rows: list[list[float]] = []
    first_noncomment_seen = False
    n_yielded = 0

    with open(filepath) as fh:
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


# ---------------------------------------------------------------------------
# Pointer reconstruction
# ---------------------------------------------------------------------------


def _reconstruct_pointers(halos: np.ndarray) -> dict[str, np.ndarray]:
    """Build all five LHaloTree pointer arrays for a halo array.

    Parameters
    ----------
    halos : ndarray, shape (N, _NCOLS), dtype float64
        Halo data — may span multiple #tree blocks when called in forest mode.

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
    nxt_prog = np.full(n, -1, dtype=np.int32)
    for i in range(n):
        nc_dfi = int(next_coprog_dfis[i])
        if nc_dfi != -1:
            nxt_prog[i] = dfi_to_idx.get(nc_dfi, -1)

    # ---- FirstHaloInFOFGroup -----------------------------------------------
    # Unresolvable upid references (cross-forest / cross-file) become self-pointers.
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
                # Cross-forest/cross-file reference: treat as own central
                fhifof[current] = current
                root = current
                break
            path.append(current)
            current = parent
        for h in path:
            fhifof[h] = root

    # ---- NextHaloInFOFGroup ------------------------------------------------
    # Group halos by (snap, central_idx); sort by mvir descending;
    # build singly-linked list: central → sat_0 → sat_1 → ... → -1.
    nhifof = np.full(n, -1, dtype=np.int32)
    groups: dict[tuple[int, int], list[tuple[float, int]]] = defaultdict(list)
    for i in range(n):
        key = (int(snaps[i]), int(fhifof[i]))
        groups[key].append((float(mvirs[i]), i))

    for members in groups.values():
        members.sort(key=lambda x: x[0], reverse=True)
        idxs = [idx for _, idx in members]
        for j in range(len(idxs) - 1):
            nhifof[idxs[j]] = idxs[j + 1]

    return {
        "Descendant": desc,
        "FirstProgenitor": fp,
        "NextProgenitor": nxt_prog,
        "FirstHaloInFOFGroup": fhifof,
        "NextHaloInFOFGroup": nhifof,
    }


# ---------------------------------------------------------------------------
# Forest-level support (forests.list + locations.dat)
# ---------------------------------------------------------------------------


def _parse_forests_list(
    path: Path,
    root_id_filter: set[int] | None = None,
) -> tuple[dict[int, int], dict[int, list[int]], list[int]]:
    """Parse forests.list → (tree_to_forest, forest_to_trees, forest_order).

    forests.list format:
        #TreeRootID ForestID
        28456576    28437782

    forest_order preserves forests.list first-appearance order so that
    test clips are consistent with reference implementations.

    Parameters
    ----------
    root_id_filter : set[int] or None
        When provided, only load entries whose TreeRootID is in this set.
        This scopes loading to the trees present in the current task's input
        files, avoiding the full forests.list cost for SLURM array jobs.
    """
    tree_to_forest: dict[int, int] = {}
    forest_to_trees: dict[int, list[int]] = {}
    forest_order: list[int] = []
    with open(path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            tid, fid = int(parts[0]), int(parts[1])
            if root_id_filter is not None and tid not in root_id_filter:
                continue
            tree_to_forest[tid] = fid
            if fid not in forest_to_trees:
                forest_to_trees[fid] = []
                forest_order.append(fid)
            forest_to_trees[fid].append(tid)
    return tree_to_forest, forest_to_trees, forest_order


def _parse_locations(
    path: Path,
    input_dir: Path,
    root_id_filter: set[int] | None = None,
) -> tuple[dict[int, tuple[Path, int]], list[int]]:
    """Parse locations.dat → (tree_offsets, ordered_tree_ids).

    locations.dat format:
        #TreeRootID FileID Offset Filename
        28456576    0      3663   tree_0_0_0.dat

    Parameters
    ----------
    root_id_filter : set[int] or None
        When provided, only load entries whose TreeRootID is in this set.

    Returns
    -------
    tree_offsets     : tree_root_id → (filepath, byte_offset)
    ordered_tree_ids : tree root IDs sorted by ascending byte offset
                       (= file-appearance order)
    """
    records: list[tuple[int, Path, int]] = []  # (offset, filepath, tree_id)
    with open(path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            tid = int(parts[0])
            if root_id_filter is not None and tid not in root_id_filter:
                continue
            offset = int(parts[2])
            filename = parts[3]
            filepath = input_dir / filename
            records.append((offset, filepath, tid))
    records.sort()  # ascending byte offset = file-appearance order
    tree_offsets = {tid: (fp, off) for off, fp, tid in records}
    ordered_tree_ids = [tid for _, _, tid in records]
    return tree_offsets, ordered_tree_ids


def _read_tree_block(fh: BinaryIO, offset: int) -> np.ndarray:
    """Read one #tree block from an open binary file handle at byte offset.

    The offset may point to the '#tree <root_id>' line itself or to the
    first data line after it; both cases are handled.  Stops at the first
    blank line or any '#' line after the initial '#tree' marker.
    """
    rows: list[list[float]] = []
    fh.seek(offset)
    first_line = True
    for raw in fh:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            break  # blank line terminates the block
        if line.startswith("#tree"):
            if first_line:
                first_line = False
                continue  # skip our own #tree marker
            break  # hit the next tree block — stop
        if line.startswith("#"):
            break  # any other comment after the header terminates the block
        first_line = False
        try:
            rows.append([float(v) for v in line.split()])
        except ValueError:
            pass
    if not rows:
        return np.empty((0, _NCOLS_MIN), dtype=np.float64)
    return np.array(rows, dtype=np.float64)


# ---------------------------------------------------------------------------
# Shared field builder
# ---------------------------------------------------------------------------


def _build_fields(halos: np.ndarray, particle_mass_msun_per_h: float) -> dict:
    """Reconstruct pointers and build the complete SAGE field dict."""
    n = len(halos)
    ptrs = _reconstruct_pointers(halos)
    mvir = halos[:, _C_MVIR]
    jx, jy, jz = halos[:, _C_JX], halos[:, _C_JY], halos[:, _C_JZ]
    with np.errstate(invalid="ignore", divide="ignore"):
        inv_mvir = np.where(mvir > 0, 1.0 / mvir, 0.0)
    spin = np.column_stack([jx * inv_mvir, jy * inv_mvir, jz * inv_mvir])
    return {
        **ptrs,
        "SubhaloLen": np.round(mvir / particle_mass_msun_per_h).astype(np.int32),
        "SnapNum": halos[:, _C_SNAP_NUM].astype(np.int32),
        "SubhaloIDMostBound": np.full(n, -1, dtype=np.int64),
        "FileNr": np.full(n, -1, dtype=np.int32),
        "Group_M_Crit200": (halos[:, _C_M200C] * 1e-10).astype(np.float32),
        "Group_M_Mean200": (halos[:, _C_M200B] * 1e-10).astype(np.float32),
        "Group_M_TopHat200": (mvir * 1e-10).astype(np.float32),
        "SubhaloVMax": halos[:, _C_VMAX].astype(np.float32),
        "SubhaloVelDisp": (halos[:, _C_VRMS] / np.sqrt(3.0)).astype(np.float32),
        "SubhaloPos": (
            np.column_stack([halos[:, _C_X], halos[:, _C_Y], halos[:, _C_Z]]) * 1000.0
        ).astype(np.float32),
        "SubhaloVel": np.column_stack([halos[:, _C_VX], halos[:, _C_VY], halos[:, _C_VZ]]).astype(
            np.float32
        ),
        "SubhaloSpin": (spin * 1000.0).astype(np.float32),
    }


# ---------------------------------------------------------------------------
# Output-unit iterators (forest mode / tree mode)
# ---------------------------------------------------------------------------


def _prepare_forest_mode(
    tree_files: list[Path],
    forests_list_path: Path,
    locations_path: Path,
) -> tuple[list[tuple[int, list[int]]], dict[int, tuple[Path, int]]]:
    """Build forest queue and tree-offset map with forest-scoped loading.

    Scans the input tree files for #tree root IDs, then filters forests.list
    and locations.dat to only the entries relevant to those IDs.  This keeps
    memory proportional to the trees in the current task rather than the full
    simulation, which is essential for SLURM array jobs where many tasks each
    process a different subset of tree files.

    Returns
    -------
    forest_queue : list of (forest_id, [tree_root_ids]) in forests.list order
    tree_offsets : tree_root_id → (filepath, byte_offset)
    """
    input_dir = tree_files[0].parent
    root_id_filter = _collect_root_ids_from_files(tree_files)
    _, forest_to_trees, forest_order = _parse_forests_list(forests_list_path, root_id_filter)
    tree_offsets, _ = _parse_locations(locations_path, input_dir, root_id_filter)

    forest_queue: list[tuple[int, list[int]]] = []
    for fid in forest_order:
        expected_trees = forest_to_trees.get(fid, [fid])
        available_trees = [
            t for t in expected_trees
            if t in tree_offsets and tree_offsets[t][0].exists()
        ]
        if available_trees:
            forest_queue.append((fid, available_trees))

    return forest_queue, tree_offsets


def _forest_mode_units(
    tree_files: list[Path],
    forests_list_path: Path,
    locations_path: Path,
    n_limit: int | None,
    _precomputed: tuple | None = None,
) -> Generator[np.ndarray]:
    """Yield one halo array per SAGE output tree using forest-level processing.

    All available tree blocks for a forest are concatenated and DFI-sorted
    before pointer reconstruction — unconditionally, including single-tree
    forests where file order may not be strict DFI order.  Forests are
    visited in forests.list appearance order.  Each .dat file is opened once
    and its handle is reused across all tree blocks it contains.

    Parameters
    ----------
    _precomputed : (forest_queue, tree_offsets) or None
        Pass the output of _prepare_forest_mode() to skip the setup phase when
        the caller has already computed these structures (e.g. convert()).
    """
    if _precomputed is not None:
        forest_queue, tree_offsets = _precomputed
    else:
        forest_queue, tree_offsets = _prepare_forest_mode(
            tree_files, forests_list_path, locations_path
        )

    needed_files: set[Path] = {
        tree_offsets[tid][0]
        for _, available_trees in forest_queue
        for tid in available_trees
    }

    n_done = 0
    with ExitStack() as stack:
        file_handles: dict[Path, BinaryIO] = {
            fp: stack.enter_context(open(fp, "rb"))  # noqa: SIM115
            for fp in needed_files
        }

        for _fid, available_trees in tqdm(forest_queue, desc="Converting forests", unit="forest"):
            if n_limit is not None and n_done >= n_limit:
                break

            arrays: list[np.ndarray] = []
            for tid in available_trees:
                fp, off = tree_offsets[tid]
                arr = _read_tree_block(file_handles[fp], off)
                if len(arr) > 0 and arr.shape[1] >= _NCOLS_MIN:
                    arrays.append(arr)

            if arrays:
                combined = np.concatenate(arrays, axis=0)
                yield combined[np.argsort(combined[:, _C_DFI])]
                n_done += 1


def _tree_mode_units(
    tree_files: list[Path],
    n_limit: int | None,
) -> Generator[np.ndarray]:
    """Yield one halo array per #tree block (original tree-level behaviour)."""
    n_done = 0
    for tf in tree_files:
        remaining = None if n_limit is None else (n_limit - n_done)
        if remaining is not None and remaining <= 0:
            break
        for halos in tqdm(_generate_trees(tf, remaining), desc="Converting trees", unit="tree"):
            if len(halos) > 0 and halos.shape[1] >= _NCOLS_MIN:
                yield halos
                n_done += 1


def _get_output_units(
    tree_files: list[Path],
    n_limit: int | None,
    forests_list_path: Path | None,
    locations_path: Path | None,
    _precomputed: tuple | None = None,
) -> Generator[np.ndarray]:
    """Route to forest-mode or tree-mode iterator based on ancillary files."""
    if (
        forests_list_path is not None
        and forests_list_path.exists()
        and locations_path is not None
        and locations_path.exists()
    ):
        yield from _forest_mode_units(
            tree_files, forests_list_path, locations_path, n_limit,
            _precomputed=_precomputed,
        )
    else:
        yield from _tree_mode_units(tree_files, n_limit)


# ---------------------------------------------------------------------------
# Public read_trees() — load input without writing output
# ---------------------------------------------------------------------------


def read_trees(
    input_path: str,
    n_trees: int | None = None,
    sim_params: dict | None = None,
) -> dict[int, dict]:
    """Read Consistent Trees ASCII files into the SAGE LHaloTree schema.

    Uses the same forest-level / tree-level routing as convert() so that
    the semantic-validation reference matches the converted output exactly.

    Parameters
    ----------
    input_path : str
        Path to a single tree_*.dat file or a directory containing them.
    n_trees : int or None
        If given, read only the first n_trees output units.
    sim_params : dict or None
        Simulation parameter overrides (same keys as --sim-config JSON).
        Keys used: particle_mass_msun_per_h, n_particles_per_side,
        box_size_mpc_per_h, omega_m. Must match what was passed to convert()
        so that SubhaloLen values are consistent between input and output columns.

    Returns
    -------
    dict[int, dict[str, np.ndarray]]
        unit_idx (0-based) → field dict.
        SubhaloPos in kpc/h, SubhaloSpin in (kpc/h)(km/s), masses in 1e10 Msun/h.
    """
    tree_files = _discover_tree_files(input_path)
    input_dir = tree_files[0].parent
    header_text = _read_header_text(tree_files[0])
    particle_mass_msun_per_h, _, _, _ = _resolve_particle_mass(header_text, sim_params)

    forests_list_path: Path | None = input_dir / "forests.list"
    locations_path: Path | None = input_dir / "locations.dat"

    if not (forests_list_path.exists() and locations_path.exists()):
        print(
            "WARNING: forests.list / locations.dat not found — falling back to per-tree mode. "
            "Cross-tree upid references cannot be resolved: satellites whose host central "
            "resides in a different #tree block will be treated as isolated centrals, "
            "producing incorrect FOF group pointers and underproducing massive galaxies in SAGE. "
            "Re-run Consistent Trees with the -F flag to generate these files.",
            file=sys.stderr,
        )

    result: dict[int, dict] = {}
    for unit_idx, halos in enumerate(
        _get_output_units(tree_files, n_trees, forests_list_path, locations_path)
    ):
        result[unit_idx] = _build_fields(halos, particle_mass_msun_per_h)

    return result


# ---------------------------------------------------------------------------
# Main convert function
# ---------------------------------------------------------------------------


def convert(
    input_path: str,
    output_path: str,
    n_trees: int | None = None,
    sim_params: dict | None = None,
    output_format: str = "lhalo_hdf5",
    n_output_files: int = 1,
) -> None:
    """Convert Consistent Trees ASCII files to SAGE LHaloTree HDF5 or binary format.

    Parameters
    ----------
    input_path : str
        Path to a single tree_*.dat file, or a directory containing them.
    output_path : str
        Path for the first output file (index 0).  When n_output_files > 1,
        additional files are created by replacing the trailing index token
        (e.g. "_STC.0" → "_STC.1", "_STC.2", …).
    n_trees : int or None
        If given, convert only the first n_trees output units (forests in
        forest mode, individual trees in tree mode).
    sim_params : dict or None
        Simulation parameter overrides from --sim-config JSON.
        Keys used: particle_mass_msun_per_h (Msun/h), n_particles_per_side,
        box_size_mpc_per_h, omega_m. All optional; header-parsed values are
        used as fallback.
    output_format : str
        'lhalo_hdf5' (default) or 'lhalo_binary'.
    n_output_files : int
        Number of output files to produce (default 1).  Trees are distributed
        as evenly as possible across files.  Must be ≥ 1.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    try:
        tree_files = _discover_tree_files(input_path)
        print(f"Found {len(tree_files)} tree file(s): {[f.name for f in tree_files]}")

        input_dir = tree_files[0].parent
        forests_list_path = input_dir / "forests.list"
        locations_path = input_dir / "locations.dat"
        use_forest_mode = forests_list_path.exists() and locations_path.exists()

        # --- Determine total tree count and (for forest mode) pre-compute
        #     the forest queue so we don't read forests.list twice. ---
        if use_forest_mode:
            print(
                "Found forests.list and locations.dat — using forest-level mode "
                "(cross-tree FOF groups resolved within each complete forest)."
            )
            forest_queue, tree_offsets = _prepare_forest_mode(
                tree_files, forests_list_path, locations_path
            )
            n_trees_available = len(forest_queue)
            precomputed = (forest_queue, tree_offsets)
        else:
            print(
                "WARNING: forests.list / locations.dat not found — falling back to per-tree mode. "
                "Cross-tree upid references cannot be resolved: satellites whose host central "
                "resides in a different #tree block will be treated as isolated centrals, "
                "producing incorrect FOF group pointers and underproducing massive galaxies "
                "in SAGE. Re-run Consistent Trees with the -F flag to generate these files.",
                file=sys.stderr,
            )
            n_trees_available = _count_trees_quick(tree_files)
            precomputed = None

        header_text = _read_header_text(tree_files[0])
        particle_mass_msun_per_h, omega_m, box_size, _pm_detail = _resolve_particle_mass(
            header_text, sim_params
        )
        print(f"Particle mass: {particle_mass_msun_per_h:.3e} Msun/h ({_pm_detail})")
        particle_mass_1e10 = particle_mass_msun_per_h * 1e-10
        print(
            f"Cosmology: Omega_M={omega_m}, box_size={box_size} Mpc/h, "
            f"particle_mass={particle_mass_msun_per_h:.3e} Msun/h "
            f"({particle_mass_1e10:.4f} × 10^10 Msun/h)"
        )

        n_trees_total = min(n_trees, n_trees_available) if n_trees else n_trees_available
        if n_trees_total == 0:
            print("ERROR: no trees found in input.", file=sys.stderr)
            sys.exit(1)

        fl_path = forests_list_path if use_forest_mode else None
        lo_path = locations_path if use_forest_mode else None

        n_trees_written = 0
        total_halos = 0

        with SplitWriter(
            output_path=output_path,
            output_format=output_format,
            n_output_files=n_output_files,
            n_trees_total=n_trees_total,
            particle_mass=particle_mass_1e10,
        ) as writer:
            tree_stream = _get_output_units(
                tree_files, n_trees, fl_path, lo_path,
                _precomputed=precomputed,
            )
            for halos in tree_stream:
                n = len(halos)
                if n == 0:
                    print(
                        f"ERROR: output unit {n_trees_written} has zero halos.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                writer.write_tree(_build_fields(halos, particle_mass_msun_per_h))
                n_trees_written += 1
                total_halos += n

        print(
            f"\nConverted {n_trees_written} SAGE trees, {total_halos} halos total. "
            f"Output: {writer.output_paths}"
        )

    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: conversion failed — {exc}", file=sys.stderr)
        sys.exit(1)
