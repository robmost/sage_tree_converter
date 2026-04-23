# Millennium Binary Conversion Example

**User:** "I've uploaded the mini-millennium trees to the `input/mini-millenium/` folder. Can you convert them for me?"

**Assistant:**
I've found the files in `input/mini-millenium/`.

## STATE 1: Initialization & Discovery

**Step 1 — Directory Scan & Size Audit:**

```shell
ls -lh input/mini-millenium/
# trees_063.0  (2.1 GB)
# trees_063.1  (1.8 GB)
# trees_063.2  (940 MB)
# ...
```

Files are large (> 100 MB each). All subsequent reads will use bounded operations only.

**Step 2 — Bounded Binary Peek (first file only):**

```python
# Incremental: read only the 8-byte header to confirm endianness and ntrees
with open("input/mini-millenium/trees_063.0", "rb") as f:
    ntrees = np.frombuffer(f.read(4), dtype=np.int32)[0]
    tot_nhalos = np.frombuffer(f.read(4), dtype=np.int32)[0]
# ntrees=5120, tot_nhalos=3245800 — LHaloTree binary header confirmed.
# Reading stopped — no further file content was loaded.
```

**Step 3 — Database Lookup:**

- **Database Match:** Checked `format-database/binary_subfind_lhalotree.json` — exact match confirmed.

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

## STATE 2: Analysis Report

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

## STATE 3: Test Engine

I am generating the binary structure map and running the conversion on the first 10 trees from `trees_063.0`.

**Test Results:**

- **Output:** `output/0_test_sage_tree_mini-millennium.hdf5`
- **Validation:**
  - Syntactic Check: Pointer integrity 100% valid within the file structure.
  - Semantic Check: Variables fall within typical distribution bounds naturally.

*(Note: Plot generation skips this phase, per validation protocols).*

Moving to State 4.

## STATE 4: Full Suite & Export

**Assistant:** "I will now write the validation script. I will ensure I read the raw input, map the OriginalIDs, and use `sage_validation_utils.py` for all plotting to compare against the output. I will process the raw arrays to match the utility function inputs."

Processing the entire mini-millennium dataset.

**Final Conversion Results:**

- **Primary Data Output:** `output/0_full_sage_tree_mini-millennium.hdf5`
- **Validation Log:** Saved to `output/0_validation_log_mini-millennium.md`.
- **Validation Plots:**
  - `output/1_validation_mah_mini-millennium.png`
  - `output/1_validation_merger_rate_mini-millennium.png`
  - `output/1_validation_spin_mini-millennium.png`
  - `output/1_validation_velocity_mini-millennium.png`
  - `output/1_validation_lifespan_mini-millennium.png`
  - `output/1_validation_hmf_mini-millennium.png`
  - `output/1_validation_spatial_mini-millennium.png`
- **Cleanup:** Testing binaries pushed to `output/audit-logs/mini-millennium_20231027_101530_scripts/`.

The data is fully compiled and ready for SAGE integration.

## STATE 5: Post-Conversion Knowledge Base Update

**Assistant:** "Was the conversion satisfactory?"

**User:** "Yes, all 7 plots look accurate."

**Assistant:** "Would you like to update the format-database with hints for future conversions? \[y/N\]"

**User:** "No thanks."

**Assistant:** "Understood. The session is complete."
