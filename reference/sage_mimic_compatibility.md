# SAGE and MIMIC Compatibility Matrix

This document records which converter output formats are compatible with
[SAGE](https://github.com/sage-home/sage-model) and
[MIMIC](https://github.com/darrencroton/mimic),
and documents the differences between their LHaloTree readers.

---

## 1. Output Format Compatibility

| Output format | SAGE | MIMIC | Notes |
| --- | --- | --- | --- |
| `lhalo_binary` | yes TreeType=0 | yes TreeType=1 | Same 104-byte struct; enum values differ (see Section 3) |
| `lhalo_hdf5` | yes TreeType=1 | no | Field names differ (see Section 2) |

**Recommendation:** Use `lhalo_binary` when the converted trees must run in both SAGE and MIMIC.
`lhalo_hdf5` is SAGE-only.

---

## 2. HDF5 Field Name Incompatibility

The converter's HDF5 output uses Subfind-style dataset names (matching SAGE's `read_tree_lhalo_hdf5.c`).
MIMIC's HDF5 reader ([mimic/src/io/tree/hdf5.c](https://github.com/darrencroton/mimic/blob/master/src/io/tree/hdf5.c)) expects the original LHaloTree field names:

| Converter produces (`lhalo_hdf5`) | MIMIC HDF5 reader expects | Struct field (both) |
| --- | --- | --- |
| `SubhaloPos` | `Pos` | `Pos[3]` |
| `SubhaloVel` | `Vel` | `Vel[3]` |
| `SubhaloSpin` | `Spin` | `Spin[3]` |
| `SubhaloVMax` | `Vmax` | `Vmax` |
| `Group_M_Mean200` | `M_mean200` | `M_Mean200` |
| `Group_M_Crit200` | `Mvir` | `Mvir` |
| `Group_M_TopHat200` | `M_TopHat` | `M_TopHat` |
| `SubhaloLen` | `Len` | `Len` |
| `SubhaloIDMostBound` | `MostBoundID` | `MostBoundID` |
| `FileNr` | `Filenr` | `FileNr` |
| (not written) | `SubHaloIndex` | `SubhaloIndex` |

Because these names differ, MIMIC's HDF5 reader will fail to open datasets from converter
HDF5 output. No workaround exists short of modifying MIMIC's reader or writing a separate
MIMIC-specific HDF5 output mode (not implemented).

---

## 3. TreeType Enum Inversion

The integer values of the `TreeType` enum are **inverted** between SAGE and MIMIC:

| Code | SAGE ([core_allvars.h:19-33](https://github.com/sage-home/sage-model/blob/master/src/core_allvars.h#L19-L33)) | MIMIC ([types.h:36-40](https://github.com/darrencroton/mimic/blob/master/src/include/types.h#L36-L40)) |
| --- | --- | --- |
| 0 | `lhalo_binary` | `genesis_lhalo_hdf5` |
| 1 | `lhalo_hdf5` | `lhalo_binary` |

When running MIMIC on binary output from the converter:

- Set `TreeType = 1` in MIMIC's configuration (not 0).

When running SAGE on binary output from the converter:

- Set `TreeType = lhalo_binary` (string form) in SAGE's parameter file,
  which maps to integer 0 in SAGE's enum.

---

## 4. HDF5 Unit Scaling (SAGE convention)

For converter `lhalo_hdf5` output, SAGE applies x0.001 to `SubhaloPos` and `SubhaloSpin` after reading:

- `SubhaloPos`: stored in kpc/h on disk -> converted to Mpc/h internally
- `SubhaloSpin`: stored in (kpc/h)(km/s) on disk -> converted to (Mpc/h)(km/s) internally

MIMIC cannot read converter HDF5 output because required dataset names differ (see Section 2), so this scaling convention is only relevant to SAGE for this output mode.

For binary output, no post-read scaling is applied by either SAGE or MIMIC.

---

## 5. Binary Struct Compatibility

The 104-byte halo record struct is identical between SAGE (`struct halo_data`,
[core_simulation.h:2-31](https://github.com/sage-home/sage-model/blob/master/src/core_simulation.h#L2-L31))
and MIMIC (`struct RawHalo`,
[types.h:8-33](https://github.com/darrencroton/mimic/blob/master/src/include/types.h#L8-L33)).
All 25 fields appear in the same order with the same C types.
See `reference/sage_lhalotree_binary_schema.md` for the full field table.
