"""Tests for utils.binary_writer: packing, header round-trip, endianness guard."""

import io
import struct

import numpy as np
import pytest

from errors import ConversionError
from utils import binary_writer
from utils.binary_writer import (
    _pack_tree,
    _require_little_endian,
    patch_header,
    write_header,
    write_placeholder_header,
)
from utils.schema import HALO_RECORD_DTYPE


def _make_fields(n=2, **overrides):
    """Minimal valid field dict for _pack_tree (all mandatory keys present)."""
    fields = {
        "Descendant": np.arange(n, dtype=np.int32),
        "FirstProgenitor": np.full(n, -1, np.int32),
        "NextProgenitor": np.full(n, -1, np.int32),
        "FirstHaloInFOFGroup": np.arange(n, dtype=np.int32),
        "NextHaloInFOFGroup": np.full(n, -1, np.int32),
        "SubhaloLen": np.full(n, 100, np.int32),
        "Group_M_Crit200": np.ones(n, np.float32),
        "SubhaloVMax": np.full(n, 200.0, np.float32),
        "SubhaloIDMostBound": np.arange(n, dtype=np.int64),
        "SnapNum": np.full(n, 63, np.int32),
        "SubhaloPos": np.tile([1000.0, 2000.0, 3000.0], (n, 1)).astype(np.float32),
        "SubhaloVel": np.tile([10.0, 20.0, 30.0], (n, 1)).astype(np.float32),
        "SubhaloSpin": np.tile([1000.0, 2000.0, 3000.0], (n, 1)).astype(np.float32),
    }
    fields.update(overrides)
    return fields


def test_pack_tree_byte_length():
    blob = _pack_tree(_make_fields(n=4))
    assert len(blob) == 4 * 104


def test_pack_tree_scales_pos_and_spin_by_1000():
    blob = _pack_tree(_make_fields(n=1))
    rec = np.frombuffer(blob, dtype=HALO_RECORD_DTYPE)
    # kpc/h -> Mpc/h and (kpc/h)(km/s) -> (Mpc/h)(km/s): both divided by 1000.
    assert np.allclose(rec["Pos"][0], [1.0, 2.0, 3.0])
    assert np.allclose(rec["Spin"][0], [1.0, 2.0, 3.0])
    # Vel is not scaled.
    assert np.allclose(rec["Vel"][0], [10.0, 20.0, 30.0])


def test_pack_tree_optional_field_defaults():
    rec = np.frombuffer(_pack_tree(_make_fields(n=1)), dtype=HALO_RECORD_DTYPE)
    assert rec["M_Mean200"][0] == 0.0
    assert rec["FileNr"][0] == -1
    assert rec["SubhaloIndex"][0] == -1
    assert rec["SubHalfMass"][0] == 0.0


def test_pack_tree_rejects_bad_vector_shape():
    bad = _make_fields(n=2)
    bad["SubhaloPos"] = np.zeros((2, 2), np.float32)
    with pytest.raises(ValueError, match="SubhaloPos"):
        _pack_tree(bad)


def test_write_and_patch_header_roundtrip():
    buf = io.BytesIO()
    write_placeholder_header(buf, n_trees=3)
    assert buf.tell() == 8 + 3 * 4
    # Simulate trees written after the placeholder.
    payload = b"\xaa" * 16
    buf.write(payload)
    end = buf.tell()

    patch_header(
        buf,
        particle_mass=1.0,
        n_trees=3,
        total_halos=30,
        n_output_files=1,
        tree_n_halos=[10, 10, 10],
    )
    # patch_header restores the position so subsequent writes are unaffected.
    assert buf.tell() == end

    buf.seek(0)
    n_trees, total = struct.unpack("<ii", buf.read(8))
    counts = np.frombuffer(buf.read(3 * 4), dtype=np.int32)
    assert n_trees == 3
    assert total == 30
    assert list(counts) == [10, 10, 10]


def test_write_header_rejects_inconsistent_counts():
    buf = io.BytesIO()
    with pytest.raises(ValueError, match="total_halos"):
        write_header(buf, 1.0, n_trees=2, total_halos=99, n_output_files=1, tree_n_halos=[10, 10])


def test_require_little_endian_raises_on_big_endian(monkeypatch):
    monkeypatch.setattr(binary_writer.sys, "byteorder", "big")
    with pytest.raises(ConversionError, match="little-endian"):
        _require_little_endian()
    with pytest.raises(ConversionError):
        write_placeholder_header(io.BytesIO(), n_trees=1)
    with pytest.raises(ConversionError):
        write_header(io.BytesIO(), 1.0, 1, 1, 1, [1])


def test_require_little_endian_passes_on_little_endian(monkeypatch):
    monkeypatch.setattr(binary_writer.sys, "byteorder", "little")
    _require_little_endian()  # must not raise
