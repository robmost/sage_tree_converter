# SubLink HDF5 Conversion Example

**User:** "I have the core IllustrisTNG HDF5 outputs. They contain Subfind structures linked via SubLink. Convert them please."

**Assistant:**
Reviewing the `.hdf5` groups in the payload.

### STATE 1: Initialization & Discovery

- **Files Found:** Valid TNG output chunks.
- **Database Match:** Located exact specification in `format-database/hdf5_subfind_sublink.json`.

**Completeness Check:**
The `Subhalo` and `Group` subtrees have been structurally verified.

### STATE 2: Analysis Report

TNG utilizes FOF-based Halo Finder methodologies coupled with Pointer-based linking logic in SubLink.

| SubLink Field (Source) | SAGE Field (Target) | Scale / Notes |
| :--- | :--- | :--- |
| `SubhaloMass` | **Mvir** | Multiply by $10^{10}$ |
| `SubhaloPos` | **Pos** | ckpc/h |
| `SubhaloVel` | **Vel** | km/s |
| `FirstProgenitorID` | **FirstProgenitor** | Pointer Parity Map Integration |

Additional FOF grouping logic dictates sequential subhalos within the same `GroupNr` correspond to `NextHaloInFOFgroup` arrays natively within SAGE structures.

**Intended Validation Checklist:**
I will map the outputs physically onto these 7 mandatory plots:

1. `mah` (Evolution)
2. `merger_rate` (Evolution)
3. `spin` (Evolution)
4. `velocity` (Histogram)
5. `lifespan` (Histogram)
6. `hmf` (Histogram)
7. `spatial` (Hexbin)

**Proposed Next Step:**
Do I have your **EXPLICIT APPROVAL** on this mapping methodology and full validation framework checklist?

**User:** "Yes, approved."

**Assistant:**
Understood. Progressing to State 3.

### STATE 3: Test Engine

Executing sequential bounds check targeting a small volume sample.

**Test Results:**

- **Output:** `output/0_test_sage_tree_illustris.hdf5`
- **Validation:** Passed syntax and physical threshold analyses successfully via native assertions. Memory bounds checked adequately.
*(No semantic plots are dumped during the test sweep state).*

Transitioning to State 4.

### STATE 4: Full Suite & Export

Conducting batch conversion across all HDF5 volume chunks.

**Final Conversion Results:**

- **Primary Data Output:** `output/0_full_sage_tree_illustris.hdf5`
- **Validation Log:** Written to `output/0_validation_log_illustris.md`.
- **Validation Plots:**
  - `output/1_validation_mah_illustris.png`
  - `output/1_validation_merger_rate_illustris.png`
  - `output/1_validation_spin_illustris.png`
  - `output/1_validation_velocity_illustris.png`
  - `output/1_validation_lifespan_illustris.png`
  - `output/1_validation_hmf_illustris.png`
  - `output/1_validation_spatial_illustris.png`
- **Cleanup:** H5py helper mapping scripts have been pushed from `cli-scripts` to `output/audit-logs/illustris_scripts/`.

Complete. Have a nice day.
