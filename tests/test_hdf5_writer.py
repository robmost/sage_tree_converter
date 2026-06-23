"""Tests for the dtype-casting helper in utils.hdf5_writer."""

import numpy as np
import pytest

from utils.hdf5_writer import _cast


def test_cast_int32_field():
    out = _cast("SnapNum", [1.0, 2.0, 3.0])
    assert out.dtype == np.int32


def test_cast_int64_field():
    out = _cast("SubhaloIDMostBound", [1, 2])
    assert out.dtype == np.int64


def test_cast_float32_scalar_field():
    out = _cast("Group_M_Crit200", [1, 2, 3])
    assert out.dtype == np.float32
    assert out.ndim == 1


def test_cast_float32_vector_field():
    out = _cast("SubhaloPos", [[1, 2, 3], [4, 5, 6]])
    assert out.dtype == np.float32
    assert out.shape == (2, 3)


def test_cast_vector_field_rejects_wrong_shape():
    with pytest.raises(ValueError, match="SubhaloPos"):
        _cast("SubhaloPos", [[1, 2], [3, 4]])


def test_cast_unknown_field_warns_and_passes_through():
    with pytest.warns(UserWarning, match="canonical dtype map"):
        out = _cast("NotARealField", [1, 2, 3])
    assert list(out) == [1, 2, 3]
