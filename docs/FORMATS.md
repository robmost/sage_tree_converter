# Supported Formats and Technical Specifications

The SAGE Universal Converter is designed around **primitives** (File Format, Halo Finder, Tree Tool). Below are the specifications for the currently supported tool-chains.

## 1. ASCII AHF + MergerTree

- **Drivers:** `ascii_ahf_mergertree_driver.py`
- **Logic:** Custom ASCII parsing of `.AHF_halos` (spatial) and `_mtree` (temporal).
- **Snapshot Skipping:** Fully supported via a Global ID Database.
- **Unit Conversions:**
  - Mass: $M_\odot/h \rightarrow 10^{10} M_\odot/h$
  - Position: $kpc/h \rightarrow Mpc/h$ (comoving)
  - Velocity: Physical $km/s$

## 2. Binary SUBFIND + LHaloTree

- **Drivers:** `binary_subfind_lhalotree_driver.py`
- **Logic:** Fixed-width C-struct reading. Matches the original Millennium database schema.
- **Pointers:** Array-index based (file-relative).
- **Unit Conversions:**
  - Mass: Already in $10^{10} M_\odot/h$.
  - Position: Comoving $Mpc/h$.

## 3. HDF5 Gadget-4 Native

- **Drivers:** `hdf5_gadget4_driver.py`
- **Logic:** Reads Gadget-4's hierarchical HDF5 structure.
- **Pointers:** Absolute indices within the `TreeHalos` dataset.
- **Unit Conversions:** Matches Gadget internal units (typically $10^{10} M_\odot/h$ and $Mpc/h$).

## 4. ASCII Rockstar + ConsistentTrees

- **Drivers:** `ascii_rockstar_consistenttrees_driver.py`
- **Logic:** Columnar parsing of `tree_*.dat` files.
- **Unit Conversions:**
  - Mass: $M_\odot/h$ (mapped to `Mvir`).
  - Position: Comoving $Mpc/h$.

---

## Technical Mapping Requirements for SAGE

Any new format added to the database must eventually map to these mandatory SAGE fields:

| Target Field | Physical Meaning | Required Units |
| :--- | :--- | :--- |
| `Mvir` | Virial Mass | $10^{10} M_\odot/h$ |
| `Pos[3]` | Comoving Position | $Mpc/h$ |
| `Vel[3]` | Peculiar Velocity | $km/s$ |
| `Vmax` | Max Circular Velocity | $km/s$ |
| `Descendant` | Forward Pointer | Index or ID |
| `FirstProgenitor` | Main Progenitor Pointer | Index or ID |
| `SnapNum` | Snapshot Number | Integer |
