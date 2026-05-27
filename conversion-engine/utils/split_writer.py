"""
split_writer.py — SplitWriter context manager for streaming SAGE LHaloTree output.

Provides a uniform write interface for all drivers regardless of output format
(HDF5 or binary) and number of output files.  Eliminates in-memory tree
accumulation for binary output by using a placeholder-then-patch strategy:
a zeroed header block of the correct size is written when each file is opened,
trees are written sequentially, and the header is patched in place after all
trees for that file are done.

Usage:
    from utils.split_writer import SplitWriter

    with SplitWriter(
        output_path=output_path,        # path to file index 0
        output_format=output_format,    # "lhalo_hdf5" or "lhalo_binary"
        n_output_files=n_output_files,
        n_trees_total=n_trees_total,    # must be known upfront
        particle_mass=particle_mass_1e10,
    ) as writer:
        for fields in tree_stream:
            writer.write_tree(fields)

    output_paths = writer.output_paths  # list of all written file paths
"""

import logging
import os
from pathlib import Path
from types import TracebackType
from typing import BinaryIO

import h5py

from utils import binary_writer, hdf5_writer

log = logging.getLogger(__name__)

_MIN_TREES_PER_FILE_WARN = 5  # warn when average trees/file falls below this


# ---------------------------------------------------------------------------
# Path and partition helpers
# ---------------------------------------------------------------------------


def _derive_output_paths(output_path: str, n_files: int) -> list[str]:
    """Return n_files output paths by replacing the trailing file-index token.

    Examples
    --------
    "output/sim_STC.0.hdf5" + 3 → ["output/sim_STC.0.hdf5",
                                     "output/sim_STC.1.hdf5",
                                     "output/sim_STC.2.hdf5"]
    "output/sim_STC.0"      + 3 → ["output/sim_STC.0",
                                     "output/sim_STC.1",
                                     "output/sim_STC.2"]
    """
    p = Path(output_path)
    if p.suffix == ".hdf5":
        # Strip .hdf5 → "output/sim_STC.0", then strip ".0" → "output/sim_STC"
        stem = str(p.with_suffix(""))
        base = stem.rsplit(".", 1)[0]
        return [f"{base}.{i}.hdf5" for i in range(n_files)]
    else:
        base = str(p).rsplit(".", 1)[0]
        return [f"{base}.{i}" for i in range(n_files)]


def _compute_partition(n_trees_total: int, n_files: int) -> list[int]:
    """Divide n_trees_total as evenly as possible across n_files.

    Returns a list of length n_files that sums to n_trees_total.  Front files
    receive one extra tree when n_trees_total % n_files != 0.
    """
    base, remainder = divmod(n_trees_total, n_files)
    return [base + (1 if i < remainder else 0) for i in range(n_files)]


# ---------------------------------------------------------------------------
# SplitWriter
# ---------------------------------------------------------------------------


class SplitWriter:
    """Stream trees to one or more SAGE LHaloTree output files.

    For binary output, uses a placeholder-then-patch strategy so no tree data
    is accumulated in memory: a zeroed header of the correct size is written at
    file open, trees are appended sequentially, and the real header is written
    at offset 0 after all trees for that file are complete.

    For HDF5 output, trees are written incrementally and the header group is
    appended after all trees in each file are done.

    Automatically rotates to the next output file when the allocated tree count
    for the current file is reached.  Cleans up all partially-written files on
    exception.

    Parameters
    ----------
    output_path : str
        Path to the first output file (index 0).  Additional files are derived
        by replacing the trailing index token (e.g. ".0.hdf5" → ".1.hdf5").
    output_format : str
        "lhalo_hdf5" or "lhalo_binary".
    n_output_files : int
        Requested number of output files (must be ≥ 1).  Clamped to
        n_trees_total if larger so no empty files are created.
    n_trees_total : int
        Total number of trees that will be written across all files (must be ≥ 1).
    particle_mass : float
        Dark matter particle mass in units of 10¹⁰ M☉/h, written to each
        file's header.
    """

    def __init__(
        self,
        output_path: str,
        output_format: str,
        n_output_files: int,
        n_trees_total: int,
        particle_mass: float,
    ) -> None:
        if n_output_files < 1:
            raise ValueError(f"n_output_files must be ≥ 1, got {n_output_files}.")
        if n_trees_total < 1:
            raise ValueError(f"n_trees_total must be ≥ 1, got {n_trees_total}.")
        if output_format not in ("lhalo_hdf5", "lhalo_binary"):
            raise ValueError(
                f"output_format must be 'lhalo_hdf5' or 'lhalo_binary', got {output_format!r}."
            )

        effective_n_files = min(n_output_files, n_trees_total)
        if effective_n_files < n_output_files:
            log.warning(
                "n_output_files=%d exceeds tree count (%d). Using %d file(s).",
                n_output_files,
                n_trees_total,
                effective_n_files,
            )

        avg_trees = n_trees_total / effective_n_files
        if avg_trees < _MIN_TREES_PER_FILE_WARN:
            log.warning(
                "n_output_files=%d yields ~%.1f trees/file on average. Files will be very small.",
                effective_n_files,
                avg_trees,
            )

        self._output_format = output_format
        self._particle_mass = particle_mass
        self._n_files_total = effective_n_files
        self._partition = _compute_partition(n_trees_total, effective_n_files)
        self._all_paths = _derive_output_paths(output_path, effective_n_files)

        self._file_idx = 0
        self._tree_idx_global = 0
        self._tree_idx_in_file = 0
        self._file_n_halos: list[int] = []
        self._opened_paths: list[str] = []
        self._current_handle: BinaryIO | h5py.File | None = None

        self._current_handle = self._open_file(0)
        self._opened_paths.append(self._all_paths[0])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open_file(self, file_idx: int) -> BinaryIO | h5py.File:
        path = self._all_paths[file_idx]
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if self._output_format == "lhalo_binary":
            fh = open(path, "wb")  # noqa: SIM115
            binary_writer.write_placeholder_header(fh, self._partition[file_idx])
            return fh
        else:
            return h5py.File(path, "w")

    def _finalise_file(self, file_idx: int, handle: BinaryIO | h5py.File) -> None:
        n = len(self._file_n_halos)
        total = sum(self._file_n_halos)
        if isinstance(handle, h5py.File):
            hdf5_writer.write_header(
                handle,
                particle_mass=self._particle_mass,
                n_trees=n,
                total_halos=total,
                n_output_files=self._n_files_total,
                tree_n_halos=self._file_n_halos,
            )
        else:
            binary_writer.patch_header(
                handle,
                particle_mass=self._particle_mass,
                n_trees=n,
                total_halos=total,
                n_output_files=self._n_files_total,
                tree_n_halos=self._file_n_halos,
            )
        handle.close()

    def _rotate(self) -> None:
        assert self._current_handle is not None
        self._finalise_file(self._file_idx, self._current_handle)
        self._current_handle = None
        self._file_idx += 1
        self._tree_idx_in_file = 0
        self._file_n_halos = []
        self._current_handle = self._open_file(self._file_idx)
        self._opened_paths.append(self._all_paths[self._file_idx])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_tree(self, fields: dict) -> None:
        """Write one tree to the current output file.

        Automatically rotates to the next output file when the current file's
        allocated tree count is reached.

        Parameters
        ----------
        fields : dict[str, array-like]
            SAGE field dict — same contract as hdf5_writer.write_tree() and
            binary_writer.write_tree().
        """
        assert self._current_handle is not None
        n_halos = len(fields["Descendant"])
        if isinstance(self._current_handle, h5py.File):
            hdf5_writer.write_tree(self._current_handle, self._tree_idx_in_file, fields)
        else:
            binary_writer.write_tree(self._current_handle, self._tree_idx_in_file, fields)

        self._file_n_halos.append(n_halos)
        self._tree_idx_in_file += 1
        self._tree_idx_global += 1

        if (
            self._tree_idx_in_file >= self._partition[self._file_idx]
            and self._file_idx < len(self._all_paths) - 1
        ):
            self._rotate()

    @property
    def output_paths(self) -> list[str]:
        """List of all output file paths (finalised and in-progress)."""
        return list(self._all_paths)

    def close(self) -> None:
        """Finalise and close all output files."""
        if self._current_handle is not None:
            self._finalise_file(self._file_idx, self._current_handle)
            self._current_handle = None

    def _cleanup(self) -> None:
        """Delete all partially-written files on error."""
        if self._current_handle is not None:
            try:
                self._current_handle.close()
            except Exception:
                pass
            self._current_handle = None
        for path in self._opened_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass

    def __enter__(self) -> "SplitWriter":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        if exc_type is not None:
            self._cleanup()
        else:
            self.close()
        return False
