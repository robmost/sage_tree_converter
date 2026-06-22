"""
plot_utils.py - Shared plotting utilities for SAGE semantic validation.

All figure saving and closing must go through save_figure(). Do not call
plt.savefig() or plt.close() directly in any plotting code.

The semantic plots are output-only (the converted data, no input/diff column),
so the figure helpers create single-column layouts.
"""

import os
from collections.abc import Sequence
from typing import Any

import matplotlib.pyplot as plt


def save_figure(fig: Any, output_path: str, dpi: int = 150) -> None:
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


def make_mass_bin_figure(
    row_labels: Sequence[str] = ("Top 5", "Median 5", "Bottom 5"),
    figsize: tuple[float, float] = (6, 11),
) -> tuple[Any, Any]:
    """Create a 3x1 figure (one row per mass bin) for output-only evolution plots.

    Each row's title is set to its mass-bin label; the caller sets the x/y labels.

    Returns
    -------
    fig : matplotlib.figure.Figure
    axes : ndarray of shape (3,)
    """
    fig, axes = plt.subplots(3, 1, figsize=figsize)
    for ax, label in zip(axes, row_labels):
        ax.set_title(label)
    return fig, axes


def make_single_figure(
    title: str = "Output",
    figsize: tuple[float, float] = (6, 5),
) -> tuple[Any, Any]:
    """Create a single-panel figure for an output-only distribution plot.

    Returns
    -------
    fig : matplotlib.figure.Figure
    ax : matplotlib.axes.Axes
    """
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    ax.set_title(title)
    return fig, ax
