"""
binary_writer.py - Utility functions for writing SAGE LHaloTree binary output files.

Public API mirrors hdf5_writer.py so drivers can call either writer with identical
arguments. The binary format is SAGE TreeType=0, read by read_tree_lhalo_binary.c.

File layout:
    Offset 0:            int32  nforests
    Offset 4:            int32  totnhalos
    Offset 8:            int32  nhalos_per_forest[nforests]
    Offset 8+nforests*4: struct halo_data records (104 bytes each, sequential)

Unit difference from HDF5:
    The HDF5 reader (read_tree_lhalo_hdf5.c) multiplies Pos and Spin by 0.001 after
    reading (kpc/h -> Mpc/h). The binary reader does NOT. Drivers produce field dicts
    in HDF5 on-disk units (SubhaloPos in kpc/h, SubhaloSpin in (kpc/h)(km/s)); this
    module divides both by 1000 before packing.

Optional fields (Group_M_Mean200, Group_M_TopHat200, SubhaloVelDisp, FileNr) are
written as 0.0 / -1 when absent from the fields dict. SubhaloIndex and SubHalfMass
have no HDF5 equivalents and are always written as -1 and 0.0 respectively.
"""

import struct
import sys
from typing import BinaryIO

import numpy as np

from errors import ConversionError
from utils.schema import HALO_RECORD_DTYPE, MANDATORY_FIELDS

# ---------------------------------------------------------------------------
# Binary struct layout matching struct halo_data in core_simulation.h
# ---------------------------------------------------------------------------

_HALO_STRUCT_FMT = "<6i3f3f3f2f3fq3if"
_HALO_STRUCT_SIZE = struct.calcsize(_HALO_STRUCT_FMT)
assert _HALO_STRUCT_SIZE == 104, (
    f"Binary struct size mismatch: got {_HALO_STRUCT_SIZE}, expected 104. "
    "Check _HALO_STRUCT_FMT against core_simulation.h."
)

# HALO_RECORD_DTYPE (utils.schema) is the canonical packed little-endian layout;
# its byte layout is identical to struct.pack(_HALO_STRUCT_FMT), so _pack_tree can
# fill columns and emit one .tobytes() instead of a per-halo Python loop.
assert HALO_RECORD_DTYPE.itemsize == _HALO_STRUCT_SIZE, (
    f"HALO_RECORD_DTYPE size {HALO_RECORD_DTYPE.itemsize} != struct size {_HALO_STRUCT_SIZE}."
)


def _require_little_endian() -> None:
    """Reject binary output on big-endian hosts.

    Checked when binary output is written (not at import time) so that HDF5
    conversions - which never call the binary writer - run on any host.
    """
    if sys.byteorder != "little":
        raise ConversionError(
            f"lhalo_binary output requires a little-endian host "
            f"(detected {sys.byteorder!r} byte order). "
            f"Use --output-format lhalo_hdf5 instead; HDF5 handles "
            f"endianness transparently."
        )


def _pack_tree(fields: dict) -> bytes:
    """Pack all halos in a tree into a bytes object (n_halos * 104 bytes).

    Fills a packed structured array and emits a single .tobytes(); byte-identical
    to packing each halo with struct.pack(_HALO_STRUCT_FMT, ...).
    """
    n = len(fields["Descendant"])

    # SubhaloPos is in kpc/h, SubhaloSpin in (kpc/h)(km/s) (HDF5 on-disk convention).
    # The binary reader expects Mpc/h - divide both by 1000.
    pos_raw = np.asarray(fields["SubhaloPos"], dtype=np.float32)
    if pos_raw.ndim != 2 or pos_raw.shape[1] != 3:
        raise ValueError(f"SubhaloPos must have shape (N, 3), got {pos_raw.shape}.")
    vel = np.asarray(fields["SubhaloVel"], dtype=np.float32)
    if vel.ndim != 2 or vel.shape[1] != 3:
        raise ValueError(f"SubhaloVel must have shape (N, 3), got {vel.shape}.")
    spin_raw = np.asarray(fields["SubhaloSpin"], dtype=np.float32)
    if spin_raw.ndim != 2 or spin_raw.shape[1] != 3:
        raise ValueError(f"SubhaloSpin must have shape (N, 3), got {spin_raw.shape}.")

    rec = np.empty(n, dtype=HALO_RECORD_DTYPE)
    rec["Descendant"] = np.asarray(fields["Descendant"], dtype=np.int32)
    rec["FirstProgenitor"] = np.asarray(fields["FirstProgenitor"], dtype=np.int32)
    rec["NextProgenitor"] = np.asarray(fields["NextProgenitor"], dtype=np.int32)
    rec["FirstHaloInFOFGroup"] = np.asarray(fields["FirstHaloInFOFGroup"], dtype=np.int32)
    rec["NextHaloInFOFGroup"] = np.asarray(fields["NextHaloInFOFGroup"], dtype=np.int32)
    rec["Len"] = np.asarray(fields["SubhaloLen"], dtype=np.int32)
    rec["M_Mean200"] = np.asarray(
        fields.get("Group_M_Mean200", np.zeros(n, np.float32)), dtype=np.float32
    )
    rec["M_Crit200"] = np.asarray(fields["Group_M_Crit200"], dtype=np.float32)
    rec["M_TopHat"] = np.asarray(
        fields.get("Group_M_TopHat200", np.zeros(n, np.float32)), dtype=np.float32
    )
    rec["Pos"] = pos_raw * np.float32(1e-3)
    rec["Vel"] = vel
    rec["VelDisp"] = np.asarray(
        fields.get("SubhaloVelDisp", np.zeros(n, np.float32)), dtype=np.float32
    )
    rec["Vmax"] = np.asarray(fields["SubhaloVMax"], dtype=np.float32)
    rec["Spin"] = spin_raw * np.float32(1e-3)
    rec["MostBoundID"] = np.asarray(fields["SubhaloIDMostBound"], dtype=np.int64)
    rec["SnapNum"] = np.asarray(fields["SnapNum"], dtype=np.int32)
    rec["FileNr"] = np.asarray(fields.get("FileNr", np.full(n, -1, np.int32)), dtype=np.int32)
    rec["SubhaloIndex"] = -1
    rec["SubHalfMass"] = 0.0

    return rec.tobytes()


def write_header(
    f: BinaryIO,
    particle_mass: float,
    n_trees: int,
    total_halos: int,
    n_output_files: int,
    tree_n_halos: np.ndarray | list[int],
) -> None:
    """Write the binary file header (nforests, totnhalos, nhalos_per_forest[]).

    Parameters
    ----------
    f :
        Open binary file object (mode "wb"). Must be at position 0.
    particle_mass : float
        Accepted for API symmetry with hdf5_writer; not stored in binary format.
    n_trees : int
        Number of merger trees (forests) in this file.
    total_halos : int
        Total number of halos across all trees.
    n_output_files : int
        Accepted for API symmetry with hdf5_writer; not stored in binary format.
    tree_n_halos : array-like
        1D sequence of length n_trees; element i is the number of halos in tree i.
        sum(tree_n_halos) must equal total_halos.
    """
    _require_little_endian()
    tree_n_halos_arr = np.asarray(tree_n_halos, dtype=np.int32)
    if len(tree_n_halos_arr) != n_trees:
        raise ValueError(f"len(tree_n_halos)={len(tree_n_halos_arr)} != n_trees={n_trees}.")
    if int(tree_n_halos_arr.sum()) != total_halos:
        raise ValueError(
            f"sum(tree_n_halos)={tree_n_halos_arr.sum()} != total_halos={total_halos}."
        )

    f.write(struct.pack("<i", n_trees))
    f.write(struct.pack("<i", total_halos))
    f.write(tree_n_halos_arr.tobytes())


def write_placeholder_header(f: BinaryIO, n_trees: int) -> None:
    """Write a zeroed placeholder header to reserve space for the real header.

    Call this at position 0 when starting a streaming binary write.  After all
    trees for this file are written, call patch_header() to overwrite the
    placeholder with the real values.

    Parameters
    ----------
    f :
        Open binary file object (mode "wb"). Must be at position 0.
    n_trees : int
        Number of trees that will be written to this file.  The placeholder
        occupies 8 + n_trees x 4 bytes (matching the real header layout).
    """
    _require_little_endian()
    size = 8 + n_trees * 4  # nforests (4B) + totnhalos (4B) + nhalos[n_trees] (4B each)
    f.write(b"\x00" * size)


def patch_header(
    f: BinaryIO,
    particle_mass: float,
    n_trees: int,
    total_halos: int,
    n_output_files: int,
    tree_n_halos: "np.ndarray | list[int]",
) -> None:
    """Seek to offset 0, write the real header, then seek back to the original position.

    Must be called after all trees have been written with write_tree().  The
    file must have been opened with write_placeholder_header() so the header
    region is already reserved.

    Parameters are identical to write_header().
    """
    pos = f.tell()
    f.seek(0)
    write_header(f, particle_mass, n_trees, total_halos, n_output_files, tree_n_halos)
    f.seek(pos)


def write_tree(
    f: BinaryIO,
    tree_idx: int,
    fields: dict,
) -> None:
    """Write a single tree's halo records sequentially to the binary file.

    Parameters
    ----------
    f :
        Open binary file object (mode "wb"). write_header() must have been called
        first; halo data is appended at the current file position.
    tree_idx : int
        Accepted for API symmetry with hdf5_writer; ignored (binary format is
        sequential - trees are identified by position, not by name).
    fields : dict[str, array-like]
        Mapping from SAGE field name to its data array. All mandatory fields must
        be present. Optional fields are used if included.

    Raises
    ------
    ValueError
        If any mandatory field is missing, or if vector fields have wrong shape.
    """
    missing = MANDATORY_FIELDS - set(fields)
    if missing:
        raise ValueError(f"write_tree: missing mandatory fields: {sorted(missing)}.")
    f.write(_pack_tree(fields))
