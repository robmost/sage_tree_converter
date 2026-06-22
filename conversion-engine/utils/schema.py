"""
schema.py — Canonical SAGE LHaloTree field sets.

Single source of truth for the field names shared by the writers
(utils.hdf5_writer, utils.binary_writer) and the validator
(validation.syntactic). See reference/sage_lhalotree_hdf5_schema.md for the
full schema (dtypes, units, shapes).
"""

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
