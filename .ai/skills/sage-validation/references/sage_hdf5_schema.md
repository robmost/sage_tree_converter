# SAGE Format Schema Template

This document defines the strict structural schema that all converter tools MUST follow when generating SAGE-compliant HDF5 or Binary files. It maps directly to SAGE's internal `halo_data` C-struct.

## 1. Binary Format Rules

If outputting a SAGE-compliant Binary format, the file MUST consist of:

1. **Header**:
   - `ntrees` (int32)
   - `tot_nhalos` (int32)
   - `tree_nhalos` (int32 array of length `ntrees`)
2. **Halo Blocks**:
   - A contiguous array of exactly `tot_nhalos` elements.
   - Each element MUST be exactly **104 bytes** and conform to the standard LHaloTree struct (see HDF5 Field Definitions below for the exact ordering and types).

## 2. HDF5 Format Rules

### 2.1. Root Attributes

- `Ntrees` (int32 or int64): Total number of trees in the file.

- `TotNHalos` (int32 or int64): Total number of halos across all trees in the file.

### 2.2. Root Datasets

- `TreeNHalos` (1D array of int32): Number of halos in each tree. Its length must equal `Ntrees`.

### 2.3. Tree Groups (`/Tree<X>/`)

- The schema MUST support multiple Tree groups. Instead of a monolithic `/Tree0/` group, simulations with distinct, independent trees should partition data into `/Tree0/`, `/Tree1/`, ..., `/TreeN/` as appropriate.

- The datasets inside each `/Tree<X>/` group MUST use the **LHaloTree naming convention** defined below.

> [!IMPORTANT]
> SAGE supports multiple naming conventions natively (e.g., Gadget4 variants like `TreeDescendant`). However, to ensure consistency across the converter's ecosystem, you MUST standardise the output using the **LHaloTree naming convention** below.

### 2.4. Field Definitions (The LHaloTree Convention)

All fields below exist in the native SAGE `halo_data` memory struct. However, during HDF5 conversion, some fields are critical for baryonic physics, while others are legacy structural artifacts.

#### MANDATORY Fields

These datasets MUST be present in the HDF5 group. If the input simulation format lacks them, they MUST be synthesised according to the rules in `core-knowledge.md` before writing.

**Merger Tree Pointers (int32):**

- `Descendant`
- `FirstProgenitor`
- `NextProgenitor`
- `FirstHaloInFOFgroup`
- `NextHaloInFOFgroup`

**Physics & Kinematics:**

- `Mvir` (float32): Primary virial mass.
- `Pos` (float32, shape `[N, 3]`): Position vector.
- `Vel` (float32, shape `[N, 3]`): Velocity vector.
- `Vmax` (float32): Maximum circular velocity.
- `VelDisp` (float32): Velocity dispersion.
- `Spin` (float32, shape `[N, 3]`): Spin vector.

**Temporal Indexing:**

- `SnapNum` (int32): Snapshot number.

#### OPTIONAL Fields

These datasets map to legacy fields in the `halo_data` struct. They are generally ignored by SAGE's core physics but may be read depending on the parser. If the input simulation has equivalent data, write it. If absent, they can be omitted from the HDF5 or filled with dummy values (-1 or 0.0).

- `Len` (int32): Number of particles in the halo.
- `M_Mean200` (float32): Mass within 200 times the mean density.
- `M_Crit200` (float32): Mass within 200 times the critical density.
- `M_TopHat` (float32): Top-hat virial mass.
- `MostBoundID` (int64): ID of the most bound particle.
- `FileNr` (int32): Original file number in the simulation.
- `SubhaloIndex` (int32): Index of the subhalo.
- `SubHalfMass` (float32): Half-mass radius/mass.
