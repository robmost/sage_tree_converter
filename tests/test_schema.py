"""Invariants for the canonical SAGE LHaloTree schema (utils.schema)."""

import numpy as np

from utils.schema import (
    ALL_KNOWN_FIELDS,
    HALO_RECORD_DTYPE,
    MANDATORY_FIELDS,
    OPTIONAL_FIELDS,
)


def test_halo_record_is_104_bytes():
    # Must match struct halo_data in core_simulation.h.
    assert HALO_RECORD_DTYPE.itemsize == 104


def test_halo_record_is_little_endian():
    # Every field is declared little-endian so the on-disk layout is host-independent.
    # (.byteorder normalises "<" to "=" on little-endian hosts; the array-protocol
    # typestring ".str" keeps the explicit "<"/">"/"|" order char.)
    for name in HALO_RECORD_DTYPE.names:
        base = HALO_RECORD_DTYPE.fields[name][0]
        sub = base.subdtype[0] if base.subdtype is not None else base
        assert sub.str[0] in ("<", "|"), (name, sub.str)


def test_mandatory_and_optional_fields_are_disjoint():
    assert MANDATORY_FIELDS.isdisjoint(OPTIONAL_FIELDS)


def test_all_known_fields_is_the_union():
    assert ALL_KNOWN_FIELDS == MANDATORY_FIELDS | OPTIONAL_FIELDS
    assert len(ALL_KNOWN_FIELDS) == len(MANDATORY_FIELDS) + len(OPTIONAL_FIELDS)


def test_field_sets_are_frozen():
    assert isinstance(MANDATORY_FIELDS, frozenset)
    assert isinstance(OPTIONAL_FIELDS, frozenset)


def test_record_roundtrips_through_bytes():
    rec = np.zeros(3, dtype=HALO_RECORD_DTYPE)
    rec["SnapNum"] = [1, 2, 3]
    back = np.frombuffer(rec.tobytes(), dtype=HALO_RECORD_DTYPE)
    assert np.array_equal(back["SnapNum"], [1, 2, 3])
    assert back.nbytes == 3 * 104
