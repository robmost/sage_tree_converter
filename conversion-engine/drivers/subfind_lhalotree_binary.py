"""
subfind_lhalotree_binary.py — Driver for the classic LHaloTree binary format.

Reads the Gadget-2/Subfind LHaloTree binary files produced by the Millennium
Simulation pipeline (e.g. trees_063.0 – trees_063.7) and writes a single
SAGE LHaloTree HDF5 or binary file.

Binary layout per file:
  int32  NTrees
  int32  TotNHalos
  int32  TreeNHalos[NTrees]
  HaloData[TotNHalos]          -- packed flat array, 104 bytes per record

HaloData struct (104 bytes, little-endian):
  int32  Descendant, FirstProgenitor, NextProgenitor
  int32  FirstHaloInFOFGroup, NextHaloInFOFGroup
  int32  Len
  float  M_Mean200, M_Crit200, M_TopHat
  float  Pos[3], Vel[3]
  float  VelDisp, Vmax
  float  Spin[3]
  int64  MostBoundID
  int32  SnapNum, FileNr, SubhaloIndex
  float  SubHalfMass

Field mapping to SAGE LHaloTree HDF5 schema: rename-only, no unit conversions.
SubhaloIndex and SubHalfMass are read but discarded (not in schema).
"""

import os
import re
import sys
from pathlib import Path

import h5py
import numpy as np
from tqdm import tqdm

from utils import binary_writer, hdf5_writer

# Dark matter particle mass for the Millennium / mini-Millennium simulation
# (Springel et al. 2005). Units: 10^10 Msun/h.
PARTICLE_MASS = 0.0860

HALO_DTYPE = np.dtype([
    ("Descendant",          np.int32),
    ("FirstProgenitor",     np.int32),
    ("NextProgenitor",      np.int32),
    ("FirstHaloInFOFGroup", np.int32),
    ("NextHaloInFOFGroup",  np.int32),
    ("Len",                 np.int32),
    ("M_Mean200",           np.float32),
    ("M_Crit200",           np.float32),
    ("M_TopHat",            np.float32),
    ("Pos",                 np.float32, 3),
    ("Vel",                 np.float32, 3),
    ("VelDisp",             np.float32),
    ("Vmax",                np.float32),
    ("Spin",                np.float32, 3),
    ("MostBoundID",         np.int64),
    ("SnapNum",             np.int32),
    ("FileNr",              np.int32),
    ("SubhaloIndex",        np.int32),
    ("SubHalfMass",         np.float32),
])  # 104 bytes per halo — confirmed against mini-Millennium file sizes


def _discover_files(input_path: str) -> list[Path]:
    """Return sorted list of LHaloTree binary files from input_path.

    Accepts either a single file or a directory. When a directory is given,
    all files matching the pattern trees_<snap>.<N> (where N is an integer)
    are collected and sorted by N.
    """
    p = Path(input_path)
    if p.is_file():
        return [p]
    if p.is_dir():
        pattern = re.compile(r"^trees_\d+\.(\d+)$")
        found = []
        for f in p.iterdir():
            m = pattern.match(f.name)
            if m:
                found.append((int(m.group(1)), f))
        if not found:
            raise ValueError(
                f"No LHaloTree binary files (trees_<snap>.<N>) found in '{input_path}'."
            )
        found.sort(key=lambda x: x[0])
        return [f for _, f in found]
    raise ValueError(f"Input path '{input_path}' is neither a file nor a directory.")


def _read_file_header(fp) -> tuple[int, np.ndarray]:
    """Read NTrees, TotNHalos, and TreeNHalos from an open binary file.

    Returns (n_trees, tree_n_halos) where tree_n_halos is a 1-D int32 array
    of length n_trees. The file pointer is left positioned at the start of
    the flat halo array.
    """
    n_trees = np.frombuffer(fp.read(4), dtype=np.int32)[0]
    tot_n_halos = np.frombuffer(fp.read(4), dtype=np.int32)[0]
    tree_n_halos = np.frombuffer(fp.read(n_trees * 4), dtype=np.int32).copy()
    if tree_n_halos.sum() != tot_n_halos:
        raise ValueError(
            f"Header inconsistency: sum(TreeNHalos)={tree_n_halos.sum()} "
            f"!= TotNHalos={tot_n_halos}."
        )
    return n_trees, tree_n_halos


def _build_fields(halos: np.ndarray) -> dict:
    """Build the canonical field dict from a structured halo array.

    Output units match HDF5 on-disk convention:
      SubhaloPos  in kpc/h  (halos["Pos"]  is Mpc/h, multiplied by 1000)
      SubhaloSpin in (kpc/h)(km/s) (halos["Spin"] is (Mpc/h)(km/s), multiplied by 1000)
    binary_writer divides both back by 1000 before packing.
    """
    return {
        "Descendant":          halos["Descendant"],
        "FirstProgenitor":     halos["FirstProgenitor"],
        "NextProgenitor":      halos["NextProgenitor"],
        "FirstHaloInFOFGroup": halos["FirstHaloInFOFGroup"],
        "NextHaloInFOFGroup":  halos["NextHaloInFOFGroup"],
        "SubhaloLen":          halos["Len"],
        "Group_M_Crit200":     halos["M_Crit200"],
        "Group_M_Mean200":     halos["M_Mean200"],
        "Group_M_TopHat200":   halos["M_TopHat"],
        "SubhaloPos":          (halos["Pos"]  * np.float32(1000.0)).astype(np.float32),
        "SubhaloVel":          halos["Vel"],
        "SubhaloVelDisp":      halos["VelDisp"],
        "SubhaloVMax":         halos["Vmax"],
        "SubhaloSpin":         (halos["Spin"] * np.float32(1000.0)).astype(np.float32),
        "SubhaloIDMostBound":  halos["MostBoundID"],
        "SnapNum":             halos["SnapNum"],
        "FileNr":              halos["FileNr"],
    }


def read_trees(
    input_path: str,
    n_trees: int | None = None,
) -> dict[int, dict]:
    """Read LHaloTree binary files into the SAGE LHaloTree schema without writing output.

    Reuses _discover_files, _read_file_header, and _build_fields. Used by
    semantic validation to load the original input data as the reference column.

    Returns
    -------
    dict[int, dict[str, np.ndarray]]
        tree_idx (0-based, matching convert() write order) → field dict.
        SubhaloPos in kpc/h, SubhaloSpin in (kpc/h)(km/s), masses in 1e10 Msun/h.
    """
    files = _discover_files(input_path)

    work = []
    for file_path in files:
        with open(file_path, "rb") as fp:
            n_trees_in_file, tree_n_halos = _read_file_header(fp)
            header_bytes = 4 + 4 + n_trees_in_file * 4
        offset = header_bytes
        for local_idx in range(n_trees_in_file):
            work.append((file_path, local_idx, int(tree_n_halos[local_idx]), offset))
            offset += int(tree_n_halos[local_idx]) * HALO_DTYPE.itemsize

    if n_trees is not None:
        work = work[:n_trees]

    result: dict[int, dict] = {}
    current_file_path = None
    current_fp = None
    try:
        for global_tree_idx, (file_path, local_idx, n_halos, byte_offset) in enumerate(
            tqdm(work, desc="Reading trees")
        ):
            if file_path != current_file_path:
                if current_fp is not None:
                    current_fp.close()
                current_fp = open(file_path, "rb")
                current_file_path = file_path
            current_fp.seek(byte_offset)
            raw = current_fp.read(n_halos * HALO_DTYPE.itemsize)
            halos = np.frombuffer(raw, dtype=HALO_DTYPE)
            result[global_tree_idx] = _build_fields(halos)
    finally:
        if current_fp is not None:
            current_fp.close()

    return result


def convert(
    input_path: str,
    output_path: str,
    n_trees: int | None = None,
    particle_mass: float | None = None,
    output_format: str = "lhalo_hdf5",
) -> None:
    """Convert LHaloTree binary files to SAGE LHaloTree HDF5 or binary format.

    Parameters
    ----------
    input_path : str
        Path to a single binary tree file, or a directory containing
        files named trees_<snap>.<N> (e.g. trees_063.0 – trees_063.7).
    output_path : str
        Path for the output file.
    n_trees : int or None
        If given, convert only the first n_trees trees (Stage 2 test mode).
    particle_mass : float or None
        Accepted for API symmetry; ignored — this driver uses the hardcoded
        Millennium particle mass (PARTICLE_MASS = 0.0860 × 10^10 Msun/h).
    output_format : str
        'lhalo_hdf5' (default) writes HDF5 via utils.hdf5_writer.
        'lhalo_binary' writes SAGE binary (TreeType=0) via utils.binary_writer.
        For binary output the header is written first because all tree counts
        are known from the input file headers before any halo data is read.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    try:
        # ------------------------------------------------------------------
        # 1. Discover input files and read all headers
        # ------------------------------------------------------------------
        files = _discover_files(input_path)

        # Build a flat work list: one entry per tree across all files.
        # Each entry: (file_path, local_tree_idx, n_halos_in_tree, byte_offset_of_first_halo)
        work = []
        for file_path in files:
            with open(file_path, "rb") as fp:
                n_trees_in_file, tree_n_halos = _read_file_header(fp)
                header_bytes = 4 + 4 + n_trees_in_file * 4
            offset = header_bytes  # start of halo data
            for local_idx in range(n_trees_in_file):
                work.append((file_path, local_idx, int(tree_n_halos[local_idx]), offset))
                offset += int(tree_n_halos[local_idx]) * HALO_DTYPE.itemsize

        # Apply n_trees limit
        if n_trees is not None:
            work = work[:n_trees]

        total_trees = len(work)
        total_halos = sum(entry[2] for entry in work)
        tree_n_halos_out = np.array([entry[2] for entry in work], dtype=np.int32)

        # ------------------------------------------------------------------
        # 2. Write output
        # ------------------------------------------------------------------
        # Helper: iterate work list, keeping input files open across their trees.
        def _iter_trees(out_f, write_tree_fn):
            current_file_path = None
            current_fp = None
            global_tree_idx = 0
            try:
                for file_path, local_idx, n_halos, byte_offset in tqdm(
                    work, desc="Converting trees"
                ):
                    if file_path != current_file_path:
                        if current_fp is not None:
                            current_fp.close()
                        current_fp = open(file_path, "rb")
                        current_file_path = file_path

                    current_fp.seek(byte_offset)
                    raw = current_fp.read(n_halos * HALO_DTYPE.itemsize)
                    halos = np.frombuffer(raw, dtype=HALO_DTYPE)
                    write_tree_fn(out_f, global_tree_idx, _build_fields(halos))
                    global_tree_idx += 1
            finally:
                if current_fp is not None:
                    current_fp.close()

        if output_format == "lhalo_hdf5":
            with h5py.File(output_path, "w") as f:
                hdf5_writer.write_header(
                    f,
                    particle_mass=PARTICLE_MASS,
                    n_trees=total_trees,
                    total_halos=total_halos,
                    n_output_files=1,
                    tree_n_halos=tree_n_halos_out,
                )
                _iter_trees(f, hdf5_writer.write_tree)

        elif output_format == "lhalo_binary":
            with open(output_path, "wb") as f:
                binary_writer.write_header(
                    f,
                    particle_mass=PARTICLE_MASS,
                    n_trees=total_trees,
                    total_halos=total_halos,
                    n_output_files=1,
                    tree_n_halos=tree_n_halos_out,
                )
                _iter_trees(f, binary_writer.write_tree)

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
