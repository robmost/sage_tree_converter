#!/usr/bin/env python3
"""extract_snaplist.py - Build the FileWithSnapList file for a SAGE dry run.

SAGE rejects an empty FileWithSnapList, so functional validation always needs
a snapshot scale-factor list. Two modes cover the supported inputs:

ascii mode (Rockstar/Consistent Trees and similar column formats):
    Streams the input catalogue, collecting one scale factor per snapshot
    index from two columns. Defaults match Consistent Trees (scale factor in
    column 0, snap index in column 31); override per format from the driver's
    column map.

    python3 scripts/extract_snaplist.py ascii --input <trees.dat> \\
        --out assets/<dataset>_snaplist.txt [--scale-col 0] [--snap-col 31]

hdf5-output mode (binary/LHaloTree inputs with an external scale list):
    Reads the SnapNum values present in Tree0 of a converted test output and
    pairs each with its scale factor from the simulation's own list file
    (snap_times.txt, output_list.txt, ...; one scale factor per line, indexed
    by snapshot number).

    python3 scripts/extract_snaplist.py hdf5-output --output-file \\
        assets/test_<base>_STC.0.hdf5 --scales-file <sim>/snap_times.txt \\
        --out assets/<dataset>_snaplist.txt

Output: one scale factor per line, ordered by snapshot index ascending.
"""

import argparse
import sys
from pathlib import Path


def _write(snap_to_scale: dict[int, float], out_path: Path) -> None:
    if not snap_to_scale:
        sys.exit("ERROR: no (snapshot, scale factor) pairs found.")
    snaps = sorted(snap_to_scale)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as out:
        for s in snaps:
            out.write(f"{snap_to_scale[s]:.8f}\n")
    print(f"Wrote {len(snaps)} scale factors (snap {snaps[0]}-{snaps[-1]}) to {out_path}")


def cmd_ascii(args: argparse.Namespace) -> None:
    snap_to_scale: dict[int, float] = {}
    min_cols = max(args.scale_col, args.snap_col) + 1
    with open(args.input) as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < min_cols:
                continue
            try:
                scale = float(parts[args.scale_col])
                snap = int(float(parts[args.snap_col]))
            except ValueError:
                continue
            snap_to_scale.setdefault(snap, scale)
    _write(snap_to_scale, Path(args.out))


def cmd_hdf5_output(args: argparse.Namespace) -> None:
    import h5py

    scales = [float(line) for line in Path(args.scales_file).read_text().split() if line.strip()]
    with h5py.File(args.output_file, "r") as f:
        tree0: h5py.Group = f["Tree0"]  # type: ignore[assignment]
        snap_ds: h5py.Dataset = tree0["SnapNum"]  # type: ignore[assignment]
        snaps = sorted(set(snap_ds[:].tolist()))
    missing = [s for s in snaps if s >= len(scales)]
    if missing:
        sys.exit(
            f"ERROR: snapshots {missing} exceed the {len(scales)} entries in "
            f"{args.scales_file} - wrong scale list for this simulation?"
        )
    _write({s: scales[s] for s in snaps}, Path(args.out))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the FileWithSnapList file for a SAGE dry run."
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    p_ascii = sub.add_parser("ascii", help="scan an ASCII catalogue for scale factors")
    p_ascii.add_argument("--input", required=True)
    p_ascii.add_argument("--out", required=True)
    p_ascii.add_argument("--scale-col", type=int, default=0)
    p_ascii.add_argument("--snap-col", type=int, default=31)
    p_ascii.set_defaults(func=cmd_ascii)

    p_h5 = sub.add_parser("hdf5-output", help="pair converted SnapNums with an external list")
    p_h5.add_argument("--output-file", required=True)
    p_h5.add_argument("--scales-file", required=True)
    p_h5.add_argument("--out", required=True)
    p_h5.set_defaults(func=cmd_hdf5_output)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
