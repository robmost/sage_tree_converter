#!/usr/bin/env python3
"""
main_driver.py — Entry point for all SAGE merger tree conversions.

Usage:
    Test run (100 trees):
        $PYTHON_BIN conversion-engine/main_driver.py --input <path> \
            --output assets/test_<base>_STC.0.hdf5 --n-trees 100 [--format <format_id>] \
            [--output-format {lhalo_hdf5,lhalo_binary}] [--sim-config <path.json>]

    Full conversion:
        $PYTHON_BIN conversion-engine/main_driver.py --input <path> \
            --output output/<base>_STC.0.hdf5 [--format <format_id>] \
            [--output-format {lhalo_hdf5,lhalo_binary}] [--sim-config <path.json>]

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
import types
from datetime import datetime
from pathlib import Path

from errors import ConversionError

# ---------------------------------------------------------------------------
# Format registry — maps format_id to the driver module filename (no .py).
# ---------------------------------------------------------------------------
FORMAT_REGISTRY: dict[str, str] = {
    "subfind_lhalotree_binary": "subfind_lhalotree_binary",
    "rockstar_consistent_trees_ascii": "rockstar_consistent_trees_ascii",
    "ahf_mergetree_ascii": "ahf_mergetree_ascii",
    "subfind_gadget4_hdf5": "subfind_gadget4_hdf5",
}

KDB_DIR = "format-database"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


_VALID_OUTPUT_FORMATS = frozenset({"lhalo_hdf5", "lhalo_binary"})


def _positive_int(value: str) -> int:
    """argparse type validator: accept only integers >= 1."""
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer.")
    if n < 1:
        raise argparse.ArgumentTypeError(f"Number of output files must be >= 1, got {n}.")
    return n


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


def _import_driver(format_id: str) -> types.ModuleType:
    """Import and return the driver module for the given format_id."""
    module_name = FORMAT_REGISTRY[format_id]
    # Ensure conversion-engine/ is on sys.path so 'drivers.<name>' resolves.
    engine_dir = str(Path(__file__).parent)
    if engine_dir not in sys.path:
        sys.path.insert(0, engine_dir)
    return importlib.import_module(f"drivers.{module_name}")


def convert_one(
    input_path: str,
    output_path: str,
    format_id: str | None = None,
    n_trees: int | None = None,
    sim_params: dict | None = None,
    output_format: str = "lhalo_hdf5",
    n_output_files: int = 1,
) -> None:
    """Run one conversion. Raises RuntimeError on failure (does not sys.exit).

    Parameters
    ----------
    input_path:      Path to the input file or directory.
    output_path:     Path for output file index 0.
    format_id:       KDB format identifier. Auto-detected from file extension if None.
    n_trees:         Convert only the first N trees (test mode). None = all trees.
    sim_params:      Simulation parameter overrides (same keys as --sim-config JSON).
    output_format:   "lhalo_hdf5" (default) or "lhalo_binary".
    n_output_files:  Number of output files to split across (must be >= 1).
    """
    log = logging.getLogger(__name__)

    if output_format not in _VALID_OUTPUT_FORMATS:
        raise RuntimeError(
            f"Invalid output_format {output_format!r}. "
            f"Valid values: {sorted(_VALID_OUTPUT_FORMATS)}"
        )

    log.info("SAGE merger tree converter starting — %s", datetime.now().isoformat())
    log.info("Input : %s", input_path)
    log.info("Output: %s", output_path)
    log.info("Output format: %s", output_format)
    log.info("Output files : %d", n_output_files)
    if n_trees is not None:
        log.info("Mode  : test (first %d trees)", n_trees)

    # -----------------------------------------------------------------------
    # Resolve format
    # -----------------------------------------------------------------------
    resolved_format = format_id

    if resolved_format is None:
        if Path(input_path).is_dir():
            raise RuntimeError(
                f"Auto-detection is not supported for directory inputs. "
                f"Specify --format (or format_id) explicitly for {input_path!r}."
            )
        log.info("format_id not supplied; attempting auto-detection …")
        resolved_format = _auto_detect_format(input_path)
        if resolved_format is None:
            raise RuntimeError(
                f"Auto-detection failed. No matching format found in {KDB_DIR!r} "
                f"for input {input_path!r}. Supply format_id explicitly."
            )
        log.info("Auto-detected format: %s", resolved_format)
    else:
        log.info("Format: %s (user-specified)", resolved_format)

    if resolved_format not in FORMAT_REGISTRY:
        known = sorted(FORMAT_REGISTRY.keys()) or ["(none registered)"]
        raise RuntimeError(
            f"Unknown format {resolved_format!r}. Registered formats: {known}"
        )

    # -----------------------------------------------------------------------
    # Import driver
    # -----------------------------------------------------------------------
    try:
        driver = _import_driver(resolved_format)
        log.info("Driver imported: drivers.%s", FORMAT_REGISTRY[resolved_format])
    except ImportError as exc:
        raise RuntimeError(f"Failed to import driver for {resolved_format!r}: {exc}") from exc

    module_name = FORMAT_REGISTRY[resolved_format]
    if not hasattr(driver, "convert"):
        raise RuntimeError(
            f"Driver module 'drivers.{module_name}' does not expose a 'convert' function."
        )

    # -----------------------------------------------------------------------
    # Run conversion
    # -----------------------------------------------------------------------
    log.info("Conversion started.")
    try:
        driver.convert(
            input_path,
            output_path,
            n_trees=n_trees,
            sim_params=sim_params or {},
            output_format=output_format,
            n_output_files=n_output_files,
        )
    except ConversionError as exc:
        raise RuntimeError(str(exc)) from exc
    except SystemExit as exc:
        raise RuntimeError("Driver exited with an error. See messages above.") from exc
    except Exception as exc:
        raise RuntimeError(f"Conversion failed with unhandled exception: {exc}") from exc

    log.info("Conversion complete. Output: %s", output_path)


def main() -> None:
    setup_logging()
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
        help="Convert only the first N trees (test mode).",
    )
    parser.add_argument(
        "--sim-config",
        metavar="PATH",
        default=None,
        help=(
            "Path to a JSON file with simulation parameter overrides "
            "(particle_mass_msun_per_h, n_particles_per_side, box_size_mpc_per_h, "
            "omega_m, omega_l, h0). All keys are optional. "
            "See reference/sim_config_template.json for the schema."
        ),
    )
    parser.add_argument(
        "--output-format",
        metavar="FORMAT",
        default="lhalo_hdf5",
        choices=["lhalo_hdf5", "lhalo_binary"],
        help="Output format: 'lhalo_hdf5' (default, SAGE TreeType=1) or "
        "'lhalo_binary' (SAGE TreeType=0).",
    )
    parser.add_argument(
        "--n-output-files",
        type=_positive_int,
        default=1,
        metavar="N",
        help="Number of output files to split trees across (default: 1). Must be >= 1.",
    )
    args = parser.parse_args()

    sim_params: dict = {}
    if args.sim_config is not None:
        try:
            with open(args.sim_config) as fh:
                sim_params = json.load(fh)
            log.info("Simulation config loaded from: %s", args.sim_config)
        except (OSError, json.JSONDecodeError) as exc:
            log.error("Failed to load --sim-config '%s': %s", args.sim_config, exc)
            sys.exit(1)

    try:
        convert_one(
            input_path=args.input,
            output_path=args.output,
            format_id=args.format,
            n_trees=args.n_trees,
            sim_params=sim_params,
            output_format=args.output_format,
            n_output_files=args.n_output_files,
        )
    except RuntimeError as exc:
        log.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
