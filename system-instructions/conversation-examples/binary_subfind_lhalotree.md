# Millennium Binary Conversion Example

**User:** "I've uploaded the mini-millennium trees to the `input/mini-millenium/` folder. Can you convert them for me?"

**Assistant:**
I've found the files in `input/mini-millenium/`.

### STATE 1: Initialization & Discovery

- **Files Found:** Multiple files starting with `trees_063`.
- **Database Match:** Checked `format-database/binary_subfind_lhalotree.json`.

**Identification Result:**

```json
{
  "file_format": "Binary",
  "halo_finder": "Subfind",
  "tree_tool": "LHaloTree",
  "status": "Match Found (binary_subfind_lhalotree)"
}
```

Moving to Analysis.

### STATE 2: Analysis Report

The files use the **LHaloTree** binary format. This is the native format SAGE was originally designed for, so the mapping is direct.

| SAGE Field | Binary Struct Member | Type | Units |
| :--- | :--- | :--- | :--- |
| **Mvir** | `M_TopHat` | float32 | $10^{10} M_\odot/h$ |
| **Pos** | `Pos[3]` | float32 | Mpc/h (comoving) |
| **Vel** | `Vel[3]` | float32 | km/s (physical) |
| **Pointers** | `FirstProgenitor`, etc. | int32 | Relative Index |

**Intended Validation Checklist:**
I will validate the physical parameters by generating the mandatory 7 plots:

1. `mah` (Evolution)
2. `merger_rate` (Evolution)
3. `spin` (Evolution)
4. `velocity` (Histogram)
5. `lifespan` (Histogram)
6. `hmf` (Histogram)
7. `spatial` (Hexbin)

**Proposed Next Step:**
I need your **EXPLICIT APPROVAL** to proceed with this mapping and perform the native test validation (which will check Little-Endian assumptions).

**User:** "Approved. Yes, that's correct."

**Assistant:**
Understood. Moving to State 3.

### STATE 3: Test Engine

I am generating the binary structure map and running the conversion on the first 10 trees from `trees_063.0`.

**Test Results:**

- **Output:** `output/0_test_sage_tree_minimillennium.hdf5`
- **Validation:**
  - Syntactic Check: Pointer integrity 100% valid within the file structure.
  - Semantic Check: Variables fall within typical distribution bounds naturally.

*(Note: Plot generation skips this phase, per validation protocols).*

Moving to State 4.

### STATE 4: Full Suite & Export

Processing the entire mini-millennium dataset.

**Final Conversion Results:**

- **Primary Data Output:** `output/0_full_sage_tree_minimillennium.hdf5`
- **Validation Log:** Saved to `output/0_validation_log_minimillennium.md`.
- **Validation Plots:**
  - `output/1_validation_mah_minimillennium.png`
  - `output/1_validation_merger_rate_minimillennium.png`
  - `output/1_validation_spin_minimillennium.png`
  - `output/1_validation_velocity_minimillennium.png`
  - `output/1_validation_lifespan_minimillennium.png`
  - `output/1_validation_hmf_minimillennium.png`
  - `output/1_validation_spatial_minimillennium.png`
- **Cleanup:** Testing binaries pushed to `output/audit-logs/minimillennium_scripts/`.

The data is fully compiled and ready for SAGE integration.
