"""
schema.py - Canonical SAGE LHaloTree field sets and binary record layout.

Single source of truth for the field names shared by the writers
(utils.hdf5_writer, utils.binary_writer) and the validator
(validation.syntactic). See reference/sage_lhalotree_hdf5_schema.md for the
full HDF5 schema and reference/sage_lhalotree_binary_schema.md for the binary one.
"""

import numpy as np

# ---------------------------------------------------------------------------
# Binary record layout - the 104-byte SAGE LHaloTree halo_data struct
# (struct halo_data in core_simulation.h). Single source of truth: the binary
# writer (utils.binary_writer) and every binary reader (the LHaloTree-binary
# driver and validation.semantic/functional/syntactic) import this dtype so the
# layout is declared exactly once. Field names are the writer-side convention.
# Byte order is explicit little-endian ("<") so readers and the writer agree on
# the on-disk layout independent of host endianness.
# ---------------------------------------------------------------------------
HALO_RECORD_DTYPE = np.dtype(
    [
        ("Descendant", "<i4"),
        ("FirstProgenitor", "<i4"),
        ("NextProgenitor", "<i4"),
        ("FirstHaloInFOFGroup", "<i4"),
        ("NextHaloInFOFGroup", "<i4"),
        ("Len", "<i4"),
        ("M_Mean200", "<f4"),
        ("M_Crit200", "<f4"),
        ("M_TopHat", "<f4"),
        ("Pos", "<f4", 3),
        ("Vel", "<f4", 3),
        ("VelDisp", "<f4"),
        ("Vmax", "<f4"),
        ("Spin", "<f4", 3),
        ("MostBoundID", "<i8"),
        ("SnapNum", "<i4"),
        ("FileNr", "<i4"),
        ("SubhaloIndex", "<i4"),
        ("SubHalfMass", "<f4"),
    ]
)
assert HALO_RECORD_DTYPE.itemsize == 104, (
    f"HALO_RECORD_DTYPE size {HALO_RECORD_DTYPE.itemsize} != 104; "
    "check against struct halo_data in core_simulation.h."
)


# Fields every driver must provide and every output file must contain.
MANDATORY_FIELDS = frozenset(
    {
        "Descendant",
        "FirstProgenitor",
        "NextProgenitor",
        "FirstHaloInFOFGroup",
        "NextHaloInFOFGroup",
        "SubhaloLen",
        "Group_M_Crit200",
        "SubhaloVMax",
        "SubhaloIDMostBound",
        "SnapNum",
        "SubhaloPos",
        "SubhaloVel",
        "SubhaloSpin",
    }
)

# Fields written when present; substituted with sentinels when absent.
OPTIONAL_FIELDS = frozenset(
    {
        "Group_M_Mean200",
        "Group_M_TopHat200",
        "SubhaloVelDisp",
        "FileNr",
    }
)

ALL_KNOWN_FIELDS = MANDATORY_FIELDS | OPTIONAL_FIELDS
