# SAGE LHaloTree Binary Output Schema

This document describes the binary file format written by `conversion-engine/utils/binary_writer.py`
and consumed by SAGE's `lhalo_binary` reader (`src/io/read_tree_lhalo_binary.c`, TreeType=0)
and MIMIC's binary reader (`src/io/tree/binary.c`, TreeType=1).

> **Compatibility:** Binary output is fully compatible with both SAGE and MIMIC. HDF5 output
> is SAGE-only. See `reference/sage_mimic_compatibility.md` for the full compatibility matrix.
> **Endianness:** The writer explicitly packs data as little-endian (`<` format prefix).
> SAGE and MIMIC read in native byte order. This is compatible on all x86-64 targets.
> The converter enforces this when binary output is written and raises `ConversionError` on a
> big-endian host. (HDF5 conversions never touch the binary writer and run on any host.)
> Use `lhalo_hdf5` for portable output on heterogeneous architectures.

---

## 1. File Layout

```text
Offset 0               : int32   nforests          — number of trees in this file
Offset 4               : int32   totnhalos         — total halos across all trees
Offset 8               : int32[] nhalos_per_forest — nhalos for each tree (length = nforests)
Offset 8 + 4×nforests  : halo_data[]               — flat array of 104-byte halo records
```

Halo records are written sequentially: all halos of tree 0, then all halos of tree 1, etc.
The record count for tree `i` is `nhalos_per_forest[i]`.

---

## 2. Halo Record (104 bytes, little-endian)

Each record corresponds to one halo and is packed with format `"<6i3f3f3f2f3fq3if"`.

| # | Field | C type | Pack char | Byte offset | Units on disk | Mandatory | Notes |
| --- | ------- | -------- | ----------- | ------------- | --------------- | ----------- | ------- |
| 1 | Descendant | int32 | `i` | 0 | — | Yes | Tree-local index; −1 = no descendant (root halo) |
| 2 | FirstProgenitor | int32 | `i` | 4 | — | Yes | Tree-local index; −1 = leaf |
| 3 | NextProgenitor | int32 | `i` | 8 | — | Yes | Tree-local index; next sibling progenitor |
| 4 | FirstHaloInFOFgroup | int32 | `i` | 12 | — | Yes | Tree-local index; self = central halo |
| 5 | NextHaloInFOFgroup | int32 | `i` | 16 | — | Yes | Tree-local index; −1 = last in group |
| 6 | Len | int32 | `i` | 20 | particles | Yes | Mapped from `SubhaloLen` |
| 7 | M_Mean200 | float32 | `f` | 24 | 10¹⁰ M☉/h | No | 0.0 if absent (`Group_M_Mean200`) |
| 8 | M_Crit200 | float32 | `f` | 28 | 10¹⁰ M☉/h | Yes | Mapped from `Group_M_Crit200` (virial/M200c) |
| 9 | M_TopHat | float32 | `f` | 32 | 10¹⁰ M☉/h | No | 0.0 if absent (`Group_M_TopHat200`) |
| 10 | Pos[0] | float32 | `f` | 36 | **Mpc/h** | Yes | See unit note below |
| 11 | Pos[1] | float32 | `f` | 40 | **Mpc/h** | Yes | |
| 12 | Pos[2] | float32 | `f` | 44 | **Mpc/h** | Yes | |
| 13 | Vel[0] | float32 | `f` | 48 | km/s | Yes | Mapped from `SubhaloVel[:,0]` |
| 14 | Vel[1] | float32 | `f` | 52 | km/s | Yes | |
| 15 | Vel[2] | float32 | `f` | 56 | km/s | Yes | |
| 16 | VelDisp | float32 | `f` | 60 | km/s | No | 0.0 if absent (`SubhaloVelDisp`) |
| 17 | Vmax | float32 | `f` | 64 | km/s | Yes | Mapped from `SubhaloVMax` |
| 18 | Spin[0] | float32 | `f` | 68 | **(Mpc/h)(km/s)** | Yes | See unit note below |
| 19 | Spin[1] | float32 | `f` | 72 | **(Mpc/h)(km/s)** | Yes | |
| 20 | Spin[2] | float32 | `f` | 76 | **(Mpc/h)(km/s)** | Yes | |
| 21 | MostBoundID | int64 | `q` | 80 | — | Yes | Mapped from `SubhaloIDMostBound` |
| 22 | SnapNum | int32 | `i` | 88 | — | Yes | Zero-based snapshot index |
| 23 | FileNr | int32 | `i` | 92 | — | No | −1 if absent |
| 24 | SubhaloIndex | int32 | `i` | 96 | — | — | Always −1 (not in schema) |
| 25 | SubHalfMass | float32 | `f` | 100 | — | — | Always 0.0 (not in schema) |

---

## 3. Unit Convention for Pos and Spin

**Critical:** The binary reader uses Pos and Spin values as-is (no post-read scaling).
This differs from the HDF5 reader, which applies ×0.001 after reading.

Drivers must produce `SubhaloPos` in **kpc/h** and `SubhaloSpin` in **(kpc/h)(km/s)** —
the same units as HDF5 output. The writer (`binary_writer._pack_tree`) internally divides
both by 1000 before struct-packing, so the binary file stores:

- `Pos[0–2]` in **Mpc/h**
- `Spin[0–2]` in **(Mpc/h)(km/s)**

**Do not divide by 1000 in the driver.** The writer handles this conversion.

---

## 4. Mandatory Fields Summary

These keys must be present in the `fields` dict passed to `binary_writer.write_tree()`:

```text
Descendant           FirstProgenitor      NextProgenitor
FirstHaloInFOFGroup  NextHaloInFOFGroup   SubhaloLen
Group_M_Crit200      SubhaloVMax          SubhaloIDMostBound
SnapNum              SubhaloPos           SubhaloVel
SubhaloSpin
```

Optional keys (written as sentinel if absent):

```text
Group_M_Mean200      → 0.0
Group_M_TopHat200    → 0.0
SubhaloVelDisp       → 0.0
FileNr               → -1
```

---

## 5. SAGE Reader Reference

Source: [read_tree_lhalo_binary.c](https://github.com/sage-home/sage-model/blob/master/src/io/read_tree_lhalo_binary.c)

- Header read: lines 56–62 (offsets 0 and 4)
- Forest metadata: line 165 (offset 8, array of `int32_t`)
- Halo load: line 261 (single `pread()` of `nhalos × 104` bytes)
- No unit conversions applied post-read
- SAGE enum: `lhalo_binary = 0` ([core_allvars.h:19](https://github.com/sage-home/sage-model/blob/master/src/core_allvars.h#L19))

## 6. MIMIC Reader Reference

Source: [mimic/src/io/tree/binary.c](https://github.com/darrencroton/mimic/blob/master/src/io/tree/binary.c)

- Same header and struct layout as SAGE
- Identical 104-byte `struct RawHalo` ([types.h:8–33](https://github.com/darrencroton/mimic/blob/master/src/include/types.h#L8-L33))
- No unit conversions applied post-read
- **MIMIC enum:** `lhalo_binary = 1` ([types.h:36–40](https://github.com/darrencroton/mimic/blob/master/src/include/types.h#L36-L40)) — inverted from SAGE
