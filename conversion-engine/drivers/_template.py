"""
_template.py - Template driver for the SAGE merger tree converter.

HOW TO USE THIS TEMPLATE
========================
1. Copy this file to 'conversion-engine/drivers/<format_id>.py'
   (e.g. 'ahf_mergertree_ascii.py').
2. Replace every section marked with TODO with real implementation.
3. One public symbol must be exposed: 'convert' (the conversion entry point).
4. Ensure 'convert' works for both full conversion (n_trees=None) and
   test-mode (n_trees=N).
5. Write the driver to 'assets/drivers/<format_id>.py' first (Stage 2).
   The kdb-extend skill moves it to 'conversion-engine/drivers/' in Stage 4.

INTERFACE CONTRACT
==================
- Signature:  convert(input_path, output_path, n_trees=None, sim_params=None,
                      output_format="lhalo_hdf5", n_output_files=1) -> None
- On success: write valid SAGE LHaloTree output file(s) derived from output_path;
              return None.
- On error:   print a message to stderr and call sys.exit(1).
              SplitWriter.__exit__ deletes any partially-written output files
              automatically; do NOT call os.remove() in the except handler.
- n_trees:    when provided, convert only the first n_trees trees.
              The output file(s) must still be valid with correct internal indexing.
- n_output_files: number of output files to split across (default 1).
              SplitWriter derives file N paths from output_path by replacing the
              trailing index token (e.g. output/sim_STC.0.hdf5 -> .0, .1, ...).
              n_trees_total MUST be known before opening SplitWriter.  Obtain it:
                - from a header scan (O(trees) line-count or H5 attribute read)
                - from len(work_list) computed before any streaming starts
                - NEVER require O(all halos) pre-pass; the scan must be cheap.
- output_format: "lhalo_hdf5" writes HDF5 (SAGE TreeType=1).
                 "lhalo_binary" writes binary (SAGE TreeType=0, 104 bytes/halo).
                 Both formats are handled uniformly via SplitWriter - no
                 format-conditional write blocks needed in the driver.
- Performance: all tree-walking and pointer reconstruction must be O(N) or O(N log N).
               O(N^2) is not acceptable.
- Auxiliary index files (e.g. forests.list, locations.dat): if the driver loads
  a format-wide index before streaming trees, filter it to only the root IDs
  present in the current input file(s) to avoid O(all_simulation_trees) memory
  usage in array-job contexts.
"""

import os
import sys

import numpy as np  # noqa: F401
from tqdm import tqdm  # noqa: F401

from utils.split_writer import SplitWriter  # noqa: F401


def convert(
    input_path: str,
    output_path: str,
    n_trees: int | None = None,
    sim_params: dict | None = None,
    output_format: str = "lhalo_hdf5",
    n_output_files: int = 1,
) -> None:
    """Convert input merger trees to SAGE LHaloTree HDF5 or binary format.

    Parameters
    ----------
    input_path : str
        Path to the input file or directory (format-dependent).
    output_path : str
        Path for output file index 0 (e.g. output/sim_STC.0.hdf5).
        Additional files are derived by SplitWriter from the trailing index token.
    n_trees : int or None
        If given, convert only the first n_trees trees (Stage 2 test mode).
    sim_params : dict or None
        Simulation parameter overrides loaded from --sim-config JSON.
        Recognised keys: particle_mass_msun_per_h, n_particles_per_side,
        box_size_mpc_per_h, omega_m, omega_l, h0. All optional; drivers
        fall back to auto-detection when absent.
    output_format : str
        'lhalo_hdf5' (default) or 'lhalo_binary'. See interface contract above.
    n_output_files : int
        Number of output files to distribute trees across (default 1).
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
        # Reference units: masses -> 10^10 Msun/h, positions -> Mpc/h,
        #                  velocities -> km/s, spin -> (Mpc/h)(km/s).

        # ------------------------------------------------------------------
        # 3. Reconstruct LHaloTree pointers
        # ------------------------------------------------------------------
        # TODO: convert the input format's pointer representation into
        # LHaloTree-style integer indices within each tree's halo array.
        # Valid index range: [0, TreeNHalos[i]-1]. Sentinel: -1.
        # Progenitors must have SnapNum < descendant SnapNum.
        # Spatial pointers must share the same SnapNum.
        # Use O(N) algorithms (hash maps, sorting) - never O(N^2) search loops.

        # ------------------------------------------------------------------
        # 4. Write output via SplitWriter
        # ------------------------------------------------------------------
        # TODO: n_trees_total MUST be known here (see interface contract for
        # cheap ways to obtain it).  Replace the placeholders below:
        #
        #   with SplitWriter(
        #       output_path=output_path,
        #       output_format=output_format,
        #       n_output_files=n_output_files,
        #       n_trees_total=n_trees_to_convert,  # known upfront
        #       particle_mass=particle_mass_1e10,
        #   ) as writer:
        #       for fields in tqdm(tree_stream, desc="Converting trees", unit="tree"):
        #           writer.write_tree(fields)
        #
        #   output_paths = writer.output_paths  # list of all written file paths
        #
        # SplitWriter handles both HDF5 and binary transparently, distributes
        # trees across n_output_files files, and deletes partial files on error.

    except NotImplementedError:
        raise
    except Exception as exc:
        print(f"ERROR: conversion failed - {exc}", file=sys.stderr)
        sys.exit(1)
