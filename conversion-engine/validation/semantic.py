"""
semantic.py — Seven mandatory semantic validation plots for SAGE merger tree conversion.

Compares input (unconverted) and output (converted) HDF5 files across seven physical
diagnostics. All plots use reference/sage_validation.mplstyle and are saved to
assets/semantic_validation/.

Usage:
    from validation.semantic import generate_all_plots
    saved = generate_all_plots(
        input_hdf5="input/original.hdf5",
        output_hdf5="output/converted.hdf5",
    )

PROHIBITIONS (enforced in code):
  - Never use output data in the input column.
  - Never plot SubhaloVMax as the velocity distribution (always use |SubhaloVel|).
  - Never call plt.savefig() or plt.close() directly — always use save_figure().
  - Never use different halo/tree samples for input and output columns.
"""

import os
import struct as _struct

import h5py
import matplotlib.pyplot as plt
import numpy as np

from .plot_utils import (
    add_reldiff_hline,
    make_1x3_figure,
    make_3x3_figure,
    rel_diff,
    save_figure,
    set_reldiff_ylim,
)

_BINARY_HALO_DTYPE = np.dtype([
    ("Descendant",          np.int32),
    ("FirstProgenitor",     np.int32),
    ("NextProgenitor",      np.int32),
    ("FirstHaloInFOFgroup", np.int32),
    ("NextHaloInFOFgroup",  np.int32),
    ("Len",                 np.int32),
    ("M_Mean200",           np.float32),
    ("Mvir",                np.float32),
    ("M_TopHat",            np.float32),
    ("Pos",                 np.float32, 3),
    ("Vel",                 np.float32, 3),
    ("VelDisp",             np.float32),
    ("Vmax",                np.float32),
    ("Spin",                np.float32, 3),
    ("MostBoundID",         np.int64),
    ("SnapNum",             np.int32),
    ("FileNr",              np.int32),
    ("SubhaloIndex",        np.int32),
    ("SubHalfMass",         np.float32),
])


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_trees(hdf5_path: str) -> dict[int, dict[str, np.ndarray]]:
    """Load all trees from an HDF5 file into memory.

    Returns
    -------
    dict mapping tree_idx (int) → dict of field_name → numpy array.
    """
    trees = {}
    with h5py.File(hdf5_path, "r") as f:
        for key in f.keys():
            if not key.startswith("Tree"):
                continue
            idx = int(key[4:])
            grp = f[key]
            trees[idx] = {field: grp[field][:] for field in grp.keys()}
    return trees


def _load_binary_trees(binary_path: str) -> dict[int, dict[str, np.ndarray]]:
    """Load all trees from a SAGE LHaloTree binary file.

    Normalises SubhaloPos (Mpc/h → kpc/h, ×1000) and SubhaloSpin
    ((Mpc/h)(km/s) → (kpc/h)(km/s), ×1000) to match HDF5 on-disk convention
    so both sides of the comparison use equivalent quantities.
    """
    trees = {}
    with open(binary_path, "rb") as fp:
        nforests   = _struct.unpack("<i", fp.read(4))[0]
        _totnhalos = _struct.unpack("<i", fp.read(4))[0]
        nhalos_per_forest = np.frombuffer(fp.read(nforests * 4), dtype=np.int32).copy()
        for idx in range(nforests):
            n = int(nhalos_per_forest[idx])
            if n == 0:
                trees[idx] = {}
                continue
            raw   = fp.read(n * _BINARY_HALO_DTYPE.itemsize)
            halos = np.frombuffer(raw, dtype=_BINARY_HALO_DTYPE).copy()
            trees[idx] = {
                "Descendant":          halos["Descendant"],
                "FirstProgenitor":     halos["FirstProgenitor"],
                "NextProgenitor":      halos["NextProgenitor"],
                "FirstHaloInFOFGroup": halos["FirstHaloInFOFgroup"],
                "NextHaloInFOFGroup":  halos["NextHaloInFOFgroup"],
                "SubhaloLen":          halos["Len"],
                "Group_M_Crit200":     halos["Mvir"],
                "Group_M_Mean200":     halos["M_Mean200"],
                "Group_M_TopHat200":   halos["M_TopHat"],
                "SubhaloPos":  (halos["Pos"]  * np.float32(1000.0)).astype(np.float32),
                "SubhaloVel":          halos["Vel"],
                "SubhaloVelDisp":      halos["VelDisp"],
                "SubhaloVMax":         halos["Vmax"],
                "SubhaloSpin": (halos["Spin"] * np.float32(1000.0)).astype(np.float32),
                "SubhaloIDMostBound":  halos["MostBoundID"],
                "SnapNum":             halos["SnapNum"],
                "FileNr":              halos["FileNr"],
            }
    return trees


def _load_native_trees(
    format_id: str,
    input_path: str,
    n_trees: int | None = None,
) -> dict[int, dict]:
    """Load trees from a native input format using the format's conversion driver.

    Checks conversion-engine/drivers/<format_id>.py first, then
    assets/drivers/<format_id>.py. The driver must expose a read_trees()
    function that returns dict[int, dict[str, np.ndarray]].

    Raises ValueError if no driver is found or if the driver lacks read_trees().
    """
    import importlib.util
    import sys
    from pathlib import Path

    engine_dir = Path(__file__).parent.parent
    candidates = [
        engine_dir / "drivers" / f"{format_id}.py",
        engine_dir.parent / "assets" / "drivers" / f"{format_id}.py",
    ]
    driver_path = next((p for p in candidates if p.exists()), None)
    if driver_path is None:
        raise ValueError(
            f"No driver found for input_format='{format_id}'. "
            f"Searched: {[str(c) for c in candidates]}"
        )

    # Ensure conversion-engine/ is importable so driver utils imports work.
    engine_str = str(engine_dir)
    if engine_str not in sys.path:
        sys.path.insert(0, engine_str)

    spec = importlib.util.spec_from_file_location(format_id, driver_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if not hasattr(mod, "read_trees"):
        raise ValueError(
            f"Driver '{driver_path.name}' does not implement read_trees(). "
            "Add read_trees(input_path, n_trees=None) to the driver."
        )
    return mod.read_trees(input_path, n_trees=n_trees)


def _find_lowest_snap(trees: dict) -> int:
    """Return the snapshot index of the lowest-redshift snapshot (highest SnapNum)."""
    return max(
        int(np.max(t["SnapNum"])) for t in trees.values() if len(t["SnapNum"]) > 0
    )


def _root_halos_at_snap(tree: dict, snap: int) -> np.ndarray:
    """Return indices of halos at snapshot snap whose Descendant is -1 (roots)."""
    snap_arr = tree["SnapNum"]
    desc_arr = tree["Descendant"]
    mask = (snap_arr == snap) & (desc_arr == -1)
    return np.where(mask)[0]


def _select_mass_bins(
    in_trees: dict, lowest_snap: int
) -> tuple[list[int], list[int], list[int]]:
    """Select top-5, median-5, and bottom-5 tree indices by root-halo mass.

    Trees with no root halo at lowest_snap, or with Group_M_Crit200 <= 0, are excluded.
    Returns three lists of tree_idx values (may be shorter than 5 if too few trees).
    """
    root_masses = {}
    for idx, tree in in_trees.items():
        roots = _root_halos_at_snap(tree, lowest_snap)
        if len(roots) == 0:
            continue
        mass = float(np.max(tree["Group_M_Crit200"][roots]))
        if mass > 0:
            root_masses[idx] = mass

    if not root_masses:
        return [], [], []

    sorted_ids = sorted(root_masses, key=root_masses.__getitem__, reverse=True)
    n = len(sorted_ids)
    k = min(5, n)

    top = sorted_ids[:k]
    bottom = sorted_ids[max(0, n - k):]
    mid_start = max(0, n // 2 - k // 2)
    median = sorted_ids[mid_start: mid_start + k]

    return top, median, bottom


def _main_progenitor_branch(tree: dict, root_idx: int) -> tuple[list[int], list[float]]:
    """Walk the main progenitor branch from root_idx downward (O(depth)).

    Returns (snap_list, mass_list) sorted ascending by snapshot (oldest first).
    """
    snaps, masses = [], []
    h = root_idx
    while h != -1:
        snaps.append(int(tree["SnapNum"][h]))
        masses.append(float(tree["Group_M_Crit200"][h]))
        h = int(tree["FirstProgenitor"][h])
    return snaps, masses


def _main_progenitor_spins(tree: dict, root_idx: int) -> tuple[list[int], list[float]]:
    """Walk the main progenitor branch and return (snaps, |SubhaloSpin|) lists."""
    snaps, spins = [], []
    h = root_idx
    while h != -1:
        snaps.append(int(tree["SnapNum"][h]))
        spin_vec = tree["SubhaloSpin"][h]
        spins.append(float(np.linalg.norm(spin_vec)))
        h = int(tree["FirstProgenitor"][h])
    return snaps, spins


def _merger_rate_along_branch(tree: dict, root_idx: int) -> dict[int, int]:
    """Count halos merging into the main-branch halo at each snapshot (O(N)).

    Build a descendant→count map in one pass over all halos in the tree.
    """
    desc = tree["Descendant"]
    snap = tree["SnapNum"]
    N = len(desc)

    # Identify main-branch halo indices (O(depth))
    branch_set = set()
    h = root_idx
    while h != -1:
        branch_set.add(h)
        h = int(tree["FirstProgenitor"][h])

    # Count progenitors of each main-branch halo (O(N))
    rate: dict[int, int] = {h: 0 for h in branch_set}
    for i in range(N):
        d = int(desc[i])
        if d in branch_set and i not in branch_set:
            s = int(snap[d])
            rate[d] = rate.get(d, 0) + 1

    # Re-key by snapshot number
    snap_rate: dict[int, int] = {}
    for h in branch_set:
        s = int(snap[h])
        snap_rate[s] = rate.get(h, 0)
    return snap_rate


def _lifespan(tree: dict, root_idx: int) -> int:
    """Count distinct snapshots along the main progenitor branch."""
    h = root_idx
    snaps = set()
    while h != -1:
        snaps.add(int(tree["SnapNum"][h]))
        h = int(tree["FirstProgenitor"][h])
    return len(snaps)


# ---------------------------------------------------------------------------
# 3×3 evolution plots
# ---------------------------------------------------------------------------

def _plot_mah(
    in_trees: dict, out_trees: dict, mass_bins: tuple, output_dir: str, style_path: str = "reference/sage_validation.mplstyle"
) -> str:
    """Plot 1 — Mass Accretion History (3×3)."""
    if os.path.isfile(style_path):
        plt.style.use(style_path)

    top, median, bottom = mass_bins
    bin_groups = [top, median, bottom]

    fig, axes = make_3x3_figure(
        col_titles=("Input — MAH", "Output — MAH", "Relative difference"),
    )

    for row_idx, tree_ids in enumerate(bin_groups):
        all_reldiff = []
        for tid in tree_ids:
            in_tree = in_trees[tid]
            out_tree = out_trees[tid]

            in_roots = _root_halos_at_snap(in_tree, max(in_tree["SnapNum"]))
            out_roots = _root_halos_at_snap(out_tree, max(out_tree["SnapNum"]))
            if len(in_roots) == 0 or len(out_roots) == 0:
                continue

            in_snaps, in_masses = _main_progenitor_branch(in_tree, int(in_roots[0]))
            out_snaps, out_masses = _main_progenitor_branch(out_tree, int(out_roots[0]))

            in_masses_pos = [m if m > 0 else np.nan for m in in_masses]
            out_masses_pos = [m if m > 0 else np.nan for m in out_masses]

            axes[row_idx, 0].semilogy(in_snaps, in_masses_pos, alpha=0.6, marker="o", markersize=3, label=f"Tree {tid}")
            axes[row_idx, 1].semilogy(out_snaps, out_masses_pos, alpha=0.6, marker="o", markersize=3)

            # Relative difference on common snapshots
            in_map = dict(zip(in_snaps, in_masses))
            common = sorted(set(in_snaps) & set(out_snaps))
            if common:
                in_m = np.array([in_map[s] for s in common])
                out_m = np.array([dict(zip(out_snaps, out_masses))[s] for s in common])
                rd = rel_diff(out_m, in_m)
                axes[row_idx, 2].plot(common, rd, alpha=0.6, marker="o", markersize=2)
                all_reldiff.extend(rd[np.isfinite(rd)].tolist())

        axes[row_idx, 0].legend(fontsize="x-small", loc="best")
        axes[row_idx, 0].set_xlabel("SnapNum")
        axes[row_idx, 0].set_ylabel("Group_M_Crit200 [10¹⁰ M☉/h]")
        axes[row_idx, 1].set_xlabel("SnapNum")
        axes[row_idx, 2].set_xlabel("SnapNum")
        axes[row_idx, 2].set_ylabel("(output - input) / input")
        add_reldiff_hline(axes[row_idx, 2])
        if all_reldiff:
            set_reldiff_ylim(axes[row_idx, 2], all_reldiff)

    path = os.path.join(output_dir, "mah.pdf")
    save_figure(fig, path)
    return path


def _plot_merger_rate(
    in_trees: dict, out_trees: dict, mass_bins: tuple, output_dir: str, style_path: str = "reference/sage_validation.mplstyle"
) -> str:
    """Plot 2 — Merger Rate (3×3)."""
    if os.path.isfile(style_path):
        plt.style.use(style_path)

    top, median, bottom = mass_bins
    bin_groups = [top, median, bottom]

    fig, axes = make_3x3_figure(
        col_titles=("Input — Merger rate", "Output — Merger rate", "Relative difference"),
    )

    for row_idx, tree_ids in enumerate(bin_groups):
        all_reldiff = []
        for tid in tree_ids:
            in_tree = in_trees[tid]
            out_tree = out_trees[tid]

            in_roots = _root_halos_at_snap(in_tree, max(in_tree["SnapNum"]))
            out_roots = _root_halos_at_snap(out_tree, max(out_tree["SnapNum"]))
            if len(in_roots) == 0 or len(out_roots) == 0:
                continue

            in_rate = _merger_rate_along_branch(in_tree, int(in_roots[0]))
            out_rate = _merger_rate_along_branch(out_tree, int(out_roots[0]))

            in_snaps = sorted(in_rate)
            out_snaps = sorted(out_rate)
            axes[row_idx, 0].plot(in_snaps, [in_rate[s] for s in in_snaps], alpha=0.6, marker="o", markersize=3, label=f"Tree {tid}")
            axes[row_idx, 1].plot(out_snaps, [out_rate[s] for s in out_snaps], alpha=0.6, marker="o", markersize=3)

            common = sorted(set(in_snaps) & set(out_snaps))
            if common:
                in_r = np.array([in_rate[s] for s in common], dtype=float)
                out_r = np.array([out_rate[s] for s in common], dtype=float)
                rd = rel_diff(out_r, in_r)
                axes[row_idx, 2].plot(common, rd, alpha=0.6, marker="o", markersize=2)
                all_reldiff.extend(rd[np.isfinite(rd)].tolist())

        axes[row_idx, 0].legend(fontsize="x-small", loc="best")
        axes[row_idx, 0].set_xlabel("SnapNum")
        axes[row_idx, 0].set_ylabel("Number of progenitors")
        axes[row_idx, 1].set_xlabel("SnapNum")
        axes[row_idx, 2].set_xlabel("SnapNum")
        axes[row_idx, 2].set_ylabel("(output - input) / input")
        add_reldiff_hline(axes[row_idx, 2])
        if all_reldiff:
            set_reldiff_ylim(axes[row_idx, 2], all_reldiff)

    path = os.path.join(output_dir, "merger_rate.pdf")
    save_figure(fig, path)
    return path


def _plot_angular_momentum(
    in_trees: dict, out_trees: dict, mass_bins: tuple, output_dir: str, style_path: str = "reference/sage_validation.mplstyle"
) -> str:
    """Plot 3 — Specific Angular Momentum |SubhaloSpin| (3×3)."""
    if os.path.isfile(style_path):
        plt.style.use(style_path)

    top, median, bottom = mass_bins
    bin_groups = [top, median, bottom]

    fig, axes = make_3x3_figure(
        col_titles=(
            "Input — |SubhaloSpin|",
            "Output — |SubhaloSpin|",
            "Relative difference",
        ),
    )

    for row_idx, tree_ids in enumerate(bin_groups):
        all_reldiff = []
        for tid in tree_ids:
            in_tree = in_trees[tid]
            out_tree = out_trees[tid]

            in_roots = _root_halos_at_snap(in_tree, max(in_tree["SnapNum"]))
            out_roots = _root_halos_at_snap(out_tree, max(out_tree["SnapNum"]))
            if len(in_roots) == 0 or len(out_roots) == 0:
                continue

            in_snaps, in_spins = _main_progenitor_spins(in_tree, int(in_roots[0]))
            out_snaps, out_spins = _main_progenitor_spins(out_tree, int(out_roots[0]))

            in_spins_pos = [s if s > 0 else np.nan for s in in_spins]
            out_spins_pos = [s if s > 0 else np.nan for s in out_spins]

            axes[row_idx, 0].semilogy(in_snaps, in_spins_pos, alpha=0.6, marker="o", markersize=3, label=f"Tree {tid}")
            axes[row_idx, 1].semilogy(out_snaps, out_spins_pos, alpha=0.6, marker="o", markersize=3)

            in_map = dict(zip(in_snaps, in_spins))
            common = sorted(set(in_snaps) & set(out_snaps))
            if common:
                in_s = np.array([in_map[s] for s in common])
                out_s = np.array([dict(zip(out_snaps, out_spins))[s] for s in common])
                rd = rel_diff(out_s, in_s)
                axes[row_idx, 2].plot(common, rd, alpha=0.6, marker="o", markersize=2)
                all_reldiff.extend(rd[np.isfinite(rd)].tolist())

        axes[row_idx, 0].legend(fontsize="x-small", loc="best")
        axes[row_idx, 0].set_xlabel("SnapNum")
        axes[row_idx, 0].set_ylabel("|SubhaloSpin| [(kpc/h)(km/s)]")
        axes[row_idx, 1].set_xlabel("SnapNum")
        axes[row_idx, 2].set_xlabel("SnapNum")
        axes[row_idx, 2].set_ylabel("(output - input) / input")
        add_reldiff_hline(axes[row_idx, 2])
        if all_reldiff:
            set_reldiff_ylim(axes[row_idx, 2], all_reldiff)

    path = os.path.join(output_dir, "angular_momentum.pdf")
    save_figure(fig, path)
    return path


# ---------------------------------------------------------------------------
# 1×3 distribution plots
# ---------------------------------------------------------------------------

def _collect_halos_at_snap(trees: dict, snap: int) -> dict[str, np.ndarray]:
    """Collect all halo-level arrays at the given snapshot across all trees.

    Returns dict of field_name → concatenated 1D (or 2D) array.
    Excludes halos with Group_M_Crit200 <= 0.
    """
    field_lists: dict[str, list] = {}
    for tree in trees.values():
        mask = (tree["SnapNum"] == snap) & (tree["Group_M_Crit200"] > 0)
        if not np.any(mask):
            continue
        for field, arr in tree.items():
            if field not in field_lists:
                field_lists[field] = []
            field_lists[field].append(arr[mask])

    return {
        field: np.concatenate(arrays, axis=0)
        for field, arrays in field_lists.items()
        if arrays
    }


def _plot_hmf(in_halos: dict, out_halos: dict, output_dir: str, style_path: str = "reference/sage_validation.mplstyle") -> str:
    """Plot 4 — Halo Mass Function (1×3)."""
    if os.path.isfile(style_path):
        plt.style.use(style_path)

    in_mass = np.log10(in_halos["Group_M_Crit200"])
    out_mass = np.log10(out_halos["Group_M_Crit200"])

    all_mass = np.concatenate([in_mass, out_mass])
    bins = np.linspace(np.nanmin(all_mass), np.nanmax(all_mass), 31)

    in_counts, _ = np.histogram(in_mass, bins=bins)
    out_counts, _ = np.histogram(out_mass, bins=bins)
    bin_centres = 0.5 * (bins[:-1] + bins[1:])

    fig, axes = make_1x3_figure(
        col_titles=("Input — HMF", "Output — HMF", "Relative difference"),
    )

    axes[0].semilogy(bin_centres, np.where(in_counts > 0, in_counts, np.nan), drawstyle="steps-mid")
    axes[1].semilogy(bin_centres, np.where(out_counts > 0, out_counts, np.nan), drawstyle="steps-mid")

    rd = rel_diff(out_counts.astype(float), in_counts.astype(float))
    axes[2].plot(bin_centres, rd, drawstyle="steps-mid")
    add_reldiff_hline(axes[2])
    set_reldiff_ylim(axes[2], rd)

    for ax in axes[:2]:
        ax.set_xlabel("log₁₀(Group_M_Crit200 [10¹⁰ M☉/h])")
        ax.set_ylabel("Count")
    axes[2].set_xlabel("log₁₀(Group_M_Crit200 [10¹⁰ M☉/h])")
    axes[2].set_ylabel("(output - input) / input")

    path = os.path.join(output_dir, "hmf.pdf")
    save_figure(fig, path)
    return path


def _plot_velocity_dist(in_halos: dict, out_halos: dict, output_dir: str, style_path: str = "reference/sage_validation.mplstyle") -> str:
    """Plot 5 — Velocity Distribution |SubhaloVel| (1×3)."""
    if os.path.isfile(style_path):
        plt.style.use(style_path)

    # PROHIBITION ENFORCED: using SubhaloVel, NOT SubhaloVMax
    in_vel_mag = np.linalg.norm(in_halos["SubhaloVel"], axis=1)
    out_vel_mag = np.linalg.norm(out_halos["SubhaloVel"], axis=1)

    v_max = max(np.nanmax(in_vel_mag), np.nanmax(out_vel_mag))
    bins = np.linspace(0, v_max, 31)

    in_counts, _ = np.histogram(in_vel_mag, bins=bins)
    out_counts, _ = np.histogram(out_vel_mag, bins=bins)
    bin_centres = 0.5 * (bins[:-1] + bins[1:])

    fig, axes = make_1x3_figure(
        col_titles=(
            "Input — |SubhaloVel|",
            "Output — |SubhaloVel|",
            "Relative difference",
        ),
    )

    axes[0].plot(bin_centres, in_counts, drawstyle="steps-mid")
    axes[1].plot(bin_centres, out_counts, drawstyle="steps-mid")

    rd = rel_diff(out_counts.astype(float), in_counts.astype(float))
    axes[2].plot(bin_centres, rd, drawstyle="steps-mid")
    add_reldiff_hline(axes[2])
    set_reldiff_ylim(axes[2], rd)

    for ax in axes[:2]:
        ax.set_xlabel("|SubhaloVel| [km/s]")
        ax.set_ylabel("Count")
    axes[2].set_xlabel("|SubhaloVel| [km/s]")
    axes[2].set_ylabel("(output - input) / input")

    path = os.path.join(output_dir, "velocity_dist.pdf")
    save_figure(fig, path)
    return path


def _plot_lifespan(in_trees: dict, out_trees: dict, output_dir: str, style_path: str = "reference/sage_validation.mplstyle") -> str:
    """Plot 6 — Lifespan Distribution (1×3)."""
    if os.path.isfile(style_path):
        plt.style.use(style_path)

    def _compute_lifespans(trees: dict, lowest_snap: int) -> list[int]:
        lifespans = []
        for tree in trees.values():
            roots = _root_halos_at_snap(tree, lowest_snap)
            for r in roots:
                lifespans.append(_lifespan(tree, int(r)))
        return lifespans

    in_lowest = _find_lowest_snap(in_trees)
    out_lowest = _find_lowest_snap(out_trees)

    in_lifespans = _compute_lifespans(in_trees, in_lowest)
    out_lifespans = _compute_lifespans(out_trees, out_lowest)

    if not in_lifespans or not out_lifespans:
        fig, axes = make_1x3_figure()
        for ax in axes:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        path = os.path.join(output_dir, "lifespan_dist.pdf")
        save_figure(fig, path)
        return path

    max_life = max(max(in_lifespans), max(out_lifespans))
    bins = np.arange(0.5, max_life + 1.5, 1)

    in_counts, _ = np.histogram(in_lifespans, bins=bins)
    out_counts, _ = np.histogram(out_lifespans, bins=bins)
    bin_centres = np.arange(1, max_life + 1)

    fig, axes = make_1x3_figure(
        col_titles=("Input — Lifespan", "Output — Lifespan", "Relative difference"),
    )

    axes[0].bar(bin_centres, in_counts, width=0.8, align="center")
    axes[1].bar(bin_centres, out_counts, width=0.8, align="center")

    rd = rel_diff(out_counts.astype(float), in_counts.astype(float))
    axes[2].plot(bin_centres, rd, drawstyle="steps-mid")
    add_reldiff_hline(axes[2])
    set_reldiff_ylim(axes[2], rd)

    for ax in axes[:2]:
        ax.set_xlabel("Snapshots tracked (lifespan)")
        ax.set_ylabel("Count")
    axes[2].set_xlabel("Snapshots tracked (lifespan)")
    axes[2].set_ylabel("(output - input) / input")

    path = os.path.join(output_dir, "lifespan_dist.pdf")
    save_figure(fig, path)
    return path


def _plot_spatial(in_halos: dict, out_halos: dict, output_dir: str, style_path: str = "reference/sage_validation.mplstyle") -> str:
    """Plot 7 — Spatial Distribution X–Y hexbin (1×3)."""
    if os.path.isfile(style_path):
        plt.style.use(style_path)

    in_x, in_y = in_halos["SubhaloPos"][:, 0], in_halos["SubhaloPos"][:, 1]
    out_x, out_y = out_halos["SubhaloPos"][:, 0], out_halos["SubhaloPos"][:, 1]

    fig, axes = make_1x3_figure(
        col_titles=("Input — Spatial", "Output — Spatial", "Relative difference"),
    )

    axes[0].hexbin(in_x, in_y, gridsize=50, mincnt=1, cmap="viridis")
    axes[1].hexbin(out_x, out_y, gridsize=50, mincnt=1, cmap="viridis")

    # Relative difference of hexbin counts: align on same grid
    all_x = np.concatenate([in_x, out_x])
    all_y = np.concatenate([in_y, out_y])
    x_min, x_max = float(np.nanmin(all_x)), float(np.nanmax(all_x))
    y_min, y_max = float(np.nanmin(all_y)), float(np.nanmax(all_y))

    gridsize = 50
    x_edges = np.linspace(x_min, x_max, gridsize + 1)
    y_edges = np.linspace(y_min, y_max, gridsize + 1)

    in_hist, _, _ = np.histogram2d(in_x, in_y, bins=[x_edges, y_edges])
    out_hist, _, _ = np.histogram2d(out_x, out_y, bins=[x_edges, y_edges])

    rd_grid = rel_diff(out_hist, in_hist)
    rd_flat = rd_grid[np.isfinite(rd_grid)]
    vmax = float(np.nanmax(np.abs(rd_flat))) if rd_flat.size > 0 else 1.0

    xc = 0.5 * (x_edges[:-1] + x_edges[1:])
    yc = 0.5 * (y_edges[:-1] + y_edges[1:])
    Xc, Yc = np.meshgrid(xc, yc, indexing="ij")
    im = axes[2].pcolormesh(Xc, Yc, rd_grid.T, cmap="RdBu_r", vmin=-vmax, vmax=vmax)
    plt.colorbar(im, ax=axes[2], label="(output - input) / input")

    for ax in axes[:2]:
        ax.set_xlabel("Pos X [kpc/h]")
        ax.set_ylabel("Pos Y [kpc/h]")
    axes[2].set_xlabel("Pos X [kpc/h]")
    axes[2].set_ylabel("Pos Y [kpc/h]")

    path = os.path.join(output_dir, "spatial_dist.pdf")
    save_figure(fig, path)
    return path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_all_plots(
    input_path: str,
    output_path: str,
    output_dir: str = "assets/semantic_validation",
    style_path: str = "reference/sage_validation.mplstyle",
    input_format: str = "lhalo_hdf5",
    output_format: str = "lhalo_hdf5",
) -> list[str]:
    """Generate all seven mandatory semantic validation plots.

    Parameters
    ----------
    input_path : str
        Path to the reference (unconverted) merger tree file.
        This is the INPUT column data — never use output_path for the input column.
    output_path : str
        Path to the converted SAGE LHaloTree output file.
    output_dir : str
        Directory where plots are saved. Created if it does not exist.
    style_path : str
        Path to the Matplotlib style sheet (reference/sage_validation.mplstyle).
    input_format : str
        Format of input_path. Use 'lhalo_hdf5' (default) for SAGE LHaloTree HDF5,
        'lhalo_binary' for SAGE LHaloTree binary, or a driver format ID (e.g.
        'ahf_mergetree_ascii', 'rockstar_consistent_trees_ascii') to load the
        original source data directly via the driver's read_trees() function.
    output_format : str
        'lhalo_hdf5' (default) or 'lhalo_binary'. Format of output_path.

    Returns
    -------
    list[str]
        Paths of all saved plot files (7 items).
    """
    # PROHIBITION ENFORCED: input_path → input column; output_path → output column.
    if os.path.abspath(input_path) == os.path.abspath(output_path):
        raise ValueError(
            "input_path and output_path point to the same file. "
            "The input column must use the unconverted file."
        )

    if os.path.isfile(style_path):
        plt.style.use(style_path)
    else:
        import warnings
        warnings.warn(f"Style file not found at '{style_path}'. Using matplotlib defaults.")

    os.makedirs(output_dir, exist_ok=True)

    print(f"Loading input trees from:  {input_path}")
    if input_format == "lhalo_hdf5":
        in_trees = _load_trees(input_path)
    elif input_format == "lhalo_binary":
        in_trees = _load_binary_trees(input_path)
    else:
        in_trees = _load_native_trees(input_format, input_path)
    print(f"Loading output trees from: {output_path}")
    out_trees = _load_trees(output_path) if output_format == "lhalo_hdf5" else _load_binary_trees(output_path)

    if not in_trees:
        raise ValueError(f"No trees found in input file: {input_path}")
    if not out_trees:
        raise ValueError(f"No trees found in output file: {output_path}")

    # Use the same tree IDs for both columns (PROHIBITION ENFORCED).
    shared_ids = sorted(set(in_trees) & set(out_trees))
    if not shared_ids:
        raise ValueError(
            "No common tree indices between input and output files. "
            "Cannot generate comparison plots."
        )
    in_trees_shared = {i: in_trees[i] for i in shared_ids}
    out_trees_shared = {i: out_trees[i] for i in shared_ids}

    lowest_snap = _find_lowest_snap(in_trees_shared)
    print(f"Lowest-redshift snapshot: {lowest_snap}")

    mass_bins = _select_mass_bins(in_trees_shared, lowest_snap)
    print(
        f"Mass bins — top: {len(mass_bins[0])}, "
        f"median: {len(mass_bins[1])}, "
        f"bottom: {len(mass_bins[2])} trees"
    )

    # Collect halos at lowest-redshift snapshot (PROHIBITION: same sample for both columns)
    in_halos_lo = _collect_halos_at_snap(in_trees_shared, lowest_snap)
    out_halos_lo = _collect_halos_at_snap(out_trees_shared, lowest_snap)

    saved = []
    print("\nGenerating plots …")

    saved.append(_plot_mah(in_trees_shared, out_trees_shared, mass_bins, output_dir))
    saved.append(_plot_merger_rate(in_trees_shared, out_trees_shared, mass_bins, output_dir))
    saved.append(_plot_angular_momentum(in_trees_shared, out_trees_shared, mass_bins, output_dir))
    saved.append(_plot_hmf(in_halos_lo, out_halos_lo, output_dir))
    saved.append(_plot_velocity_dist(in_halos_lo, out_halos_lo, output_dir))  # uses SubhaloVel, NOT SubhaloVMax
    saved.append(_plot_lifespan(in_trees_shared, out_trees_shared, output_dir))
    saved.append(_plot_spatial(in_halos_lo, out_halos_lo, output_dir))

    print(f"\nAll {len(saved)} plots saved to: {output_dir}")
    return saved
