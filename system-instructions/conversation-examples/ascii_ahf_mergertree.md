# AHF Multi-Snapshot ASCII Conversion Example

**User:** "I have AHF halo catalogues for 3 snapshots and the corresponding MergerTree files. Can you convert them to a SAGE tree?"

**Assistant:**
I've found your AHF data in the `input/` directory.

## STATE 1: Initialization & Discovery

- **Files Found:** `snap_014.AHF_halos`, `snap_015.AHF_halos`, `snap_016.AHF_halos`, and `snap_015_mtree`, `snap_016_mtree`.
- **Database Match:** Checked `format-database/ascii_ahf_mergertree.json`. The primitives map correctly.

**Completeness Check:**
The snapshots and temporal link files are available. I will proceed with formulating the analysis report.

## STATE 2: Analysis Report

AHF files require specific unit scaling and complex pointer resolution across potentially non-sequential snapshots.

| AHF Field (Source) | SAGE Field (Target) | Action |
| :--- | :--- | :--- |
| `Mhalo(4)` | **Mvir** | Scale by $10^{10}$ |
| `Xc(6), Yc(7), Zc(8)` | **Pos** | kpc/h $\rightarrow$ Mpc/h |
| `VXc(9), VYc(10), VZc(11)` | **Vel** | Direct Copy (km/s) |
| `_mtree` (Block Structure) | **Descendant** | Map IDs via Global ID Database |

**Intended Validation Checklist:**
I will validate the output physically by generating the 7 mandatory plots natively required for this conversion:

1. `mah` (Evolution)
2. `merger_rate` (Evolution)
3. `spin` (Evolution)
4. `velocity` (Histogram)
5. `lifespan` (Histogram)
6. `hmf` (Histogram)
7. `spatial` (Hexbin)

**Proposed Next Step:**
I need your **EXPLICIT APPROVAL** over this mapping and checklist before writing conversion code. Once approved, I will process a small test sample and perform native validation checks.

**User:** "Approved. Yes, this mapping looks good."

**Assistant:**
Understood. Moving to State 3.

## STATE 3: Test Engine

I am generating `assets/cli-scripts/ahf_test_conversion.py` and running the test conversion on a subset of the dataset.

**Test Results:**

- **Output:** `output/0_test_sage_tree_ahf.hdf5`
- **Validation:** Executed syntactic and native semantic checks successfully.
  - Syntactic Integrity: Pointer resolutions verified for test halos.
  - Semantic Integrity: Ranges for mass and positions are within physical bounds.

*(Note: As per State 3 protocol, no validation plots were generated during this test pass).*

Moving to State 4 for full suite execution.

## STATE 4: Full Suite & Export

Processing the entire 3 snapshot dataset.

**Final Conversion Results:**

- **Primary Data Output:** `output/0_full_sage_tree_ahf.hdf5`
- **Validation Log:** Recorded to `output/0_validation_log_ahf.md` following the strict `validation_log_style.md` standard.
- **Validation Plots:**
  - `output/1_validation_mah_ahf.png`
  - `output/1_validation_merger_rate_ahf.png`
  - `output/1_validation_spin_ahf.png`
  - `output/1_validation_velocity_ahf.png`
  - `output/1_validation_lifespan_ahf.png`
  - `output/1_validation_hmf_ahf.png`
  - `output/1_validation_spatial_ahf.png`
- **Cleanup:** Unused CLI scripts have been archived to `output/audit-logs/ahf_scripts/`.

The conversion is complete. You can inspect the final dataset and validation log in the `output/` directory.
