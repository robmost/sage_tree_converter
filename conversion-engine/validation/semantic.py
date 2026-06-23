"""
semantic.py - Seven semantic validation plots for SAGE merger tree conversion.

Renders seven physical-plausibility diagnostics of the CONVERTED output file -
absolute distributions, with no input/output comparison column. All plots use
reference/sage_validation.mplstyle and are saved to assets/semantic_validation/.

These plots show whether the converted trees are physically sensible (mass
accretion histories, mass/velocity/spin distributions, spatial layout). They are
deliberately NOT a differential test of the conversion logic: a converter cannot
be validated against itself, because the only independent reference would be a
second, separately-derived conversion. Conversion-logic correctness is instead
established by the G1 schema-mapping review, syntactic validation, and functional
(SAGE dry-run) validation.

Usage:
    from validation.semantic import generate_all_plots
    saved = generate_all_plots(output_path="output/converted.0.hdf5")

Invariants (enforced in code):
  - Velocity distribution plots always use |SubhaloVel|, never SubhaloVMax.
  - Figures are always saved via save_figure(), not plt.savefig()/plt.close() directly.
"""

import os
import struct as _struct
import warnings

import h5py
import matplotlib.pyplot as plt
import numpy as np

from utils.schema import HALO_RECORD_DTYPE as _BINARY_HALO_DTYPE

from .plot_utils import (
    make_mass_bin_figure,
    make_single_figure,
    save_figure,
)

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------


def _load_trees(hdf5_path: str) -> dict[int, dict[str, np.ndarray]]:
    """Load all trees from an HDF5 file into memory.

    Returns
    -------
    dict mapping tree_idx (int) -> dict of field_name -> numpy array.
    """
    trees: dict[int, dict[str, np.ndarray]] = {}
    with h5py.File(hdf5_path, "r") as f:
        for key in f.keys():
            if not key.startswith("Tree"):
                continue
            idx = int(key[4:])
            grp: h5py.Group = f[key]  # type: ignore[assignment]
            trees[idx] = {
                field: np.asarray(grp[field])  # type: ignore[arg-type]
                for field in grp.keys()
            }
    return trees


def _load_binary_trees(binary_path: str) -> dict[int, dict[str, np.ndarray]]:
    """Load all trees from a SAGE LHaloTree binary file.

    Normalises SubhaloPos (Mpc/h -> kpc/h, x1000) and SubhaloSpin
    ((Mpc/h)(km/s) -> (kpc/h)(km/s), x1000) to match the HDF5 on-disk convention
    so plotted units are consistent regardless of output format.
    """
    trees: dict[int, dict[str, np.ndarray]] = {}
    with open(binary_path, "rb") as fp:
        nforests = _struct.unpack("<i", fp.read(4))[0]
        _totnhalos = _struct.unpack("<i", fp.read(4))[0]
        nhalos_per_forest = np.frombuffer(fp.read(nforests * 4), dtype=np.int32).copy()
        for idx in range(nforests):
            n = int(nhalos_per_forest[idx])
            # n == 0 reads b"", so np.frombuffer yields empty arrays and the tree
            # dict keeps the full schema (matching the HDF5 loader).
            raw = fp.read(n * _BINARY_HALO_DTYPE.itemsize)
            halos = np.frombuffer(raw, dtype=_BINARY_HALO_DTYPE).copy()
            trees[idx] = {
                "Descendant": halos["Descendant"],
                "FirstProgenitor": halos["FirstProgenitor"],
                "NextProgenitor": halos["NextProgenitor"],
                "FirstHaloInFOFGroup": halos["FirstHaloInFOFGroup"],
                "NextHaloInFOFGroup": halos["NextHaloInFOFGroup"],
                "SubhaloLen": halos["Len"],
                "Group_M_Crit200": halos["M_Crit200"],
                "Group_M_Mean200": halos["M_Mean200"],
                "Group_M_TopHat200": halos["M_TopHat"],
                "SubhaloPos": (halos["Pos"] * np.float32(1000.0)).astype(np.float32),
                "SubhaloVel": halos["Vel"],
                "SubhaloVelDisp": halos["VelDisp"],
                "SubhaloVMax": halos["Vmax"],
                "SubhaloSpin": (halos["Spin"] * np.float32(1000.0)).astype(np.float32),
                "SubhaloIDMostBound": halos["MostBoundID"],
                "SnapNum": halos["SnapNum"],
                "FileNr": halos["FileNr"],
            }
    return trees


# ---------------------------------------------------------------------------
# Tree-walking and selection helpers
# ---------------------------------------------------------------------------


def _find_lowest_snap(trees: dict) -> int:
    """Return the snapshot index of the lowest-redshift snapshot (highest SnapNum)."""
    return max(int(np.max(t["SnapNum"])) for t in trees.values() if len(t["SnapNum"]) > 0)


def _root_halos_at_snap(tree: dict, snap: int) -> np.ndarray:
    """Return indices of halos at snapshot snap whose Descendant is -1 (roots)."""
    snap_arr = tree["SnapNum"]
    desc_arr = tree["Descendant"]
    mask = (snap_arr == snap) & (desc_arr == -1)
    return np.where(mask)[0]


def _heaviest_root(tree: dict, roots: np.ndarray) -> int:
    """Return the flat index of the most massive root halo."""
    return int(roots[np.argmax(tree["Group_M_Crit200"][roots])])


def _select_mass_bins(trees: dict, lowest_snap: int) -> tuple[list[int], list[int], list[int]]:
    """Select top-5, median-5, and bottom-5 tree indices by root-halo mass.

    Trees with no root halo at lowest_snap, or with Group_M_Crit200 <= 0, are excluded.
    Returns three lists of tree_idx values (may be shorter than 5 if too few trees).
    """
    root_masses = {}
    for idx, tree in trees.items():
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
    bottom = sorted_ids[max(0, n - k) :]
    mid_start = max(0, n // 2 - k // 2)
    median = sorted_ids[mid_start : mid_start + k]

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

    Build a descendant->count map in one pass over all halos in the tree.
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
# Per-mass-bin evolution plots (3x1: one row per Top/Median/Bottom-5 group)
# ---------------------------------------------------------------------------


def _plot_mah(
    out_trees: dict,
    mass_bins: tuple,
    output_dir: str,
    style_path: str = "reference/sage_validation.mplstyle",
) -> str:
    """Plot 1 - Mass Accretion History (3x1, output only)."""
    if os.path.isfile(style_path):
        plt.style.use(style_path)

    bin_groups = list(mass_bins)  # top, median, bottom

    fig, axes = make_mass_bin_figure()

    for row_idx, tree_ids in enumerate(bin_groups):
        ax = axes[row_idx]
        for tid in tree_ids:
            out_tree = out_trees[tid]
            out_roots = _root_halos_at_snap(out_tree, max(out_tree["SnapNum"]))
            if len(out_roots) == 0:
                continue
            out_snaps, out_masses = _main_progenitor_branch(
                out_tree, _heaviest_root(out_tree, out_roots)
            )
            out_masses_pos = [m if m > 0 else np.nan for m in out_masses]
            ax.semilogy(
                out_snaps, out_masses_pos, alpha=0.6, marker="o", markersize=3, label=f"Tree {tid}"
            )

        ax.legend(fontsize="x-small", loc="best")
        ax.set_xlabel("SnapNum")
        ax.set_ylabel("Group_M_Crit200 [10^10 Msun/h]")

    path = os.path.join(output_dir, "mah.pdf")
    save_figure(fig, path)
    return path


def _plot_merger_rate(
    out_trees: dict,
    mass_bins: tuple,
    output_dir: str,
    style_path: str = "reference/sage_validation.mplstyle",
) -> str:
    """Plot 2 - Merger Rate (3x1, output only)."""
    if os.path.isfile(style_path):
        plt.style.use(style_path)

    bin_groups = list(mass_bins)

    fig, axes = make_mass_bin_figure()

    for row_idx, tree_ids in enumerate(bin_groups):
        ax = axes[row_idx]
        for tid in tree_ids:
            out_tree = out_trees[tid]
            out_roots = _root_halos_at_snap(out_tree, max(out_tree["SnapNum"]))
            if len(out_roots) == 0:
                continue
            out_rate = _merger_rate_along_branch(out_tree, _heaviest_root(out_tree, out_roots))
            out_snaps = sorted(out_rate)
            ax.plot(
                out_snaps,
                [out_rate[s] for s in out_snaps],
                alpha=0.6,
                marker="o",
                markersize=3,
                label=f"Tree {tid}",
            )

        ax.legend(fontsize="x-small", loc="best")
        ax.set_xlabel("SnapNum")
        ax.set_ylabel("Number of progenitors")

    path = os.path.join(output_dir, "merger_rate.pdf")
    save_figure(fig, path)
    return path


def _plot_angular_momentum(
    out_trees: dict,
    mass_bins: tuple,
    output_dir: str,
    style_path: str = "reference/sage_validation.mplstyle",
) -> str:
    """Plot 3 - Specific Angular Momentum |SubhaloSpin| (3x1, output only)."""
    if os.path.isfile(style_path):
        plt.style.use(style_path)

    bin_groups = list(mass_bins)

    fig, axes = make_mass_bin_figure()

    for row_idx, tree_ids in enumerate(bin_groups):
        ax = axes[row_idx]
        for tid in tree_ids:
            out_tree = out_trees[tid]
            out_roots = _root_halos_at_snap(out_tree, max(out_tree["SnapNum"]))
            if len(out_roots) == 0:
                continue
            out_snaps, out_spins = _main_progenitor_spins(
                out_tree, _heaviest_root(out_tree, out_roots)
            )
            out_spins_pos = [s if s > 0 else np.nan for s in out_spins]
            ax.semilogy(
                out_snaps, out_spins_pos, alpha=0.6, marker="o", markersize=3, label=f"Tree {tid}"
            )

        ax.legend(fontsize="x-small", loc="best")
        ax.set_xlabel("SnapNum")
        ax.set_ylabel("|SubhaloSpin| [(kpc/h)(km/s)]")

    path = os.path.join(output_dir, "angular_momentum.pdf")
    save_figure(fig, path)
    return path


# ---------------------------------------------------------------------------
# Distribution plots (single panel, output only)
# ---------------------------------------------------------------------------


def _collect_halos_at_snap(trees: dict, snap: int) -> dict[str, np.ndarray]:
    """Collect all halo-level arrays at the given snapshot across all trees.

    Returns dict of field_name -> concatenated 1D (or 2D) array.
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
        field: np.concatenate(arrays, axis=0) for field, arrays in field_lists.items() if arrays
    }


def _plot_hmf(
    out_halos: dict,
    output_dir: str,
    style_path: str = "reference/sage_validation.mplstyle",
) -> str:
    """Plot 4 - Halo Mass Function (output only)."""
    if os.path.isfile(style_path):
        plt.style.use(style_path)

    out_mass = np.log10(out_halos["Group_M_Crit200"])
    bins = np.linspace(np.nanmin(out_mass), np.nanmax(out_mass), 31)
    out_counts, _ = np.histogram(out_mass, bins=bins)
    bin_centres = 0.5 * (bins[:-1] + bins[1:])

    fig, ax = make_single_figure("Output - HMF")
    ax.semilogy(bin_centres, np.where(out_counts > 0, out_counts, np.nan), drawstyle="steps-mid")
    ax.set_xlabel("log10(Group_M_Crit200 [10^10 Msun/h])")
    ax.set_ylabel("Count")

    path = os.path.join(output_dir, "hmf.pdf")
    save_figure(fig, path)
    return path


def _plot_velocity_dist(
    out_halos: dict,
    output_dir: str,
    style_path: str = "reference/sage_validation.mplstyle",
) -> str:
    """Plot 5 - Velocity Distribution |SubhaloVel| (output only)."""
    if os.path.isfile(style_path):
        plt.style.use(style_path)

    out_vel_mag = np.linalg.norm(out_halos["SubhaloVel"], axis=1)
    bins = np.linspace(0, np.nanmax(out_vel_mag), 31)
    out_counts, _ = np.histogram(out_vel_mag, bins=bins)
    bin_centres = 0.5 * (bins[:-1] + bins[1:])

    fig, ax = make_single_figure("Output - |SubhaloVel|")
    ax.plot(bin_centres, out_counts, drawstyle="steps-mid")
    ax.set_xlabel("|SubhaloVel| [km/s]")
    ax.set_ylabel("Count")

    path = os.path.join(output_dir, "velocity_dist.pdf")
    save_figure(fig, path)
    return path


def _plot_lifespan(
    out_trees: dict,
    output_dir: str,
    style_path: str = "reference/sage_validation.mplstyle",
) -> str:
    """Plot 6 - Lifespan Distribution (output only)."""
    if os.path.isfile(style_path):
        plt.style.use(style_path)

    def _compute_lifespans(trees: dict, lowest_snap: int) -> list[int]:
        lifespans = []
        for tree in trees.values():
            roots = _root_halos_at_snap(tree, lowest_snap)
            for r in roots:
                lifespans.append(_lifespan(tree, int(r)))
        return lifespans

    out_lowest = _find_lowest_snap(out_trees)
    out_lifespans = _compute_lifespans(out_trees, out_lowest)

    if not out_lifespans:
        fig, ax = make_single_figure("Output - Lifespan")
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        path = os.path.join(output_dir, "lifespan_dist.pdf")
        save_figure(fig, path)
        return path

    max_life = max(out_lifespans)
    bins = np.arange(0.5, max_life + 1.5, 1)
    out_counts, _ = np.histogram(out_lifespans, bins=bins)
    bin_centres = np.arange(1, max_life + 1)

    fig, ax = make_single_figure("Output - Lifespan")
    ax.bar(bin_centres, out_counts, width=0.8, align="center")
    ax.set_xlabel("Snapshots tracked (lifespan)")
    ax.set_ylabel("Count")

    path = os.path.join(output_dir, "lifespan_dist.pdf")
    save_figure(fig, path)
    return path


def _plot_spatial(
    out_halos: dict,
    output_dir: str,
    style_path: str = "reference/sage_validation.mplstyle",
) -> str:
    """Plot 7 - Spatial Distribution X-Y hexbin (output only)."""
    if os.path.isfile(style_path):
        plt.style.use(style_path)

    out_x, out_y = out_halos["SubhaloPos"][:, 0], out_halos["SubhaloPos"][:, 1]

    fig, ax = make_single_figure("Output - Spatial")
    hb = ax.hexbin(out_x, out_y, gridsize=50, mincnt=1, cmap="viridis")
    plt.colorbar(hb, ax=ax, label="Count")
    ax.set_xlabel("Pos X [kpc/h]")
    ax.set_ylabel("Pos Y [kpc/h]")

    path = os.path.join(output_dir, "spatial_dist.pdf")
    save_figure(fig, path)
    return path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_all_plots(
    output_path: str,
    output_dir: str = "assets/semantic_validation",
    style_path: str = "reference/sage_validation.mplstyle",
    output_format: str = "lhalo_hdf5",
) -> list[str]:
    """Generate the seven semantic validation plots from the converted output file.

    Output-only physical-plausibility plots (no input/output comparison column).
    See the module docstring for why this is not a differential test of the
    conversion logic.

    Parameters
    ----------
    output_path : str
        Path to the converted SAGE LHaloTree output file.
    output_dir : str
        Directory where plots are saved. Created if it does not exist.
    style_path : str
        Path to the Matplotlib style sheet (reference/sage_validation.mplstyle).
    output_format : str
        'lhalo_hdf5' (default) or 'lhalo_binary'. Format of output_path.

    Returns
    -------
    list[str]
        Paths of all saved plot files (7 items).
    """
    if os.path.isfile(style_path):
        plt.style.use(style_path)
    else:
        warnings.warn(f"Style file not found at '{style_path}'. Using matplotlib defaults.")

    os.makedirs(output_dir, exist_ok=True)

    print(f"Loading output trees from: {output_path}")
    out_trees = (
        _load_trees(output_path)
        if output_format == "lhalo_hdf5"
        else _load_binary_trees(output_path)
    )
    if not out_trees:
        raise ValueError(f"No trees found in output file: {output_path}")

    lowest_snap = _find_lowest_snap(out_trees)
    print(f"Lowest-redshift snapshot: {lowest_snap}")

    mass_bins = _select_mass_bins(out_trees, lowest_snap)
    print(
        f"Mass bins - top: {len(mass_bins[0])}, "
        f"median: {len(mass_bins[1])}, "
        f"bottom: {len(mass_bins[2])} trees"
    )

    # Collect halos at the lowest-redshift snapshot for the distribution plots.
    halos_lo = _collect_halos_at_snap(out_trees, lowest_snap)

    saved = []
    print("\nGenerating plots ...")

    saved.append(_plot_mah(out_trees, mass_bins, output_dir))
    saved.append(_plot_merger_rate(out_trees, mass_bins, output_dir))
    saved.append(_plot_angular_momentum(out_trees, mass_bins, output_dir))
    saved.append(_plot_hmf(halos_lo, output_dir))
    saved.append(_plot_velocity_dist(halos_lo, output_dir))  # uses SubhaloVel, NOT SubhaloVMax
    saved.append(_plot_lifespan(out_trees, output_dir))
    saved.append(_plot_spatial(halos_lo, output_dir))

    print(f"\nAll {len(saved)} plots saved to: {output_dir}")
    return saved
