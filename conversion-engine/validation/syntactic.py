"""
syntactic.py — Programmatic syntactic validation for SAGE LHaloTree output files.

Supports both lhalo_hdf5 (run_checks) and lhalo_binary (run_binary_checks).

Implements the same six checks as .ai/skills/syntactic-validation/scripts/run_syntactic_checks.py
but as a callable Python API (no stdout, structured return value).

This module is used by the main driver and tests for programmatic access.
For human-readable output, run the script at
.ai/skills/syntactic-validation/scripts/run_syntactic_checks.py directly.

Usage:
    from validation.syntactic import run_checks
    result = run_checks("output/converted.hdf5", n_snapshots=64)
    if not result["overall"]:
        for name, check in result["checks"].items():
            if not check["passed"]:
                print(f"FAIL — {name}: {check['detail']}")
"""

import os
import struct
from typing import Any

import h5py
import numpy as np

CheckDict = dict[str, Any]


def _load_arr(group: h5py.Group, key: str) -> np.ndarray:
    """Load an h5py dataset field into a numpy array (type-narrowing helper)."""
    ds: h5py.Dataset = group[key]  # type: ignore[assignment]
    return np.asarray(ds)  # type: ignore[arg-type]


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

OPTIONAL_FIELDS = frozenset(
    {
        "Group_M_Mean200",
        "Group_M_TopHat200",
        "SubhaloVelDisp",
        "FileNr",
    }
)

ALL_KNOWN_FIELDS = MANDATORY_FIELDS | OPTIONAL_FIELDS


def _PASS(detail: str = "") -> dict:
    return {"passed": True, "detail": detail}


def _FAIL(detail: str) -> dict:
    return {"passed": False, "detail": detail}


def _check_file_integrity(path: str) -> dict:
    try:
        with h5py.File(path, "r") as f:
            keys = list(f.keys())
        if "Header" not in keys:
            return _FAIL("Header group missing")
        tree_keys = [k for k in keys if k.startswith("Tree")]
        if not tree_keys:
            return _FAIL("No Tree<X> groups found")
        return _PASS()
    except Exception as exc:
        return _FAIL(str(exc))


def _check_schema_compliance(f: h5py.File) -> dict:
    hdr: h5py.Group = f["Header"]  # type: ignore[assignment]
    details = []

    n_trees_attr = int(hdr.attrs.get("NtreesPerFile", -1))
    n_halos_attr = int(hdr.attrs.get("NhalosPerFile", -1))

    if "TreeNHalos" not in hdr:
        return _FAIL("Header/TreeNHalos dataset missing")

    tree_n_halos = _load_arr(hdr, "TreeNHalos")

    if len(tree_n_halos) != n_trees_attr:
        details.append(f"len(TreeNHalos)={len(tree_n_halos)} != NtreesPerFile={n_trees_attr}")

    if int(tree_n_halos.sum()) != n_halos_attr:
        details.append(f"sum(TreeNHalos)={tree_n_halos.sum()} != NhalosPerFile={n_halos_attr}")

    tree_names = sorted([k for k in f.keys() if k.startswith("Tree")])
    if len(tree_names) != n_trees_attr:
        details.append(
            f"Number of Tree groups ({len(tree_names)}) != NtreesPerFile ({n_trees_attr})"
        )

    for tree_name in tree_names:
        grp: h5py.Group = f[tree_name]  # type: ignore[assignment]
        present = set(grp.keys())
        missing = MANDATORY_FIELDS - present
        extra = present - ALL_KNOWN_FIELDS
        if missing:
            details.append(f"{tree_name}: missing fields {sorted(missing)}")
        if extra:
            details.append(f"{tree_name}: undocumented extra fields {sorted(extra)}")

    if details:
        return _FAIL("; ".join(details))
    return _PASS()


def _check_temporal_pointers(f: h5py.File) -> dict:
    details = []
    tree_names = sorted([k for k in f.keys() if k.startswith("Tree")])

    for tree_name in tree_names:
        grp: h5py.Group = f[tree_name]  # type: ignore[assignment]
        N = len(_load_arr(grp, "SnapNum"))
        snap = _load_arr(grp, "SnapNum").astype(np.int32)
        desc = _load_arr(grp, "Descendant").astype(np.int32)
        fp = _load_arr(grp, "FirstProgenitor").astype(np.int32)
        np_ = _load_arr(grp, "NextProgenitor").astype(np.int32)

        for field_name, arr in [
            ("Descendant", desc),
            ("FirstProgenitor", fp),
            ("NextProgenitor", np_),
        ]:
            bad = np.where((arr < -1) | (arr >= N))[0]
            if len(bad):
                details.append(
                    f"{tree_name}/{field_name}: {len(bad)} out-of-range values "
                    f"(first at index {bad[0]}, value={arr[bad[0]]})"
                )

        mask = desc != -1
        idx = np.where(mask)[0]
        if len(idx) and np.any(snap[desc[mask]] <= snap[idx]):
            details.append(f"{tree_name}/Descendant: snapshot ordering violated")

        # FirstProgenitor must be at a strictly earlier snapshot than the halo itself.
        mask_fp = fp != -1
        idx_fp = np.where(mask_fp)[0]
        if len(idx_fp) and np.any(snap[fp[mask_fp]] >= snap[idx_fp]):
            details.append(f"{tree_name}/FirstProgenitor: snapshot ordering violated")

        # NextProgenitor is a sibling progenitor of the SAME descendant.
        # The constraint is snap[NextProgenitor[i]] < snap[Descendant[i]],
        # not snap[i], because sibling progenitors can be at the same snapshot.
        mask_np = np_ != -1
        idx_np = np.where(mask_np)[0]
        if len(idx_np):
            desc_of_np = desc[idx_np]
            no_desc = desc_of_np == -1
            if np.any(no_desc):
                details.append(
                    f"{tree_name}/NextProgenitor: "
                    f"{int(no_desc.sum())} halos have NextProgenitor but no Descendant"
                )
            has_desc = ~no_desc
            if np.any(has_desc):
                snap_np_target = snap[np_[idx_np[has_desc]]]
                snap_desc = snap[desc_of_np[has_desc]]
                if np.any(snap_np_target >= snap_desc):
                    details.append(
                        f"{tree_name}/NextProgenitor: snapshot ordering violated "
                        f"(snap[NextProgenitor[i]] >= snap[Descendant[i]])"
                    )

    if details:
        return _FAIL("; ".join(details))
    return _PASS()


def _check_spatial_pointers(f: h5py.File) -> dict:
    details = []
    tree_names = sorted([k for k in f.keys() if k.startswith("Tree")])

    for tree_name in tree_names:
        grp: h5py.Group = f[tree_name]  # type: ignore[assignment]
        N = len(_load_arr(grp, "SnapNum"))
        snap = _load_arr(grp, "SnapNum").astype(np.int32)
        fof = _load_arr(grp, "FirstHaloInFOFGroup").astype(np.int32)
        nfof = _load_arr(grp, "NextHaloInFOFGroup").astype(np.int32)

        for field_name, arr in [
            ("FirstHaloInFOFGroup", fof),
            ("NextHaloInFOFGroup", nfof),
        ]:
            bad = np.where((arr < -1) | (arr >= N))[0]
            if len(bad):
                details.append(f"{tree_name}/{field_name}: {len(bad)} out-of-range values")

            mask = arr != -1
            idx = np.where(mask)[0]
            if len(idx) and np.any(snap[arr[mask]] != snap[idx]):
                details.append(f"{tree_name}/{field_name}: cross-snapshot spatial pointer found")

    if details:
        return _FAIL("; ".join(details))
    return _PASS()


def _check_snapshot_consistency(f: h5py.File, n_snapshots: int | None) -> dict:
    details = []
    tree_names = sorted([k for k in f.keys() if k.startswith("Tree")])

    for tree_name in tree_names:
        grp: h5py.Group = f[tree_name]  # type: ignore[assignment]
        snap = _load_arr(grp, "SnapNum").astype(np.int32)
        if np.any(snap < 0):
            details.append(f"{tree_name}: negative SnapNum values found")
        if n_snapshots is not None and np.any(snap >= n_snapshots):
            details.append(f"{tree_name}: SnapNum >= n_snapshots ({n_snapshots}) found")

    note = (
        "" if n_snapshots is not None else " (upper bound not verified — n_snapshots not provided)"
    )
    if details:
        return _FAIL("; ".join(details) + note)
    return _PASS(note.strip())


def _check_property_consistency(f: h5py.File) -> dict:
    details = []
    tree_names = sorted([k for k in f.keys() if k.startswith("Tree")])

    for tree_name in tree_names:
        grp: h5py.Group = f[tree_name]  # type: ignore[assignment]

        mass = _load_arr(grp, "Group_M_Crit200")
        if not np.all(np.isfinite(mass)):
            details.append(f"{tree_name}/Group_M_Crit200: NaN or Inf present")
        if np.any(mass < 0) or np.any(mass > 1e6):
            n_bad = int(np.sum((mass < 0) | (mass > 1e6)))
            details.append(
                f"{tree_name}/Group_M_Crit200: {n_bad} values outside [0, 1e6] (10¹⁰ M☉/h)"
            )

        vel = _load_arr(grp, "SubhaloVel")
        vel_mag = np.linalg.norm(vel, axis=1)
        if np.any(vel_mag > 10_000):
            n_bad = int(np.sum(vel_mag > 10_000))
            details.append(f"{tree_name}/SubhaloVel: {n_bad} magnitudes > 10000 km/s")

        vmax = _load_arr(grp, "SubhaloVMax")
        if np.any(vmax < 0) or np.any(vmax > 10_000):
            details.append(f"{tree_name}/SubhaloVMax: values outside [0, 10000] km/s")

        pos = _load_arr(grp, "SubhaloPos")
        if not np.all(np.isfinite(pos)):
            details.append(f"{tree_name}/SubhaloPos: NaN or Inf present")

    if details:
        return _FAIL("; ".join(details))
    return _PASS()


def run_checks(hdf5_path: str, n_snapshots: int | None = None) -> CheckDict:
    """Run all six syntactic checks on a SAGE LHaloTree HDF5 file.

    Parameters
    ----------
    hdf5_path : str
        Path to the HDF5 file to validate.
    n_snapshots : int or None
        Total number of snapshots in the simulation. If provided, Check 5
        verifies that all SnapNum values are in [0, n_snapshots - 1].

    Returns
    -------
    dict with keys:
        "overall" : bool — True if all checks passed.
        "checks"  : dict mapping check name → {"passed": bool, "detail": str}
    """
    checks: CheckDict = {
        "file_integrity": _FAIL("not run"),
        "schema_compliance": _FAIL("not run"),
        "temporal_pointer_integrity": _FAIL("not run"),
        "spatial_pointer_integrity": _FAIL("not run"),
        "snapshot_consistency": _FAIL("not run"),
        "property_consistency": _FAIL("not run"),
    }
    result: CheckDict = {"overall": False, "checks": checks}

    # Check 1 — file integrity (also determines if we can continue)
    result["checks"]["file_integrity"] = _check_file_integrity(hdf5_path)
    if not result["checks"]["file_integrity"]["passed"]:
        return result

    # Checks 2–6 — open once, run sequentially
    with h5py.File(hdf5_path, "r") as f:
        result["checks"]["schema_compliance"] = _check_schema_compliance(f)
        result["checks"]["temporal_pointer_integrity"] = _check_temporal_pointers(f)
        result["checks"]["spatial_pointer_integrity"] = _check_spatial_pointers(f)
        result["checks"]["snapshot_consistency"] = _check_snapshot_consistency(f, n_snapshots)
        result["checks"]["property_consistency"] = _check_property_consistency(f)

    result["overall"] = all(c["passed"] for c in result["checks"].values())
    return result


# ---------------------------------------------------------------------------
# Binary format (lhalo_binary / SAGE TreeType=0) validation
# ---------------------------------------------------------------------------

_BINARY_HALO_DTYPE = np.dtype(
    [
        ("Descendant", np.int32),
        ("FirstProgenitor", np.int32),
        ("NextProgenitor", np.int32),
        ("FirstHaloInFOFgroup", np.int32),
        ("NextHaloInFOFgroup", np.int32),
        ("Len", np.int32),
        ("M_Mean200", np.float32),
        ("Mvir", np.float32),
        ("M_TopHat", np.float32),
        ("Pos", np.float32, 3),
        ("Vel", np.float32, 3),
        ("VelDisp", np.float32),
        ("Vmax", np.float32),
        ("Spin", np.float32, 3),
        ("MostBoundID", np.int64),
        ("SnapNum", np.int32),
        ("FileNr", np.int32),
        ("SubhaloIndex", np.int32),
        ("SubHalfMass", np.float32),
    ]
)  # 104 bytes per record — matches struct halo_data in core_simulation.h


def run_binary_checks(binary_path: str, n_snapshots: int | None = None) -> CheckDict:
    """Run structural checks on a SAGE LHaloTree binary file (TreeType=0).

    Parameters
    ----------
    binary_path : str
        Path to the binary file written by utils.binary_writer.
    n_snapshots : int or None
        Total number of snapshots. If provided, SnapNum values in the first
        tree are verified to be in [0, n_snapshots - 1].

    Returns
    -------
    dict with keys:
        "overall" : bool — True if all checks passed.
        "checks"  : dict mapping check name → {"passed": bool, "detail": str}
    """
    checks: CheckDict = {
        "file_readable": _FAIL("not run"),
        "header_consistency": _FAIL("not run"),
        "file_size_consistency": _FAIL("not run"),
        "first_tree_pointers": _FAIL("not run"),
        "first_tree_snapnums": _FAIL("not run"),
    }
    result: CheckDict = {"overall": False, "checks": checks}

    # Check 1 — file readable and has at least an 8-byte header
    try:
        with open(binary_path, "rb") as f:
            header_bytes = f.read(8)
        if len(header_bytes) < 8:
            result["checks"]["file_readable"] = _FAIL(
                f"File too short: {len(header_bytes)} bytes (need at least 8 for header)."
            )
            return result
    except OSError as exc:
        result["checks"]["file_readable"] = _FAIL(str(exc))
        return result
    result["checks"]["file_readable"] = _PASS()

    # Check 2 — header internal consistency: sum(nhalos_per_forest) == totnhalos
    nforests, totnhalos = struct.unpack("<ii", header_bytes)
    if nforests <= 0:
        result["checks"]["header_consistency"] = _FAIL(f"nforests={nforests} must be positive.")
        return result

    forest_index_size = nforests * 4
    try:
        with open(binary_path, "rb") as f:
            f.seek(8)
            raw = f.read(forest_index_size)
        if len(raw) < forest_index_size:
            result["checks"]["header_consistency"] = _FAIL(
                f"File truncated: expected {forest_index_size} bytes for nhalos_per_forest, "
                f"got {len(raw)}."
            )
            return result
    except OSError as exc:
        result["checks"]["header_consistency"] = _FAIL(str(exc))
        return result

    nhalos_per_forest = np.frombuffer(raw, dtype=np.int32)
    actual_total = int(nhalos_per_forest.sum())
    if actual_total != totnhalos:
        result["checks"]["header_consistency"] = _FAIL(
            f"sum(nhalos_per_forest)={actual_total} != totnhalos={totnhalos}."
        )
        return result
    result["checks"]["header_consistency"] = _PASS(f"nforests={nforests}, totnhalos={totnhalos}.")

    # Check 3 — file size matches expected layout
    expected_size = 8 + forest_index_size + totnhalos * _BINARY_HALO_DTYPE.itemsize
    try:
        actual_size = os.path.getsize(binary_path)
    except OSError as exc:
        result["checks"]["file_size_consistency"] = _FAIL(str(exc))
        return result
    if actual_size != expected_size:
        result["checks"]["file_size_consistency"] = _FAIL(
            f"Expected {expected_size} bytes, got {actual_size}."
        )
        return result
    result["checks"]["file_size_consistency"] = _PASS(f"{actual_size} bytes.")

    # Check 4 — first tree pointer bounds
    n0 = int(nhalos_per_forest[0])
    halo_data_start = 8 + forest_index_size
    try:
        with open(binary_path, "rb") as f:
            f.seek(halo_data_start)
            raw = f.read(n0 * _BINARY_HALO_DTYPE.itemsize)
        halos = np.frombuffer(raw, dtype=_BINARY_HALO_DTYPE)
    except OSError as exc:
        result["checks"]["first_tree_pointers"] = _FAIL(str(exc))
        result["checks"]["first_tree_snapnums"] = _FAIL("not run (read error above)")
        return result

    ptr_details = []
    for field in (
        "Descendant",
        "FirstProgenitor",
        "NextProgenitor",
        "FirstHaloInFOFgroup",
        "NextHaloInFOFgroup",
    ):
        arr = halos[field].astype(np.int32)
        bad = np.where((arr < -1) | (arr >= n0))[0]
        if len(bad):
            ptr_details.append(
                f"{field}: {len(bad)} out-of-range values "
                f"(first at index {bad[0]}, value={int(arr[bad[0]])})"
            )
    if ptr_details:
        result["checks"]["first_tree_pointers"] = _FAIL("; ".join(ptr_details))
    else:
        result["checks"]["first_tree_pointers"] = _PASS(f"first tree, {n0} halos.")

    # Check 5 — first tree snapshot numbers
    snap = halos["SnapNum"].astype(np.int32)
    snap_details = []
    if np.any(snap < 0):
        snap_details.append(f"{int(np.sum(snap < 0))} negative SnapNum values.")
    if n_snapshots is not None and np.any(snap >= n_snapshots):
        snap_details.append(
            f"{int(np.sum(snap >= n_snapshots))} SnapNum values >= n_snapshots ({n_snapshots})."
        )
    if snap_details:
        result["checks"]["first_tree_snapnums"] = _FAIL(" ".join(snap_details))
    else:
        note = f"range [{int(snap.min())}, {int(snap.max())}]"
        if n_snapshots is None:
            note += " (upper bound not verified — n_snapshots not provided)"
        result["checks"]["first_tree_snapnums"] = _PASS(note)

    result["overall"] = all(c["passed"] for c in result["checks"].values())
    return result
