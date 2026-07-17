#!/usr/bin/env python3
"""
run_binary_checks.py - Syntactic validation for SAGE LHaloTree binary files.
Implements five structural checks on a converted lhalo_binary output file.

Usage:
    python run_binary_checks.py --file <output.0> [--n-snapshots <N>]

Exit code 0 if all checks pass, 1 if any check fails.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "conversion-engine"))
from validation.syntactic import run_binary_checks


def main():
    parser = argparse.ArgumentParser(
        description="Run syntactic validation checks on a SAGE LHaloTree binary file."
    )
    parser.add_argument("--file", required=True, help="Path to the binary file")
    parser.add_argument(
        "--n-snapshots",
        type=int,
        default=None,
        help="Number of snapshots in the simulation (for SnapNum range check)",
    )
    args = parser.parse_args()

    print(f"Running binary syntactic validation on: {args.file}\n")
    result = run_binary_checks(args.file, n_snapshots=args.n_snapshots)

    for name, info in result["checks"].items():
        status = "PASS" if info["passed"] else "FAIL"
        msg = f"  {name}: {status}"
        if not info["passed"] and info.get("detail"):
            msg += f"\n    Reason: {info['detail']}"
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
