"""
_template.py — Template driver for the SAGE merger tree converter.

HOW TO USE THIS TEMPLATE
========================
1. Copy this file to 'conversion-engine/drivers/<format_id>.py'
   (e.g. 'ahf_mergertree_ascii.py').
2. Replace every section marked with TODO with real implementation.
3. Two public symbols must be exposed: 'convert' (conversion entry point) and
   'read_trees' (used by semantic validation to load input data independently).
4. Ensure 'convert' works for both full conversion (n_trees=None) and
   test-mode (n_trees=N).
5. Write the driver to 'assets/drivers/<format_id>.py' first (Stage 2).
   The kdb-extend skill moves it to 'conversion-engine/drivers/' in Stage 4.

INTERFACE CONTRACT
==================
- Signature:  convert(input_path, output_path, n_trees=None, particle_mass=None,
                      output_format="lhalo_hdf5") -> None
- On success: write a valid SAGE LHaloTree output file to output_path; return None.
- On error:   print a message to stderr and call sys.exit(1).
              Delete any partially-written output file before exiting.
- n_trees:    when provided, convert only the first n_trees trees.
              The output file must still be valid with correct internal indexing.
- output_format: "lhalo_hdf5" writes HDF5 (SAGE TreeType=1) via utils.hdf5_writer.
                 "lhalo_binary" writes binary (SAGE TreeType=0) via utils.binary_writer.
                 For binary output, write_header() MUST be called before write_tree().
                 If tree counts are not known upfront, accumulate all field dicts in
                 memory first, then write header + trees sequentially.
- Performance: all tree-walking and pointer reconstruction must be O(N) or O(N log N).
               O(N²) is not acceptable.
"""

import os
import sys

import h5py
import numpy as np
from tqdm import tqdm

from utils import binary_writer, hdf5_writer


def convert(
    input_path: str,
    output_path: str,
    n_trees: int | None = None,
    particle_mass: float | None = None,
    output_format: str = "lhalo_hdf5",
) -> None:
    """Convert input merger trees to SAGE LHaloTree HDF5 or binary format.

    Parameters
    ----------
    input_path : str
        Path to the input file or directory (format-dependent).
    output_path : str
        Path for the output file. The parent directory is created if needed.
    n_trees : int or None
        If given, convert only the first n_trees trees (Stage 2 test mode).
    particle_mass : float or None
        Dark matter particle mass in Msun/h. Override from CLI; may be None.
    output_format : str
        'lhalo_hdf5' (default) or 'lhalo_binary'. See interface contract above.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    try:
        # ------------------------------------------------------------------
        # 1. Read input
        # ------------------------------------------------------------------
        # TODO: open input_path and parse the raw merger tree data.
        # Record: n_trees_total, per-tree halo arrays for all fields.
        # Apply n_trees limit here if provided:
        #   n_trees_to_convert = min(n_trees, n_trees_total) if n_trees else n_trees_total
        raise NotImplementedError("Replace this with the actual conversion logic.")

        # ------------------------------------------------------------------
        # 2. Apply field mapping and unit conversions
        # ------------------------------------------------------------------
        # TODO: for each halo field, apply the scale_factor or conversion_expr
        # defined in 'assets/proposed_mapping_<format_id>.json'.
        # Reference units: masses → 10¹⁰ M☉/h, positions → Mpc/h,
        #                  velocities → km/s, spin → (Mpc/h)(km/s).

        # ------------------------------------------------------------------
        # 3. Reconstruct LHaloTree pointers
        # ------------------------------------------------------------------
        # TODO: convert the input format's pointer representation into
        # LHaloTree-style integer indices within each tree's halo array.
        # Valid index range: [0, TreeNHalos[i]-1]. Sentinel: -1.
        # Progenitors must have SnapNum < descendant SnapNum.
        # Spatial pointers must share the same SnapNum.
        # Use O(N) algorithms (hash maps, sorting) — never O(N²) search loops.

        # ------------------------------------------------------------------
        # 4. Write output via utils.hdf5_writer or utils.binary_writer
        # ------------------------------------------------------------------
        # TODO: build tree_n_halos, particle_mass_1e10, all_fields, then choose:
        #
        # lhalo_hdf5 (header may be written last if counts aren't known upfront):
        #
        #   with h5py.File(output_path, "w") as f:
        #       hdf5_writer.write_header(
        #           f, particle_mass=particle_mass_1e10,
        #           n_trees=n_trees_to_convert, total_halos=total_halos,
        #           n_output_files=1, tree_n_halos=tree_n_halos,
        #       )
        #       for i in tqdm(range(n_trees_to_convert), desc="Writing trees"):
        #           hdf5_writer.write_tree(f, i, all_fields[i])
        #
        # lhalo_binary (header MUST be written first; accumulate field dicts
        # in memory if counts aren't known before streaming starts):
        #
        #   with open(output_path, "wb") as f:
        #       binary_writer.write_header(
        #           f, particle_mass=particle_mass_1e10,
        #           n_trees=n_trees_to_convert, total_halos=total_halos,
        #           n_output_files=1, tree_n_halos=tree_n_halos,
        #       )
        #       for i in tqdm(range(n_trees_to_convert), desc="Writing trees"):
        #           binary_writer.write_tree(f, i, all_fields[i])

    except NotImplementedError:
        raise
    except Exception as exc:
        print(f"ERROR: conversion failed — {exc}", file=sys.stderr)
        if os.path.exists(output_path):
            os.remove(output_path)
        sys.exit(1)


def read_trees(
    input_path: str,
    n_trees: int | None = None,
) -> dict[int, dict]:
    """Read input trees into the SAGE LHaloTree schema without writing output.

    Applies all unit conversions and pointer reconstruction that convert() would,
    but accumulates results in memory instead of writing to disk. Called by
    semantic validation to load the original input data as the reference column.

    Parameters
    ----------
    input_path : str
        Path to the input file or directory (format-dependent).
    n_trees : int or None
        If given, read only the first n_trees trees.

    Returns
    -------
    dict[int, dict[str, np.ndarray]]
        Maps integer tree index (0-based, matching convert() output order) to
        a field dict using SAGE LHaloTree HDF5 field names and on-disk units.
        SubhaloPos in kpc/h, SubhaloSpin in (kpc/h)(km/s), masses in 1e10 Msun/h.
    """
    raise NotImplementedError("Replace this with the actual read_trees logic.")
