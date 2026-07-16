#!/usr/bin/env python3
"""run_semantic_plots.py - CLI wrapper for the seven semantic validation plots.

Thin wrapper around conversion-engine/validation/semantic.py::generate_all_plots
so Stage 3 (and direct-conversion users) can render the plots with one
deterministic command instead of an ad-hoc Python snippet.

Usage:
    python3 scripts/run_semantic_plots.py --file output/<base>_STC.0.hdf5
    python3 scripts/run_semantic_plots.py --file output/<base>_STC.0 \\
        --output-format lhalo_binary

Plots (PDF plus PNG siblings) are written to assets/semantic_validation/ by
default. Exit code 0 when all seven plots are produced.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "conversion-engine"))

import matplotlib

matplotlib.use("Agg")

from validation.semantic import generate_all_plots  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", required=True, help="Converted SAGE LHaloTree output file")
    parser.add_argument(
        "--output-format",
        choices=("lhalo_hdf5", "lhalo_binary"),
        default="lhalo_hdf5",
    )
    parser.add_argument("--output-dir", default="assets/semantic_validation")
    parser.add_argument("--style", default="reference/sage_validation.mplstyle")
    args = parser.parse_args()

    saved = generate_all_plots(
        output_path=args.file,
        output_dir=args.output_dir,
        style_path=args.style,
        output_format=args.output_format,
    )
    if len(saved) != 7:
        sys.exit(f"ERROR: expected 7 plots, got {len(saved)}.")


if __name__ == "__main__":
    main()
