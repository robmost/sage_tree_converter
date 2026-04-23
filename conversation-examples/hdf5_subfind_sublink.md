# SubLink HDF5 Conversion Example

**User:** "I have the core IllustrisTNG HDF5 outputs. They contain Subfind structures linked via SubLink. Convert them please."

**Assistant:**
Reviewing the `.hdf5` groups in the payload.

## STATE 1: Initialization & Discovery

**Step 1 — Directory Scan & Size Audit:**

```shell
ls -lh input/illustris_tng/
# sublink_merger_tree_extended.0.hdf5   (8.3 GB)
# sublink_merger_tree_extended.1.hdf5   (7.9 GB)
# sublink_merger_tree_extended.2.hdf5   (8.1 GB)
# ...
```

Files exceed 100 MB each — user will be warned before full-dataset processing. All reads restricted to structural inspection only.

**Step 2 — Bounded HDF5 Group/Attribute Peek (no array data loaded):**

```python
# Incremental: inspect root attributes and top-level group names only
import h5py
with h5py.File("input/illustris_tng/sublink_merger_tree_extended.0.hdf5", "r") as f:
    print(dict(f.attrs))        # {'NumTrees': 4096, 'Redshift': 0.0}
    print(list(f.keys()))       # ['Subhalo', 'Group']
    print(list(f["Subhalo"].keys())[:5])  # ['SubhaloMass', 'SubhaloPos', 'FirstProgenitorID', ...]
# SubLink structure confirmed from 'Subhalo'/'Group' group names and 'FirstProgenitorID' dataset.
# Reading stopped — no array data was loaded.
```

**Step 3 — Database Lookup:**

- **Database Match:** Located exact specification in `format-database/hdf5_subfind_sublink.json`.

**Completeness Check:**
The `Subhalo` and `Group` subtrees have been structurally verified from the key scan.

> [!WARNING]
> Multiple chunks totalling > 24 GB detected. Full-dataset conversion will require chunked streaming. Explicit user authorization will be requested before STATE 4 execution.

## STATE 2: Analysis Report

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

## STATE 3: Test Engine

Executing sequential bounds check targeting a small volume sample.

**Test Results:**

- **Output:** `output/0_test_sage_tree_illustris.hdf5`
- **Validation:** Passed syntax and physical threshold analyses successfully via native assertions. Memory bounds checked adequately.
*(No semantic plots are dumped during the test sweep state).*

Transitioning to State 4.

## STATE 4: Full Suite & Export

**Assistant:** "I will now write the validation script. I will ensure I read the raw input, map the OriginalIDs, and use `sage_validation_utils.py` for all plotting to compare against the output. I will process the raw arrays to match the utility function inputs."

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
