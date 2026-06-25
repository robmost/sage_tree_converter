"""FOF-topology invariants shared across drivers, plus the Gadget-4 windowed read.

Covers the universal LHaloTree rule that the true FOF central heads the
NextHaloInFOFGroup chain (utils.fof_topology + each driver), the opt-in flyby merge
(utils.fof_topology.merge_flybys), and that windowed bulk reads in the Gadget-4 driver
do not change the output.
"""

import numpy as np
import pytest

from utils.fof_topology import build_fof_chains, central_first, merge_flybys

# ---------------------------------------------------------------------------
# central_first
# ---------------------------------------------------------------------------


def test_central_first_moves_central_to_head():
    assert central_first([3, 1, 2], 2) == [2, 3, 1]


def test_central_first_noop_when_already_head():
    idxs = [2, 3, 1]
    assert central_first(idxs, 2) == [2, 3, 1]


def test_central_first_empty():
    assert central_first([], 0) == []


# ---------------------------------------------------------------------------
# build_fof_chains
# ---------------------------------------------------------------------------


def test_build_fof_chains_central_heads_over_heavier_satellite():
    # One z=0 group: central idx0 (light) with a heavier satellite idx1.
    snaps = np.array([0, 0], dtype=np.int32)
    central_idx = np.array([0, 0], dtype=np.int32)  # both belong to central 0
    sort_value = np.array([1.0, 9.0])  # satellite is heavier
    fhifof, nhifof = build_fof_chains(snaps, central_idx, sort_value)
    assert list(fhifof) == [0, 0]
    assert nhifof[0] == 1  # central heads despite being lighter
    assert nhifof[1] == -1


def test_build_fof_chains_satellites_ordered_by_sort_value_desc():
    snaps = np.array([0, 0, 0], dtype=np.int32)
    central_idx = np.array([0, 0, 0], dtype=np.int32)
    sort_value = np.array([5.0, 2.0, 8.0])  # central(0), sats 1,2
    _, nhifof = build_fof_chains(snaps, central_idx, sort_value)
    # central 0 first, then satellites by descending sort_value: idx2 (8) then idx1 (2)
    assert nhifof[0] == 2
    assert nhifof[2] == 1
    assert nhifof[1] == -1


def test_build_fof_chains_separates_groups_by_snap_and_central():
    # Two snapshots, each a singleton central -> no links.
    snaps = np.array([1, 0], dtype=np.int32)
    central_idx = np.array([0, 1], dtype=np.int32)
    sort_value = np.array([3.0, 4.0])
    fhifof, nhifof = build_fof_chains(snaps, central_idx, sort_value)
    assert list(fhifof) == [0, 1]
    assert list(nhifof) == [-1, -1]


# ---------------------------------------------------------------------------
# merge_flybys
# ---------------------------------------------------------------------------


def test_merge_flybys_noop_with_single_z0_central():
    # snaps: two snapshots, one z=0 central -> nothing to merge.
    fhifof = np.array([0, 0, 2], dtype=np.int32)  # halo2 is a progenitor central
    nhifof = np.array([1, -1, -1], dtype=np.int32)
    snaps = np.array([1, 1, 0], dtype=np.int32)
    mvirs = np.array([10.0, 5.0, 8.0])
    out_f, out_n, out_mb = merge_flybys(fhifof, nhifof, mvirs, snaps)
    np.testing.assert_array_equal(out_f, fhifof)
    np.testing.assert_array_equal(out_n, nhifof)
    assert out_mb is None


def test_merge_flybys_collapses_multiple_z0_centrals():
    # Two independent z=0 centrals (idx0 light, idx2 heavy) each with a satellite.
    # idx0<-idx1 (group A), idx2<-idx3 (group B), all at the final snapshot.
    fhifof = np.array([0, 0, 2, 2], dtype=np.int32)
    nhifof = np.array([1, -1, 3, -1], dtype=np.int32)
    snaps = np.array([0, 0, 0, 0], dtype=np.int32)
    mvirs = np.array([1.0, 0.5, 9.0, 4.0])  # idx2 is the most massive central
    out_f, out_n, _ = merge_flybys(fhifof, nhifof, mvirs, snaps)
    # Everything folds into the most massive central (idx2).
    np.testing.assert_array_equal(out_f, np.array([2, 2, 2, 2]))
    # Exactly one self-pointing central remains at z=0.
    assert int(np.sum(out_f == np.arange(4))) == 1
    # Chain is headed by the central (idx2) and reaches every member.
    chain = []
    cur = 2
    while cur != -1:
        chain.append(cur)
        cur = int(out_n[cur])
    assert chain[0] == 2
    assert sorted(chain) == [0, 1, 2, 3]


def test_merge_flybys_flips_real_mostbound_only_on_demoted_centrals():
    fhifof = np.array([0, 0, 2, 2], dtype=np.int32)
    nhifof = np.array([1, -1, 3, -1], dtype=np.int32)
    snaps = np.array([0, 0, 0, 0], dtype=np.int32)
    mvirs = np.array([1.0, 0.5, 9.0, 4.0])
    most_bound = np.array([100, 200, 300, 400], dtype=np.int64)
    _, _, out_mb = merge_flybys(fhifof, nhifof, mvirs, snaps, most_bound)
    # idx0 is the demoted flyby central -> sign flipped; its satellite (idx1) and the
    # host group (idx2 central, idx3 sat) keep their IDs.
    np.testing.assert_array_equal(out_mb, np.array([-100, 200, 300, 400]))


def test_merge_flybys_leaves_sentinel_mostbound_untouched():
    fhifof = np.array([0, 2], dtype=np.int32)
    nhifof = np.array([-1, -1], dtype=np.int32)
    snaps = np.array([0, 0], dtype=np.int32)
    mvirs = np.array([1.0, 9.0])
    most_bound = np.array([-1, -1], dtype=np.int64)  # CT/AHF sentinel
    _, _, out_mb = merge_flybys(fhifof, nhifof, mvirs, snaps, most_bound)
    np.testing.assert_array_equal(out_mb, np.array([-1, -1]))


# ---------------------------------------------------------------------------
# Consistent-Trees driver: stripped central heads the chain
# ---------------------------------------------------------------------------


def _ctrees_two_halo_group():
    """Build a minimal CT halo array: one z=0 FOF with a stripped (light) central."""
    from drivers import rockstar_consistent_trees_ascii as ct

    ncols = ct._C_M200C + 1
    halos = np.zeros((2, ncols), dtype=np.float64)
    # central (light) then satellite (heavy)
    halos[0, ct._C_ID] = 100
    halos[0, ct._C_DESC_ID] = -1
    halos[0, ct._C_UPID] = -1
    halos[0, ct._C_MVIR] = 10.0
    halos[0, ct._C_DFI] = 0
    halos[0, ct._C_SNAP_NUM] = 50
    halos[0, ct._C_NEXT_COPROG_DFI] = -1
    halos[1, ct._C_ID] = 101
    halos[1, ct._C_DESC_ID] = -1
    halos[1, ct._C_UPID] = 100  # satellite of the central
    halos[1, ct._C_MVIR] = 99.0  # heavier than its central
    halos[1, ct._C_DFI] = 1
    halos[1, ct._C_SNAP_NUM] = 50
    halos[1, ct._C_NEXT_COPROG_DFI] = -1
    return ct, halos


def test_ctrees_central_heads_chain_when_satellite_is_heavier():
    ct, halos = _ctrees_two_halo_group()
    ptrs = ct._reconstruct_pointers(halos)
    fhifof = ptrs["FirstHaloInFOFGroup"]
    nhifof = ptrs["NextHaloInFOFGroup"]
    assert list(fhifof) == [0, 0]  # both point to the central
    assert nhifof[0] == 1  # central heads the chain
    assert nhifof[1] == -1  # satellite is the tail


# ---------------------------------------------------------------------------
# Gadget-4 driver: min-SubhaloNr central heads the chain
# ---------------------------------------------------------------------------


def test_gadget4_central_is_min_subhalonr_not_max_len():
    from drivers.subfind_gadget4_hdf5 import _build_fof_pointers

    snap = np.array([50, 50], dtype=np.int32)
    group_nr = np.array([0, 0], dtype=np.int64)
    sub_len = np.array([10, 99], dtype=np.int32)  # idx1 is heavier
    sub_nr = np.array([5, 9], dtype=np.int64)  # idx0 is the central (min SubhaloNr)
    fhfof, nhfof = _build_fof_pointers(snap, group_nr, sub_len, sub_nr)
    assert list(fhfof) == [0, 0]
    assert nhfof[0] == 1  # central (idx0) heads despite idx1 being heavier
    assert nhfof[1] == -1


# ---------------------------------------------------------------------------
# Gadget-4 windowed read equivalence
# ---------------------------------------------------------------------------


def _write_synthetic_gadget4(path, trees):
    """Write a tiny Gadget-4-style trees.hdf5 from a list of per-tree halo dicts."""
    import h5py

    starts, lengths = [], []
    cursor = 0
    cols = {
        "TreeDescendant": np.int32,
        "SnapNum": np.int32,
        "GroupNr": np.int64,
        "SubhaloLen": np.int32,
        "SubhaloNr": np.int64,
        "Group_M_Crit200": np.float32,
        "SubhaloVelDisp": np.float32,
        "SubhaloVmax": np.float32,
        "SubhaloIDMostbound": np.int64,
    }
    flat = {k: [] for k in cols}
    flat_pos, flat_vel, flat_spin = [], [], []
    for t in trees:
        n = len(t["SnapNum"])
        starts.append(cursor)
        lengths.append(n)
        cursor += n
        for k in cols:
            flat[k].append(np.asarray(t[k], dtype=cols[k]))
        flat_pos.append(np.asarray(t["SubhaloPos"], dtype=np.float32))
        flat_vel.append(np.asarray(t["SubhaloVel"], dtype=np.float32))
        flat_spin.append(np.asarray(t["SubhaloSpin"], dtype=np.float32))
    with h5py.File(path, "w") as f:
        tt = f.create_group("TreeTable")
        tt.create_dataset("StartOffset", data=np.array(starts, dtype=np.int64))
        tt.create_dataset("Length", data=np.array(lengths, dtype=np.int64))
        th = f.create_group("TreeHalos")
        for k in cols:
            th.create_dataset(k, data=np.concatenate(flat[k]))
        th.create_dataset("SubhaloPos", data=np.concatenate(flat_pos))
        th.create_dataset("SubhaloVel", data=np.concatenate(flat_vel))
        th.create_dataset("SubhaloSpin", data=np.concatenate(flat_spin))


def _make_tree(snaps, group, sub_len, sub_nr, desc):
    n = len(snaps)
    rng = np.arange(n, dtype=np.float32)
    return {
        "SnapNum": snaps,
        "GroupNr": group,
        "SubhaloLen": sub_len,
        "SubhaloNr": sub_nr,
        "TreeDescendant": desc,
        "Group_M_Crit200": (np.asarray(sub_len, dtype=np.float32) * 1e-3),
        "SubhaloVelDisp": rng + 1.0,
        "SubhaloVmax": rng + 2.0,
        "SubhaloIDMostbound": np.arange(n, dtype=np.int64) + 1,
        "SubhaloPos": np.stack([rng, rng + 0.1, rng + 0.2], axis=1),
        "SubhaloVel": np.stack([rng, rng + 0.3, rng + 0.4], axis=1),
        "SubhaloSpin": np.stack([rng, rng + 0.5, rng + 0.6], axis=1),
    }


def test_gadget4_windowed_read_matches_single_window(tmp_path, monkeypatch):
    import h5py

    from drivers import subfind_gadget4_hdf5 as g4

    trees = [
        # tree 0: z=0 group with central (min SubhaloNr) lighter than its satellite
        _make_tree(
            snaps=[50, 50, 49],
            group=[0, 0, 0],
            sub_len=[10, 50, 30],
            sub_nr=[1, 2, 9],
            desc=[-1, 0, 1],
        ),
        # tree 1: two z=0 groups (kept independent by default)
        _make_tree(
            snaps=[50, 50, 49, 49],
            group=[0, 1, 0, 1],
            sub_len=[20, 15, 8, 7],
            sub_nr=[3, 4, 11, 12],
            desc=[-1, -1, 0, 1],
        ),
        _make_tree(
            snaps=[50, 49],
            group=[0, 0],
            sub_len=[5, 4],
            sub_nr=[5, 13],
            desc=[-1, 0],
        ),
    ]
    src = tmp_path / "trees.hdf5"
    _write_synthetic_gadget4(src, trees)

    def run(window_halos):
        monkeypatch.setattr(g4, "_WINDOW_HALOS", window_halos)
        out = tmp_path / f"out_{window_halos}_STC.0.hdf5"
        g4.convert(str(src), str(out), sim_params={"particle_mass_msun_per_h": 1.0e9})
        data = {}
        with h5py.File(out, "r") as f:
            for k in f:
                if not k.startswith("Tree"):
                    continue
                data[k] = {fld: f[k][fld][:] for fld in f[k]}
        return data

    big = run(10_000)  # all trees in one window
    small = run(1)  # forces a fresh window per tree
    assert big.keys() == small.keys()
    for tree_key in big:
        for fld in big[tree_key]:
            np.testing.assert_array_equal(
                big[tree_key][fld], small[tree_key][fld], err_msg=f"{tree_key}/{fld}"
            )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
