"""
subfind_lhalotree_binary.py - Driver for the classic LHaloTree binary format.

Reads the Gadget-2/Subfind LHaloTree binary files (e.g. produced by the Millennium
Simulation pipeline, trees_063.0 - trees_063.7) and writes a single
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
import warnings
from io import BufferedReader
from pathlib import Path

import numpy as np
from tqdm import tqdm

from errors import ConversionError
from utils.schema import HALO_RECORD_DTYPE as HALO_DTYPE
from utils.sim_params import estimate_particle_mass
from utils.split_writer import SplitWriter

# HALO_DTYPE (the 104-byte SAGE LHaloTree record) is the canonical layout from
# utils.schema - the same input and output binary format. See _build_fields for
# the field -> SAGE-schema mapping.

# Halos to read when estimating particle mass from the data (bounded sample).
_PM_SAMPLE_HALOS = 50_000


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


def _read_file_header(fp: BufferedReader) -> tuple[int, np.ndarray]:
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


# Group-mass fields to estimate particle mass from, in order of preference. M_Crit200 is the
# group virial mass SAGE reads for centrals, so calibrating the particle mass to it keeps
# satellite masses (Len * PartMass) on the same scale as SAGE's central masses. The binary
# stores no subhalo mass, so the estimate is approximate. M_TopHat / M_Mean200 are fallbacks.
_PM_MASS_FIELDS = ("M_Crit200", "M_TopHat", "M_Mean200")


def _estimate_pm_from_sample(work: list) -> float:
    """Estimate particle mass (10^10 Msun/h) from a group mass / Len of FOF centrals.

    Reads up to _PM_SAMPLE_HALOS halos from the start of the work list. Within each tree a
    central has FirstHaloInFOFGroup == its own local index. Returns 0.0 if no usable halo.
    """
    cols: dict[str, list[np.ndarray]] = {f: [] for f in _PM_MASS_FIELDS}
    lens: list[np.ndarray] = []
    sampled = 0
    current_path = None
    fp: BufferedReader | None = None
    try:
        for file_path, _local_idx, n_halos, byte_offset in work:
            if file_path != current_path:
                if fp is not None:
                    fp.close()
                fp = open(file_path, "rb")
                current_path = file_path
            assert fp is not None
            fp.seek(byte_offset)
            halos = np.frombuffer(fp.read(n_halos * HALO_DTYPE.itemsize), dtype=HALO_DTYPE)
            central = (halos["FirstHaloInFOFGroup"] == np.arange(n_halos, dtype=np.int32)) & (
                halos["Len"] > 0
            )
            for f in _PM_MASS_FIELDS:
                cols[f].append(halos[f][central])
            lens.append(halos["Len"][central])
            sampled += n_halos
            if sampled >= _PM_SAMPLE_HALOS:
                break
    finally:
        if fp is not None:
            fp.close()
    if not lens:
        return 0.0
    length = np.concatenate(lens)
    for f in _PM_MASS_FIELDS:
        mass = np.concatenate(cols[f])
        positive = mass > 0
        if positive.any():
            return estimate_particle_mass(mass[positive], length[positive])
    return 0.0


def _build_fields(halos: np.ndarray) -> dict:
    """Build the canonical field dict from a structured halo array.

    Output units match HDF5 on-disk convention:
      SubhaloPos  in kpc/h  (halos["Pos"]  is Mpc/h, multiplied by 1000)
      SubhaloSpin in (kpc/h)(km/s) (halos["Spin"] is (Mpc/h)(km/s), multiplied by 1000)
    binary_writer divides both back by 1000 before packing.
    """
    return {
        "Descendant": halos["Descendant"],
        "FirstProgenitor": halos["FirstProgenitor"],
        "NextProgenitor": halos["NextProgenitor"],
        "FirstHaloInFOFGroup": halos["FirstHaloInFOFGroup"],
        "NextHaloInFOFGroup": halos["NextHaloInFOFGroup"],
        "SubhaloLen": halos["Len"],
        "Group_M_Crit200": halos["M_Crit200"],
        "Group_M_Mean200": halos["M_Mean200"],
        "Group_M_TopHat200": halos["M_TopHat"],
        "SubhaloPos": (halos["Pos"] * np.float32(1000.0)).astype(np.float32),
        "SubhaloVel": halos["Vel"],
        "SubhaloVelDisp": halos["VelDisp"],
        "SubhaloVMax": halos["Vmax"],
        "SubhaloSpin": (halos["Spin"] * np.float32(1000.0)).astype(np.float32),
        "SubhaloIDMostBound": halos["MostBoundID"],
        "SnapNum": halos["SnapNum"],
        "FileNr": halos["FileNr"],
    }


def convert(
    input_path: str,
    output_path: str,
    n_trees: int | None = None,
    sim_params: dict | None = None,
    output_format: str = "lhalo_hdf5",
    n_output_files: int = 1,
) -> None:
    """Convert LHaloTree binary files to SAGE LHaloTree HDF5 or binary format.

    Parameters
    ----------
    input_path : str
        Path to a single binary tree file, or a directory containing
        files named trees_<snap>.<N> (e.g. trees_063.0 - trees_063.7).
    output_path : str
        Path for the output file.
    n_trees : int or None
        If given, convert only the first n_trees trees.
    sim_params : dict or None
        Simulation parameter overrides from --sim-config JSON.
        Key used: particle_mass_msun_per_h (Msun/h, converted to 10^10 Msun/h
        internally). If absent, the particle mass is estimated from a group mass / Len
        of massive FOF centrals (with a warning); if it cannot be estimated, a
        ConversionError is raised.
    output_format : str
        'lhalo_hdf5' (default) writes HDF5 via utils.hdf5_writer.
        'lhalo_binary' writes SAGE binary (TreeType=0) via utils.binary_writer.
        For binary output the header is written first because all tree counts
        are known from the input file headers before any halo data is read.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    _pm_override = (sim_params or {}).get("particle_mass_msun_per_h")

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

        # Particle mass (10^10 Msun/h): override, else estimate from the data and warn.
        # The LHaloTree binary stores no cosmology, so the value cannot be recovered exactly.
        if _pm_override is not None:
            effective_pm = float(_pm_override) * 1e-10
        else:
            effective_pm = _estimate_pm_from_sample(work)
            if effective_pm <= 0:
                raise ConversionError(
                    "could not estimate particle mass from the input; pass "
                    "particle_mass_msun_per_h via --sim-config."
                )
            warnings.warn(
                f"particle_mass not provided; estimated {effective_pm:.4e} x 10^10 Msun/h "
                "from a group mass (M_Crit200, else M_TopHat/M_Mean200) / Len of massive "
                "centrals (approximate). Pass --sim-config with particle_mass_msun_per_h "
                "to set it exactly.",
                stacklevel=2,
            )

        # ------------------------------------------------------------------
        # 2. Write output
        # ------------------------------------------------------------------
        current_file_path = None
        current_fp: BufferedReader | None = None
        with SplitWriter(
            output_path=output_path,
            output_format=output_format,
            n_output_files=n_output_files,
            n_trees_total=total_trees,
            particle_mass=effective_pm,
        ) as writer:
            try:
                for file_path, local_idx, n_halos, byte_offset in tqdm(
                    work, desc="Converting trees"
                ):
                    if file_path != current_file_path:
                        if current_fp is not None:
                            current_fp.close()
                        current_fp = open(file_path, "rb")
                        current_file_path = file_path
                    assert current_fp is not None
                    current_fp.seek(byte_offset)
                    raw = current_fp.read(n_halos * HALO_DTYPE.itemsize)
                    halos = np.frombuffer(raw, dtype=HALO_DTYPE)
                    writer.write_tree(_build_fields(halos))
            finally:
                if current_fp is not None:
                    current_fp.close()

        print(
            f"  Done: {total_trees} trees. Output: {writer.output_paths}",
            file=sys.stderr,
        )

    except ConversionError:
        raise
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: conversion failed - {exc}", file=sys.stderr)
        raise ConversionError(f"conversion failed - {exc}") from exc
