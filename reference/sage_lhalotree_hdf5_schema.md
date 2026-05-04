# SAGE LHaloTree HDF5 Output Schema

This document is the authoritative reference for the HDF5 file format written by the
converter and read by SAGE's `lhalo_hdf5` reader. It is immutable during converter
operation. All `lhalo_hdf5` output files must conform exactly to this schema.

> **Compatibility:** This schema targets SAGE's `lhalo_hdf5` reader
> (`src/io/read_tree_lhalo_hdf5.c`, TreeType=1). It is **not compatible** with MIMIC's
> HDF5 reader, which expects the original LHaloTree field names (`Pos`, `Vel`,
> `M_mean200`, etc.). Use `lhalo_binary` output when targeting both SAGE and MIMIC.
> See `reference/sage_mimic_compatibility.md` for the full compatibility matrix.

---

## 1. File-Level Structure

```text
<output>.hdf5
├── Header/                         # HDF5 group
│   ├── [attr] ParticleMass         # double
│   ├── [attr] NtreesPerFile        # int32
│   ├── [attr] NhalosPerFile        # int32
│   ├── [attr] NumberOfOutputFiles  # int32
│   └── TreeNHalos                  # dataset: 1D int32, length = NtreesPerFile
└── Tree0/                          # HDF5 group — first merger tree (zero-indexed)
    └── <field>                     # one dataset per field (see Section 3)
    ...
└── Tree<NtreesPerFile-1>/          # HDF5 group — last merger tree
    └── <field>
```

---

## 2. Header Group

### 2.1 HDF5 Attributes

All four attributes are attached directly to the `Header/` group.

| Attribute | HDF5 type | Description |
| --- | --- | --- |
| `ParticleMass` | `double` (float64) | Dark matter particle mass in units of 10¹⁰ M☉/h |
| `NtreesPerFile` | `int32` | Number of merger trees stored in this file |
| `NhalosPerFile` | `int32` | Total number of halos across all trees in this file |
| `NumberOfOutputFiles` | `int32` | Total number of tree files in the simulation set |

### 2.2 TreeNHalos Dataset

- **Path**: `/Header/TreeNHalos`
- **dtype**: `int32`
- **Shape**: 1D array of length `NtreesPerFile`
- **Semantics**: `TreeNHalos[i]` is the number of halos in tree `Tree<i>`. The sum of all
  elements must equal `NhalosPerFile`.

---

## 3. Tree Groups

Each merger tree is stored in its own HDF5 group named `Tree<X>` where `X` is the
zero-based tree index (`X` ∈ `[0, NtreesPerFile - 1]`).

Within each `Tree<X>/` group, every field is stored as a 1D or 2D dataset. The first
dimension of every dataset is `N = TreeNHalos[X]` (the number of halos in that tree).
Halos are stored in a flat array; the tree structure is encoded entirely through the
pointer fields described in Section 4.

### 3.1 Pointer Fields (mandatory)

These five fields encode the tree topology. All are `int32`. Valid values are integers
in `[0, N - 1]`. The sentinel value `-1` indicates "no link".

| Field | dtype | Shape | Description |
| --- | --- | --- | --- |
| `Descendant` | int32 | (N,) | Index of the halo this halo merges into at the next snapshot. `-1` if this halo has no descendant (it is the root of the tree at redshift 0). |
| `FirstProgenitor` | int32 | (N,) | Index of the most massive progenitor of this halo at the previous snapshot. `-1` if this halo has no progenitors (it is a leaf). |
| `NextProgenitor` | int32 | (N,) | Index of the next progenitor of the same descendant, forming a singly-linked list of all progenitors. `-1` if there is no next progenitor. |
| `FirstHaloInFOFGroup` | int32 | (N,) | Index of the central (most massive) halo in the same FOF group at the same snapshot. A central halo points to itself. |
| `NextHaloInFOFGroup` | int32 | (N,) | Index of the next satellite halo in the same FOF group at the same snapshot, forming a singly-linked list. `-1` for the last halo in the group. |

### 3.2 Halo Property Fields (mandatory)

| Field | dtype | Shape | Units | Description |
| --- | --- | --- | --- | --- |
| `SubhaloLen` | int32 | (N,) | particles | Number of simulation particles bound to the halo |
| `Group_M_Crit200` | float32 | (N,) | 10¹⁰ M☉/h | Mass within the radius enclosing 200 times the critical density |
| `SubhaloVMax` | float32 | (N,) | km/s | Maximum circular velocity: max(sqrt(GM(\<r\>)/r)) |
| `SubhaloIDMostBound` | int64 | (N,) | — | Particle ID of the most bound particle. Dummy value (`-1`) is acceptable if unavailable in the input format. |
| `SnapNum` | int32 | (N,) | — | Snapshot index of this halo. Valid range: `[0, N_snapshots - 1]`. |

### 3.3 Vector Fields (mandatory)

Each vector field is stored as a 2D dataset with shape `(N, 3)`.

| Field | dtype | Shape | Units | Description |
| --- | --- | --- | --- | --- |
| `SubhaloPos` | float32 | (N, 3) | **kpc/h** | Comoving position `[X, Y, Z]` of the halo centre. SAGE multiplies by 0.001 on read → Mpc/h internally. |
| `SubhaloVel` | float32 | (N, 3) | km/s | Peculiar velocity `[Vx, Vy, Vz]` of the halo |
| `SubhaloSpin` | float32 | (N, 3) | **(kpc/h)(km/s)** | Specific angular momentum vector `[Jx, Jy, Jz]`. Angular momentum per unit mass, **not** the dimensionless spin parameter λ. SAGE multiplies by 0.001 on read → (Mpc/h)(km/s) internally. |

### 3.4 Optional Fields

SAGE reads these fields if present but does not use them for baryonic physics
calculations. They must still conform to the specified dtype and units if included.
Use the sentinel value noted below when the field is unavailable in the input format.

| Field | dtype | Shape | Units | Sentinel | Description |
| --- | --- | --- | --- | --- | --- |
| `Group_M_Mean200` | float32 | (N,) | 10¹⁰ M☉/h | `0.0` | Mass within the radius enclosing 200 times the mean density |
| `Group_M_TopHat200` | float32 | (N,) | 10¹⁰ M☉/h | `0.0` | Mass within the tophat overdensity radius |
| `SubhaloVelDisp` | float32 | (N,) | km/s | `0.0` | 1D velocity dispersion of the halo |
| `FileNr` | int32 | (N,) | — | `-1` | Index of the source file this halo originated from (multi-file inputs) |

---

## 4. Pointer Field Semantics

### 4.1 Valid Range and Sentinel

- **Valid index**: an integer in `[0, TreeNHalos[X] - 1]`. All pointer fields refer to
  positions within the **same** `Tree<X>` halo array. Cross-tree pointers do not exist.
- **Sentinel**: `-1` indicates the absence of a link. No other negative value is valid.

### 4.2 Temporal Pointer Constraints

- `FirstProgenitor` and `NextProgenitor` of halo `i` must point to halos with a
  `SnapNum` **strictly less than** `SnapNum[i]`. Progenitors are always at an earlier
  snapshot than their descendant.
- `Descendant` of halo `i` must point to a halo with a `SnapNum` **strictly greater
  than** `SnapNum[i]`, or be `-1`.
- A halo may have at most one `Descendant`.
- A halo's `FirstProgenitor` is defined as the progenitor with the largest mass
  (main progenitor branch).

### 4.3 Spatial Pointer Constraints

- `FirstHaloInFOFGroup` and `NextHaloInFOFGroup` of halo `i` must point to halos with
  the **same** `SnapNum` as halo `i`. Spatial pointers never cross snapshot boundaries.
- A halo where `FirstHaloInFOFGroup[i] == i` is the **central halo** of its FOF group.
  All other halos in the group are satellites; their `FirstHaloInFOFGroup` points to the
  central.
- The `NextHaloInFOFGroup` chain starting from `FirstHaloInFOFGroup[i]` visits every
  halo in the FOF group exactly once and terminates with `-1`.

---

## 5. LHaloTree Linking Conventions

### 5.1 Progenitor Chain (temporal traversal)

To walk all progenitors of halo `i`:

```python
p = FirstProgenitor[i]
while p != -1:
    # process progenitor p
    p = NextProgenitor[p]
```

The first step follows `FirstProgenitor` (the main progenitor). Each subsequent step
follows `NextProgenitor` to visit minor mergers at the same snapshot. The chain ends
when `NextProgenitor == -1`.

### 5.2 Descendant Chain (temporal traversal)

To walk forward in time from halo `i`:

```python
d = i
while Descendant[d] != -1:
    d = Descendant[d]
    # process descendant d
```

Each halo has at most one descendant, so this is a simple pointer-follow. When
`Descendant[d] == -1`, `d` is the root halo (the z=0 descendant or the final halo
before the tree terminates).

### 5.3 FOF Group Chain (spatial traversal)

To walk all halos in the FOF group of halo `i` at the same snapshot:

```python
central = FirstHaloInFOFGroup[i]
member = central
while member != -1:
    # process group member
    member = NextHaloInFOFGroup[member]
```

The chain starts at the central halo (which points to itself via `FirstHaloInFOFGroup`)
and walks through all satellites via `NextHaloInFOFGroup`, ending with `-1`.

### 5.4 Unit Conventions

| Quantity | On-disk unit | SAGE internal unit after read |
| --- | --- | --- |
| Masses | 10¹⁰ M☉/h | 10¹⁰ M☉/h |
| Positions (`SubhaloPos`) | **kpc/h** | Mpc/h (× 0.001 applied by reader) |
| Velocities | km/s (physical peculiar) | km/s |
| Specific angular momentum (`SubhaloSpin`) | **(kpc/h)(km/s)** | (Mpc/h)(km/s) (× 0.001 applied by reader) |
| Particle IDs | unitless integer | unitless integer |
| Snapshot indices | unitless integer, zero-based | unitless integer, zero-based |

> **Important**: `SubhaloPos` and `SubhaloSpin` must be stored in **kpc/h** and **(kpc/h)(km/s)** respectively. `read_tree_lhalo_hdf5.c` (`convert_units_for_forest`) unconditionally multiplies both fields by `0.001` after reading. Any driver producing lhalo_hdf5 output must pre-scale these two fields by × 1000 before writing.

---

## 6. Schema Compliance Rules for the Converter

1. Every mandatory field listed in Sections 3.1, 3.2, and 3.3 must be present in every
   `Tree<X>/` group. Missing mandatory fields cause SAGE to abort.
2. All `int32` fields must be stored as HDF5 `H5T_NATIVE_INT32` (or equivalent).
   All `float32` fields must be stored as HDF5 `H5T_NATIVE_FLOAT`. `MostBoundID`
   must be stored as HDF5 `H5T_NATIVE_INT64`.
3. Vector fields (`Pos`, `SubhaloVel`, `SubhaloSpin`) must be stored in row-major
   order with shape `(N, 3)` — i.e., the three components of halo `i` are at
   positions `[i, 0]`, `[i, 1]`, `[i, 2]`.
4. Optional fields use their specified sentinel values when the input format does not
   provide the corresponding data.
5. `Header/TreeNHalos` is a dataset, not an attribute. Its sum must equal `NhalosPerFile`.
