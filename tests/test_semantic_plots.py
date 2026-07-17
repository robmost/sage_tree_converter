"""Invariants for the semantic validation plotting code (validation.semantic).

These tests carry the code-structure items that used to live in the Stage 3
auditor checklist. The plotting code is static engine code, so its structural
guarantees belong here, where they run deterministically on every test run;
the session auditor inspects the rendered plots, not this code.
"""

import ast
import inspect
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import h5py
import numpy as np
import pytest

from validation import plot_utils, semantic

SEMANTIC_SOURCE = Path(inspect.getsourcefile(semantic)).read_text()
PLOT_UTILS_SOURCE = Path(inspect.getsourcefile(plot_utils)).read_text()

EXPECTED_PLOTS = {
    "mah.pdf",
    "merger_rate.pdf",
    "angular_momentum.pdf",
    "hmf.pdf",
    "velocity_dist.pdf",
    "lifespan_dist.pdf",
    "spatial_dist.pdf",
}


def _function_source(module_source: str, name: str) -> str:
    tree = ast.parse(module_source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(module_source, node)
    raise AssertionError(f"function {name!r} not found")


def _plot_function_names() -> list[str]:
    tree = ast.parse(SEMANTIC_SOURCE)
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("_plot_")
    ]


# ---------------------------------------------------------------------------
# Code-structure invariants (former auditor checklist items 1, 3, 4, 5, 8, 9)
# ---------------------------------------------------------------------------


def test_no_direct_savefig_or_close_in_semantic():
    # All saving/closing must go through plot_utils.save_figure(). AST-based so
    # that docstrings and comments mentioning the calls do not trip the check.
    # Any .savefig() call is a violation; for close() only plt.close() is,
    # so closing file handles or other resources stays allowed.
    offenders = []
    for node in ast.walk(ast.parse(SEMANTIC_SOURCE)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr == "savefig":
            offenders.append("savefig")
        elif (
            node.func.attr == "close"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "plt"
        ):
            offenders.append("plt.close")
    assert offenders == []


def test_save_figure_is_the_only_saver():
    seg = _function_source(PLOT_UTILS_SOURCE, "save_figure")
    assert "fig.savefig(" in seg
    assert "plt.close(fig)" in seg


def test_each_plot_function_applies_style_before_creating_its_figure():
    for name in _plot_function_names():
        seg = _function_source(SEMANTIC_SOURCE, name)
        style_pos = seg.find("plt.style.use")
        fig_pos = max(seg.find("make_mass_bin_figure"), seg.find("make_single_figure"))
        assert style_pos != -1, f"{name} never applies the style sheet"
        assert fig_pos != -1, f"{name} creates no figure via plot_utils"
        assert style_pos < fig_pos, f"{name} creates its figure before applying the style"


def test_velocity_dist_uses_vel_modulus_not_vmax():
    seg = _function_source(SEMANTIC_SOURCE, "_plot_velocity_dist")
    assert "SubhaloVMax" not in seg
    assert "SubhaloVel" in seg
    assert "norm" in seg


def test_mah_branch_walk_uses_group_m_crit200():
    seg = _function_source(SEMANTIC_SOURCE, "_main_progenitor_branch")
    assert "Group_M_Crit200" in seg
    assert "M_Mean200" not in seg
    assert "M_TopHat" not in seg


def test_angular_momentum_uses_spin_vector_magnitude():
    seg = _function_source(SEMANTIC_SOURCE, "_main_progenitor_spins")
    assert "SubhaloSpin" in seg
    assert "norm" in seg


def test_progenitor_walks_use_linked_list_pattern():
    # Former checklist item 7 (O(N) traversal): every branch walker follows the
    # FirstProgenitor linked list in a while loop, never a scan over all halos.
    for name in ("_main_progenitor_branch", "_main_progenitor_spins", "_lifespan"):
        seg = _function_source(SEMANTIC_SOURCE, name)
        assert "while h != -1" in seg, f"{name} does not walk the FirstProgenitor chain"
        assert "FirstProgenitor" in seg


# ---------------------------------------------------------------------------
# Behavioural invariants (former checklist item 2 and prohibition 7)
# ---------------------------------------------------------------------------


def _chain_tree(mass_scale: float) -> dict[str, np.ndarray]:
    """Three-halo main-branch chain: snap 2 root <- snap 1 <- snap 0."""
    n = 3
    return {
        "SnapNum": np.array([2, 1, 0], dtype=np.int32),
        "Descendant": np.array([-1, 0, 1], dtype=np.int32),
        "FirstProgenitor": np.array([1, 2, -1], dtype=np.int32),
        "NextProgenitor": np.full(n, -1, dtype=np.int32),
        "Group_M_Crit200": (mass_scale * np.array([3.0, 2.0, 1.0])).astype(np.float32),
        "SubhaloVel": np.full((n, 3), 100.0, dtype=np.float32),
        "SubhaloSpin": np.full((n, 3), 50.0, dtype=np.float32),
        "SubhaloPos": (np.arange(n * 3, dtype=np.float32).reshape(n, 3) * 100.0),
    }


def test_select_mass_bins_excludes_nonpositive_root_masses():
    trees = {0: _chain_tree(5.0), 1: _chain_tree(1.0), 2: _chain_tree(2.0)}
    trees[1]["Group_M_Crit200"][:] = 0.0
    top, median, bottom = semantic._select_mass_bins(trees, lowest_snap=2)
    selected = set(top) | set(median) | set(bottom)
    assert 1 not in selected
    assert selected == {0, 2}


def test_heaviest_root_is_selected_not_first():
    tree = _chain_tree(1.0)
    # Two roots at snap 2; the second is the massive one.
    tree["SnapNum"] = np.array([2, 2, 0], dtype=np.int32)
    tree["Descendant"] = np.array([-1, -1, 1], dtype=np.int32)
    tree["Group_M_Crit200"] = np.array([1.0, 9.0, 0.5], dtype=np.float32)
    roots = semantic._root_halos_at_snap(tree, 2)
    assert list(roots) == [0, 1]
    assert semantic._heaviest_root(tree, roots) == 1


def test_main_progenitor_branch_walks_the_chain():
    tree = _chain_tree(1.0)
    snaps, masses = semantic._main_progenitor_branch(tree, 0)
    assert snaps == [2, 1, 0]
    assert masses == [3.0, 2.0, 1.0]


# ---------------------------------------------------------------------------
# End-to-end: all seven plots (plus PNG siblings) are produced
# ---------------------------------------------------------------------------


@pytest.fixture
def tiny_hdf5(tmp_path):
    path = tmp_path / "tiny_STC.0.hdf5"
    with h5py.File(path, "w") as f:
        for idx in range(6):
            grp = f.create_group(f"Tree{idx}")
            for field, arr in _chain_tree(float(idx + 1)).items():
                grp.create_dataset(field, data=arr)
    return str(path)


def test_generate_all_plots_writes_seven_plots_with_png_siblings(tiny_hdf5, tmp_path):
    out_dir = tmp_path / "plots"
    style = Path(__file__).resolve().parents[1] / "reference" / "sage_validation.mplstyle"
    saved = semantic.generate_all_plots(
        output_path=tiny_hdf5,
        output_dir=str(out_dir),
        style_path=str(style),
    )
    assert {Path(p).name for p in saved} == EXPECTED_PLOTS
    for name in EXPECTED_PLOTS:
        pdf = out_dir / name
        png = pdf.with_suffix(".png")
        assert pdf.is_file() and pdf.stat().st_size > 0
        assert png.is_file() and png.stat().st_size > 0
