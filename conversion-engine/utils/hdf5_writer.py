"""
hdf5_writer.py — Utility functions for writing SAGE LHaloTree HDF5 output files.

All conversion drivers must write output through these functions to guarantee
dtype correctness and schema compliance with reference/sage_lhalotree_hdf5_schema.md.
"""

from typing import Any

import h5py
import numpy as np

from utils.schema import MANDATORY_FIELDS

# ---------------------------------------------------------------------------
# Canonical dtype map (schema §3.1–3.3)
# ---------------------------------------------------------------------------

# Fields stored as int32
_INT32_FIELDS = frozenset(
    {
        "Descendant",
        "FirstProgenitor",
        "NextProgenitor",
        "FirstHaloInFOFGroup",
        "NextHaloInFOFGroup",
        "SubhaloLen",
        "SnapNum",
        "FileNr",
    }
)

# Fields stored as int64
_INT64_FIELDS = frozenset(
    {
        "SubhaloIDMostBound",
    }
)

# Fields stored as float32 (scalar per halo)
_FLOAT32_SCALAR_FIELDS = frozenset(
    {
        "Group_M_Crit200",
        "SubhaloVMax",
        "Group_M_Mean200",
        "Group_M_TopHat200",
        "SubhaloVelDisp",
    }
)

# Fields stored as float32 with shape (N, 3)
_FLOAT32_VECTOR_FIELDS = frozenset(
    {
        "SubhaloPos",
        "SubhaloVel",
        "SubhaloSpin",
    }
)

def _cast(field_name: str, data: Any) -> np.ndarray:
    """Cast data to the canonical dtype for the given field name."""
    arr = np.asarray(data)
    if field_name in _INT32_FIELDS:
        return arr.astype(np.int32)
    if field_name in _INT64_FIELDS:
        return arr.astype(np.int64)
    if field_name in _FLOAT32_SCALAR_FIELDS:
        return arr.astype(np.float32)
    if field_name in _FLOAT32_VECTOR_FIELDS:
        out = arr.astype(np.float32)
        if out.ndim != 2 or out.shape[1] != 3:
            raise ValueError(
                f"Vector field '{field_name}' must have shape (N, 3), got {arr.shape}."
            )
        return out
    # Unknown field — preserve as-is but warn.
    import warnings

    warnings.warn(
        f"Field '{field_name}' is not in the canonical dtype map. "
        "Writing as-is. Check reference/sage_lhalotree_hdf5_schema.md.",
        stacklevel=3,
    )
    return arr


def write_header(
    f: h5py.File,
    particle_mass: float,
    n_trees: int,
    total_halos: int,
    n_output_files: int,
    tree_n_halos: np.ndarray | list[int],
) -> None:
    """Create the Header/ group with the four mandatory attributes and TreeNHalos dataset.

    Parameters
    ----------
    f : h5py.File
        An open, writable HDF5 file object.
    particle_mass : float
        Dark matter particle mass in units of 10¹⁰ M☉/h (stored as float64).
    n_trees : int
        Number of merger trees in this file.
    total_halos : int
        Total number of halos across all trees.
    n_output_files : int
        Total number of output tree files in the simulation set.
    tree_n_halos : array-like
        1D sequence of length n_trees; element i is the number of halos in Tree<i>.
        sum(tree_n_halos) must equal total_halos.
    """
    tree_n_halos_arr = np.asarray(tree_n_halos, dtype=np.int32)
    if len(tree_n_halos_arr) != n_trees:
        raise ValueError(f"len(tree_n_halos)={len(tree_n_halos_arr)} != n_trees={n_trees}.")
    if int(tree_n_halos_arr.sum()) != total_halos:
        raise ValueError(
            f"sum(tree_n_halos)={tree_n_halos_arr.sum()} != total_halos={total_halos}."
        )

    hdr = f.create_group("Header")
    hdr.attrs["ParticleMass"] = np.float64(particle_mass)
    hdr.attrs["NtreesPerFile"] = np.int32(n_trees)
    hdr.attrs["NhalosPerFile"] = np.int32(total_halos)
    hdr.attrs["NumberOfOutputFiles"] = np.int32(n_output_files)
    hdr.create_dataset("TreeNHalos", data=tree_n_halos_arr)


def write_tree(
    f: h5py.File,
    tree_idx: int,
    fields: dict,
) -> None:
    """Write a single Tree<X> group from a dict of field arrays.

    Parameters
    ----------
    f : h5py.File
        An open, writable HDF5 file object.
    tree_idx : int
        Zero-based tree index; the group will be named 'Tree{tree_idx}'.
    fields : dict[str, array-like]
        Mapping from SAGE field name to its data array. All mandatory fields
        must be present. Optional fields are written if included.

    Raises
    ------
    ValueError
        If any mandatory field is missing from fields.
    """
    missing = MANDATORY_FIELDS - set(fields)
    if missing:
        raise ValueError(
            f"Tree{tree_idx}: missing mandatory fields: {sorted(missing)}. "
            "All fields in MANDATORY_FIELDS must be provided."
        )

    grp = f.create_group(f"Tree{tree_idx}")
    for field_name, data in fields.items():
        grp.create_dataset(field_name, data=_cast(field_name, data))
