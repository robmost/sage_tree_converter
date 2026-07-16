#!/usr/bin/env python3
"""estimate_output.py - Pre-G1 output-size and memory estimates.

Computes, for a given input dataset and format, the numbers the G1 gate
prompt needs (AGENTS.md Section 3) plus the Stage 2 memory pre-check
(AGENTS.md Section 8):

  - n_trees_total and n_halos (exact where the format allows, estimated
    otherwise - the output says which)
  - estimated output size for both lhalo_hdf5 (120 B/halo) and
    lhalo_binary (104 B/halo)
  - suggested number of output files (8 GB target per file)
  - input size, format-aware memory multiplier, estimated peak memory,
    and available system memory

The multiplier is read from the KDB entry's "memory_multiplier" key when
present; the SAGE_MEMORY_MULTIPLIER environment variable overrides it.

Usage:
    python3 scripts/estimate_output.py --input <file_or_dir> --format <format_id>
"""

import argparse
import json
import math
import os
import re
import struct
import sys
from pathlib import Path

HDF5_BYTES_PER_HALO = 120
BINARY_BYTES_PER_HALO = 104
TARGET_BYTES_PER_FILE = 8_000_000_000
KDB_DIR = Path("format-database")


def _fail(msg: str) -> None:
    sys.exit(f"ERROR: {msg}")


# ---------------------------------------------------------------------------
# Per-format counters. Each returns (n_trees, n_halos, exact: bool).
# ---------------------------------------------------------------------------


def _count_ctrees_ascii(input_path: Path) -> tuple[int, int, bool]:
    """Count '#tree' markers (trees) and data lines (halos). Exact."""
    if input_path.is_file():
        files = [input_path]
    else:
        files = sorted(input_path.glob("tree_*.dat")) or sorted(input_path.glob("*.dat"))
    if not files:
        _fail(f"no Consistent Trees .dat files found under {input_path}")
    n_trees = n_halos = 0
    for fp in files:
        with fp.open() as fh:
            for line in fh:
                if line.startswith("#tree"):
                    n_trees += 1
                elif line and line[0] not in "#\n":
                    n_halos += 1
    return n_trees, n_halos, True


def _count_ahf_ascii(input_path: Path) -> tuple[int, int, bool]:
    """Halos: data lines across all AHF_halos files (exact). Trees: data
    lines in the latest-snapshot file (estimate - the true count needs the
    full croco linkage)."""
    if not input_path.is_dir():
        input_path = input_path.parent
    files = sorted(input_path.glob("*.AHF_halos"))
    if not files:
        _fail(f"no .AHF_halos files found under {input_path}")

    def _data_lines(fp: Path) -> int:
        with fp.open() as fh:
            return sum(1 for line in fh if line and line[0] not in "#\n")

    def _snap_key(fp: Path) -> int:
        m = re.search(r"(\d+)", fp.name)
        return int(m.group(1)) if m else -1

    n_halos = sum(_data_lines(fp) for fp in files)
    n_trees = _data_lines(max(files, key=_snap_key))
    return n_trees, n_halos, False


def _count_lhalotree_binary(input_path: Path) -> tuple[int, int, bool]:
    """Read NTrees and TotNHalos from each trees_<snap>.<N> header. Exact."""
    if input_path.is_file():
        files = [input_path]
    else:
        pattern = re.compile(r"^trees_\d+\.(\d+)$")
        files = sorted(f for f in input_path.iterdir() if pattern.match(f.name))
    if not files:
        _fail(f"no LHaloTree binary files (trees_<snap>.<N>) found under {input_path}")
    n_trees = n_halos = 0
    for fp in files:
        with fp.open("rb") as fh:
            ntrees, totnhalos = struct.unpack("<ii", fh.read(8))
        n_trees += ntrees
        n_halos += totnhalos
    return n_trees, n_halos, True


def _count_gadget4_hdf5(input_path: Path) -> tuple[int, int, bool]:
    """Read the TreeTable lengths. Exact, O(header)."""
    import h5py

    if input_path.is_dir():
        candidates = sorted(input_path.glob("*.hdf5")) + sorted(input_path.glob("*.h5"))
        if not candidates:
            _fail(f"no HDF5 files found under {input_path}")
        input_path = candidates[0]
    with h5py.File(input_path, "r") as f:
        tree_table: h5py.Group = f["TreeTable"]  # type: ignore[assignment]
        length_ds: h5py.Dataset = tree_table["Length"]  # type: ignore[assignment]
        lengths = length_ds[:]
    return int(lengths.size), int(lengths.sum()), True


COUNTERS = {
    "rockstar_consistent_trees_ascii": _count_ctrees_ascii,
    "ahf_mergetree_ascii": _count_ahf_ascii,
    "subfind_lhalotree_binary": _count_lhalotree_binary,
    "subfind_gadget4_hdf5": _count_gadget4_hdf5,
}


# ---------------------------------------------------------------------------
# Input size, multiplier, available memory
# ---------------------------------------------------------------------------


def _input_size_bytes(input_path: Path) -> int:
    if input_path.is_file():
        return input_path.stat().st_size
    return sum(f.stat().st_size for f in input_path.rglob("*") if f.is_file())


def _memory_multiplier(format_id: str) -> tuple[float, str]:
    env = os.environ.get("SAGE_MEMORY_MULTIPLIER")
    if env:
        return float(env), "SAGE_MEMORY_MULTIPLIER"
    kdb_entry = KDB_DIR / f"{format_id}.json"
    if kdb_entry.is_file():
        value = json.loads(kdb_entry.read_text()).get("memory_multiplier")
        if value:
            return float(value), f"{kdb_entry}"
    return 3.0, "default"


def _available_memory_bytes() -> int | None:
    try:
        import psutil

        return int(psutil.virtual_memory().available)
    except ImportError:
        pass
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        for line in meminfo.read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    return None


def _gb(n_bytes: float) -> str:
    return f"{n_bytes / 1e9:.2f} GB"


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-G1 output-size and memory estimates.")
    parser.add_argument("--input", required=True, help="Input file or dataset directory")
    parser.add_argument("--format", required=True, choices=sorted(COUNTERS), dest="format_id")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        _fail(f"input path does not exist: {input_path}")

    n_trees, n_halos, exact = COUNTERS[args.format_id](input_path)
    tag = "exact" if exact else "estimated"
    hdf5_bytes = n_halos * HDF5_BYTES_PER_HALO
    binary_bytes = n_halos * BINARY_BYTES_PER_HALO
    n_files = max(1, math.ceil(hdf5_bytes / TARGET_BYTES_PER_FILE))

    input_bytes = _input_size_bytes(input_path)
    multiplier, source = _memory_multiplier(args.format_id)
    peak = input_bytes * multiplier
    available = _available_memory_bytes()

    print(f"Format:                 {args.format_id}")
    print(f"Trees (n_trees_total):  {n_trees}  ({tag})")
    print(f"Halos:                  {n_halos}  ({tag})")
    print(f"Estimated output hdf5:  {_gb(hdf5_bytes)}  ({HDF5_BYTES_PER_HALO} B/halo)")
    print(f"Estimated output bin:   {_gb(binary_bytes)}  ({BINARY_BYTES_PER_HALO} B/halo)")
    print(f"Suggested n_files:      {n_files}  (~{_gb(hdf5_bytes / n_files)} each, hdf5)")
    print(f"Input size:             {_gb(input_bytes)}")
    print(f"Memory multiplier:      {multiplier}  (from {source})")
    print(f"Estimated peak memory:  {_gb(peak)}")
    if available is None:
        print("Available memory:       could not be determined (note this to the user)")
    else:
        print(f"Available memory:       {_gb(available)}")
        if peak > available:
            print(
                "WARNING: estimated peak memory exceeds available memory - "
                "warn the user and ask whether to proceed (AGENTS.md Section 8)."
            )


if __name__ == "__main__":
    main()
