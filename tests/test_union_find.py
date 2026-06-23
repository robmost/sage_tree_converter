"""Tests for the _UnionFind helper used by the AHF driver to group halos into trees."""

from drivers.ahf_mergetree_ascii import _UnionFind


def test_init_each_element_is_its_own_root():
    uf = _UnionFind([1, 2, 3])
    assert uf.find(1) == 1
    assert uf.find(2) == 2
    assert uf.find(3) == 3


def test_union_is_transitive():
    uf = _UnionFind(range(5))
    uf.union(0, 1)
    uf.union(1, 2)
    assert uf.find(0) == uf.find(2)
    # A separate component stays separate.
    assert uf.find(0) != uf.find(3)


def test_union_is_idempotent():
    uf = _UnionFind([1, 2])
    uf.union(1, 2)
    root = uf.find(1)
    uf.union(1, 2)
    assert uf.find(1) == root
    assert uf.find(2) == root


def test_find_compresses_path():
    uf = _UnionFind(range(4))
    uf.union(0, 1)
    uf.union(1, 2)
    uf.union(2, 3)
    root = uf.find(3)
    # After find, every node on the path points straight at the root.
    assert uf.parent[3] == root
