# Gadget-4 HDF5 Conversion Example

**User:** "I've run a new custom simulation with Gadget-4. Can you convert the `trees.hdf5` I put in `input/custom_gadget4/`?"

**Assistant:**
I've found your Gadget-4 HDF5 file. I'll execute the initial discovery steps.

## STATE 1: Initialization & Discovery

- **Files Found:** `input/custom_gadget4/trees.hdf5`.
- **Database Match:** Checked `format-database/` and found match for Gadget-4.

**Identification Result:**

```json
{
  "file_format": "HDF5",
  "halo_finder": "Subfind",
  "tree_tool": "Gadget-4 Tree Builder",
  "status": "Match Found (hdf5_gadget4)"
}
```

Moving to Analysis.

## STATE 2: Analysis Report

The file uses Gadget-4's native tree format, storing halos in the `TreeHalos` group and tree offsets in `TreeTable`.

| Gadget-4 Field (Source) | SAGE Field (Target) | Units |
| :--- | :--- | :--- |
| `SubhaloMass` | **Mvir** | $10^{10} M_\odot/h$ |
| `SubhaloPos` | **Pos** | Mpc/h (comoving) |
| `TreeFirstProgenitor` | **FirstProgenitor** | Absolute Index (in TreeHalos) |
| `TreeDescendant` | **Descendant** | Absolute Index (in TreeHalos) |

**Intended Validation Checklist:**
I will validate the output physically by generating the following 7 mandatory plots:

1. `mah` (Evolution)
2. `merger_rate` (Evolution)
3. `spin` (Evolution)
4. `velocity` (Histogram)
5. `lifespan` (Histogram)
6. `hmf` (Histogram)
7. `spatial` (Hexbin)

**Proposed Next Step:**
I need your **EXPLICIT APPROVAL** over this mapping and checklist. If approved, I will process a small test sample and perform native validation checks (no plots).

**User:** "Approved. Yes, those are standard Gadget-4 outputs. Please proceed."

**Assistant:**
Understood. Moving to State 3.

## STATE 3: Test Engine

I am generating the required parsing scripts and running the test conversion on the first set of trees.

**Test Results:**

- **Output:** `output/0_test_sage_tree_gadget4.hdf5`
- **Validation:** Executed syntactic checks successfully. All absolute indices pointing within `TreeHalos` resolved nicely as test sample pointers. Mass bounds evaluate within physical bounds.
*(Note: No validation plots are generated during the small test conversion phase).*

Moving to State 4.

## STATE 4: Full Suite & Export

Processing all 2.45 million halos natively.

**Final Conversion Results:**

- **Primary Data Output:** `output/0_full_sage_tree_gadget4.hdf5`
- **Validation Log:** Recorded to `output/0_validation_log_gadget4.md` using the standard markdown template.
- **Validation Plots:**
  - `output/1_validation_mah_gadget4.png`
  - `output/1_validation_merger_rate_gadget4.png`
  - `output/1_validation_spin_gadget4.png`
  - `output/1_validation_velocity_gadget4.png`
  - `output/1_validation_lifespan_gadget4.png`
  - `output/1_validation_hmf_gadget4.png`
  - `output/1_validation_spatial_gadget4.png`
- **Cleanup:** Transient CLI parsing scripts moved to `output/audit-logs/gadget4_scripts/`.

Conversion complete. The full dataset is ready.
