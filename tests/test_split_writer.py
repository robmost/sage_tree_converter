"""Pure-function and validation tests for utils.split_writer.

Covers the partition/path helpers and the SplitWriter.__init__ rules that
AGENTS.md (G1 input validation, rules 4-5) states are enforced "in both modes".
"""

import logging

import pytest

from utils.split_writer import SplitWriter, _compute_partition, _derive_output_paths


def test_compute_partition_sums_and_length():
    part = _compute_partition(100, 3)
    assert part == [34, 33, 33]
    assert sum(part) == 100
    assert len(part) == 3


def test_compute_partition_even_split():
    assert _compute_partition(12, 4) == [3, 3, 3, 3]


def test_compute_partition_more_files_than_trees_pads_with_zeros():
    part = _compute_partition(3, 5)
    assert part == [1, 1, 1, 0, 0]
    assert sum(part) == 3


def test_derive_output_paths_hdf5():
    assert _derive_output_paths("output/sim_STC.0.hdf5", 3) == [
        "output/sim_STC.0.hdf5",
        "output/sim_STC.1.hdf5",
        "output/sim_STC.2.hdf5",
    ]


def test_derive_output_paths_binary():
    assert _derive_output_paths("output/sim_STC.0", 2) == [
        "output/sim_STC.0",
        "output/sim_STC.1",
    ]


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"n_output_files": 0, "n_trees_total": 10}, "n_output_files"),
        ({"n_output_files": 1, "n_trees_total": 0}, "n_trees_total"),
        ({"n_output_files": 1, "n_trees_total": 10, "output_format": "bogus"}, "output_format"),
    ],
)
def test_init_rejects_bad_args(tmp_path, kwargs, match):
    base = {
        "output_path": str(tmp_path / "out.0.hdf5"),
        "output_format": "lhalo_hdf5",
        "particle_mass": 1.0,
    }
    base.update(kwargs)
    with pytest.raises(ValueError, match=match):
        SplitWriter(**base)


def test_init_clamps_files_to_tree_count_and_warns(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        writer = SplitWriter(
            output_path=str(tmp_path / "out.0.hdf5"),
            output_format="lhalo_hdf5",
            n_output_files=100,
            n_trees_total=5,
            particle_mass=1.0,
        )
    try:
        # Rule 4: clamp n_output_files down to n_trees_total.
        assert writer._n_files_total == 5
        assert sum(writer._partition) == 5
        assert len(writer.output_paths) == 5
        assert any("exceeds tree count" in r.message for r in caplog.records)
    finally:
        writer.close()


def test_init_warns_on_very_fine_split(tmp_path, caplog):
    # Rule 5: < 5 trees/file on average -> warn (but proceed).
    with caplog.at_level(logging.WARNING):
        writer = SplitWriter(
            output_path=str(tmp_path / "out.0.hdf5"),
            output_format="lhalo_hdf5",
            n_output_files=3,
            n_trees_total=6,
            particle_mass=1.0,
        )
    try:
        assert any("trees/file" in r.message for r in caplog.records)
    finally:
        writer.close()
