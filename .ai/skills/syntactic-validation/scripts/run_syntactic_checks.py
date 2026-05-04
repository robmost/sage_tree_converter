#!/usr/bin/env python3
"""
run_syntactic_checks.py — Syntactic validation for SAGE LHaloTree HDF5 files.
Thin wrapper around conversion-engine/validation/syntactic.py::run_checks.

Usage:
    python run_syntactic_checks.py --file <output.hdf5> [--n-snapshots <N>]

Exit code 0 if all checks pass, 1 if any check fails.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "conversion-engine"))
from validation.syntactic import run_checks

CHECK_LABELS = {
    "file_integrity":             "Check 1 — File integrity",
    "schema_compliance":          "Check 2 — Schema compliance",
    "temporal_pointer_integrity": "Check 3 — Pointer integrity — temporal",
    "spatial_pointer_integrity":  "Check 4 — Pointer integrity — spatial",
    "snapshot_consistency":       "Check 5 — Snapshot consistency",
    "property_consistency":       "Check 6 — Property consistency",
}


def main():
    parser = argparse.ArgumentParser(
        description="Run syntactic validation checks on a SAGE LHaloTree HDF5 file."
    )
    parser.add_argument("--file", required=True, help="Path to the HDF5 file")
    parser.add_argument(
        "--n-snapshots",
        type=int,
        default=None,
        help="Number of snapshots in the simulation (for Check 5)",
    )
    args = parser.parse_args()

    print(f"Running syntactic validation on: {args.file}\n")
    result = run_checks(args.file, n_snapshots=args.n_snapshots)

    for name, label in CHECK_LABELS.items():
        info = result["checks"][name]
        status = "PASS" if info["passed"] else "FAIL"
        msg = f"  {label}: {status}"
        if info.get("detail"):
            tag = "Note" if info["passed"] else "Reason"
            msg += f"\n    {tag}: {info['detail']}"
        print(msg)

    print()
    if result["overall"]:
        print("Overall: ALL CHECKS PASSED")
        sys.exit(0)
    else:
        n_fail = sum(1 for v in result["checks"].values() if not v["passed"])
        print(f"Overall: {n_fail} CHECK(S) FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
