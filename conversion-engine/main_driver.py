#!/usr/bin/env python3
"""
main_driver.py — Entry point for all SAGE merger tree conversions.

Usage:
    Stage 2 (test, 100 trees):
        $PYTHON_BIN conversion-engine/main_driver.py --input <path> \
            --output assets/test_<base>_STC.0.hdf5 --n-trees 100 [--format <format_id>] \
            [--output-format {lhalo_hdf5,lhalo_binary}]

    Stage 3 (full conversion):
        $PYTHON_BIN conversion-engine/main_driver.py --input <path> \
            --output output/<base>_STC.0.hdf5 [--format <format_id>] \
            [--output-format {lhalo_hdf5,lhalo_binary}]

    <base> is the dataset directory name inside input/ (see AGENTS.md §13):
    - Directory input: base = Path(input_path).name
    - File input:      base = Path(input_path).parent.name
    Files placed directly in input/ (not in a subdirectory) are not supported.
    Run from the project root so that relative paths resolve correctly.

    --output-format lhalo_hdf5   (default) SAGE LHaloTree HDF5 (TreeType=1)
    --output-format lhalo_binary           SAGE LHaloTree binary (TreeType=0)
"""

import argparse
import importlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Format registry — maps format_id to the driver module filename (no .py).
# Updated during Stage 4 when new drivers are registered.
# ---------------------------------------------------------------------------
FORMAT_REGISTRY: dict[str, str] = {
    "subfind_lhalotree_binary": "subfind_lhalotree_binary",
    "rockstar_consistent_trees_ascii": "rockstar_consistent_trees_ascii",
    "ahf_mergetree_ascii": "ahf_mergetree_ascii",
    "subfind_gadget4_hdf5": "subfind_gadget4_hdf5",
}

KDB_DIR = "format-database"


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _auto_detect_format(input_path: str) -> str | None:
    """Scan format-database/*.json and return the first matching format_id.

    Matching is based on the file extension of input_path compared to the
    'file_format' field in each KDB entry. A full match also requires the
    entry's format_id to be in FORMAT_REGISTRY (i.e., its driver is present).
    This is a best-effort heuristic; the user should confirm the detected
    format or supply --format explicitly.
    """
    kdb_path = Path(KDB_DIR)
    if not kdb_path.is_dir():
        return None

    ext = Path(input_path).suffix.lower()
    ext_map = {".hdf5": "hdf5", ".h5": "hdf5", ".txt": "ascii", ".dat": "ascii"}
    detected_file_format = ext_map.get(ext)

    candidates = []
    for json_file in sorted(kdb_path.glob("*.json")):
        try:
            entry = json.loads(json_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        fmt_id = entry.get("format_id", "")
        if fmt_id not in FORMAT_REGISTRY:
            continue
        if detected_file_format and entry.get("file_format") == detected_file_format:
            candidates.append(fmt_id)

    if len(candidates) == 1:
        return candidates[0]
    return None


def _import_driver(format_id: str):
    """Import and return the driver module for the given format_id."""
    module_name = FORMAT_REGISTRY[format_id]
    # Ensure conversion-engine/ is on sys.path so 'drivers.<name>' resolves.
    engine_dir = str(Path(__file__).parent)
    if engine_dir not in sys.path:
        sys.path.insert(0, engine_dir)
    return importlib.import_module(f"drivers.{module_name}")


def main() -> None:
    _setup_logging()
    log = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(
        description="Convert merger tree files to SAGE LHaloTree HDF5 format.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="PATH",
        help="Path to the input file or directory.",
    )
    parser.add_argument(
        "--output", required=True, metavar="PATH", help="Path for the output HDF5 file."
    )
    parser.add_argument(
        "--format",
        metavar="FORMAT_ID",
        default=None,
        help="Format identifier (e.g. 'ahf_mergertree_ascii'). "
        "If omitted, auto-detection is attempted.",
    )
    parser.add_argument(
        "--n-trees",
        type=int,
        default=None,
        metavar="N",
        help="Convert only the first N trees (Stage 2 test mode).",
    )
    parser.add_argument(
        "--particle-mass",
        type=float,
        default=None,
        metavar="MSUN_PER_H",
        help="Dark matter particle mass in Msun/h. Overrides the value "
        "computed from the file header (use when the simulation "
        "N_particles differs from the driver default).",
    )
    parser.add_argument(
        "--output-format",
        metavar="FORMAT",
        default="lhalo_hdf5",
        choices=["lhalo_hdf5", "lhalo_binary"],
        help="Output format: 'lhalo_hdf5' (default, SAGE TreeType=1) or "
        "'lhalo_binary' (SAGE TreeType=0).",
    )
    args = parser.parse_args()

    log.info("SAGE merger tree converter starting — %s", datetime.now().isoformat())
    log.info("Input : %s", args.input)
    log.info("Output: %s", args.output)
    log.info("Output format: %s", args.output_format)
    if args.n_trees:
        log.info("Mode  : test (first %d trees)", args.n_trees)

    # -----------------------------------------------------------------------
    # Resolve format
    # -----------------------------------------------------------------------
    format_id = args.format

    if format_id is None:
        log.info("--format not supplied; attempting auto-detection …")
        format_id = _auto_detect_format(args.input)
        if format_id is None:
            log.error(
                "Auto-detection failed. No matching format found in %s "
                "for input '%s'. Use --format to specify the format explicitly.",
                KDB_DIR,
                args.input,
            )
            sys.exit(1)
        log.info("Auto-detected format: %s", format_id)
    else:
        log.info("Format: %s (user-specified)", format_id)

    if format_id not in FORMAT_REGISTRY:
        log.error(
            "Unknown format '%s'. Registered formats: %s",
            format_id,
            sorted(FORMAT_REGISTRY.keys()) or ["(none — add drivers in Stage 4)"],
        )
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Import driver
    # -----------------------------------------------------------------------
    try:
        driver = _import_driver(format_id)
        log.info("Driver imported: drivers.%s", FORMAT_REGISTRY[format_id])
    except ImportError as exc:
        log.error("Failed to import driver for '%s': %s", format_id, exc)
        sys.exit(1)

    if not hasattr(driver, "convert"):
        log.error(
            "Driver module 'drivers.%s' does not expose a 'convert' function.",
            FORMAT_REGISTRY[format_id],
        )
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Run conversion
    # -----------------------------------------------------------------------
    if args.particle_mass is not None:
        log.info("Particle mass override: %.3e Msun/h", args.particle_mass)

    log.info("Conversion started.")
    try:
        driver.convert(
            args.input,
            args.output,
            n_trees=args.n_trees,
            particle_mass=args.particle_mass,
            output_format=args.output_format,
        )
    except SystemExit:
        log.error("Driver exited with an error. See messages above.")
        sys.exit(1)
    except Exception as exc:
        log.error("Conversion failed with unhandled exception: %s", exc)
        sys.exit(1)

    log.info("Conversion complete. Output: %s", args.output)


if __name__ == "__main__":
    main()
