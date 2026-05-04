"""
plot_utils.py — Shared plotting utilities for SAGE semantic validation.

All figure saving and closing must go through save_figure(). Do not call
plt.savefig() or plt.close() directly in any plotting code.
"""

import os

import matplotlib.pyplot as plt
import numpy as np


def save_figure(fig, output_path: str, dpi: int = 150) -> None:
    """Save a matplotlib figure to output_path and close it.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure to save.
    output_path : str
        Full path for the output file (e.g. 'assets/semantic_validation/mah.pdf').
    dpi : int
        Resolution in dots per inch. Default 150.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def make_3x3_figure(
    row_labels=("Top 5", "Median 5", "Bottom 5"),
    col_titles=("Input", "Output", "Relative difference"),
    figsize=(12, 10),
):
    """Create a 3×3 figure with labelled columns and row labels on column 1.

    Returns
    -------
    fig : matplotlib.figure.Figure
    axes : ndarray of shape (3, 3)
    """
    fig, axes = plt.subplots(3, 3, figsize=figsize)
    for col_idx, title in enumerate(col_titles):
        axes[0, col_idx].set_title(title)
    for row_idx, label in enumerate(row_labels):
        axes[row_idx, 0].set_ylabel(label, labelpad=10)
    return fig, axes


def make_1x3_figure(col_titles=("Input", "Output", "Relative difference")):
    """Create a 1×3 figure with labelled columns.

    Returns
    -------
    fig : matplotlib.figure.Figure
    axes : ndarray of shape (3,)
    """
    fig, axes = plt.subplots(1, 3)
    for ax, title in zip(axes, col_titles):
        ax.set_title(title)
    return fig, axes


def add_reldiff_hline(ax) -> None:
    """Add a horizontal dashed line at y=0 to a relative difference panel."""
    ax.axhline(0, color="black", linestyle="--", linewidth=0.8, zorder=0)


def set_reldiff_ylim(ax, rel_diff_array) -> None:
    """Set symmetric y limits on a relative difference panel.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
    rel_diff_array : array-like
        Array of relative difference values (may contain NaN).
    """
    arr = np.asarray(rel_diff_array, dtype=float)
    abs_max = np.nanmax(np.abs(arr)) if np.any(np.isfinite(arr)) else 0.0
    if abs_max == 0 or np.isnan(abs_max):
        abs_max = 0.1
    ax.set_ylim(-abs_max * 1.1, abs_max * 1.1)


def rel_diff(output, input_, fill_nan_where_zero=True):
    """Compute (output - input) / input element-wise.

    Where input == 0, the result is NaN.

    Parameters
    ----------
    output, input_ : array-like
    fill_nan_where_zero : bool
        If True (default), replace positions where input == 0 with NaN.

    Returns
    -------
    numpy.ndarray
    """
    output = np.asarray(output, dtype=float)
    input_ = np.asarray(input_, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(input_ != 0, (output - input_) / input_, np.nan)
    return result
