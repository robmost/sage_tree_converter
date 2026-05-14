---
name: semantic-validation
description: Generates the seven mandatory semantic validation plots comparing
             input and converted output merger trees. Use after a full conversion
             run in Stage 3 to assess whether the conversion preserved the physical
             properties of the data.
---

# Semantic Validation

## Instructions

## Path Convention

Two path prefixes are used in this skill:
- **`.ai/skills/semantic-validation/references/<file>`** — files in this skill's own `references/` subfolder.
- **`reference/<file>` (project root)** — files in the project-root `reference/` directory (e.g. `reference/sage_validation.mplstyle`).

This skill is invoked at the start of Stage 3, after the full conversion run completes.
The goal is to produce seven plots that compare the input (unconverted) and output
(converted) merger trees side by side, with a relative difference column.

### 1. Apply the style sheet and load utility functions

Before creating any figure:

```python
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
plt.style.use("reference/sage_validation.mplstyle")  # project root
```

Load the utility functions from `.ai/skills/semantic-validation/assets/plot_utils.py` (relative to this skill folder).
All figure saving and closing must go through `plot_utils.save_figure()`. Do **not**
call `plt.savefig()` or `plt.close()` directly anywhere in the plotting code.

### 2. Sample selection — apply once, use for all plots

1. Open both the input file (original merger tree) and the full conversion output file.

   The output file path depends on the format chosen at G1:
   - HDF5 output:   `output/<base>_STC.0.hdf5`
   - Binary output: `output/<base>_STC.0`

   where `<base>` is the dataset directory name (see AGENTS.md §13 for the derivation rule).

   Pass the appropriate format flags to `generate_all_plots()`:
   ```python
   from validation.semantic import generate_all_plots
   generate_all_plots(
       input_path="<original_input_path>",
       output_path="output/<base>_STC.0[.hdf5]",
       input_format="<see below>",          # format ID of the original input
       output_format="lhalo_hdf5",          # or "lhalo_binary" if binary output was chosen
   )
   ```

   The binary loader normalises `SubhaloPos` (Mpc/h → kpc/h, ×1000) and `SubhaloSpin`
   ((Mpc/h)(km/s) → (kpc/h)(km/s), ×1000) so both columns use equivalent units.

   For the `input_format` parameter:
   - Original input is SAGE LHaloTree HDF5 → `input_format="lhalo_hdf5"`
   - Original input is SAGE LHaloTree binary (e.g. Subfind/Millennium) → `input_format="lhalo_binary"`
   - Original input is any other native format (e.g. AHF ASCII, Rockstar/Consistent Trees ASCII) →
     pass the driver format ID: `input_format="ahf_mergetree_ascii"` or
     `input_format="rockstar_consistent_trees_ascii"`. `generate_all_plots()` will call
     the driver's `read_trees()` function to load the original source data directly.

   **Never** pass the Stage 2 test conversion output as `input_path` for ASCII or
   native binary formats — always point `input_path` to the original source and set
   `input_format` to the driver format ID so `read_trees()` loads the raw data.
2. Identify the lowest-redshift snapshot: the snapshot with `SnapNum == max(SnapNum)`
   across all trees.
3. At that snapshot, collect all halos with `Group_M_Crit200 > 0`. **Exclude** halos
   with `Group_M_Crit200 <= 0` before any sampling.
4. For the 3×3 evolution plots, select three mass bins from the surviving halos:
   - **Top-5**: 5 trees ranked by the **maximum** `Group_M_Crit200` across all their
     root halos at the lowest-redshift snapshot.
   - **Median-5**: 5 trees nearest the median of that per-tree maximum mass.
   - **Bottom-5**: 5 trees with the lowest per-tree maximum mass (still > 0).

   A tree may have **multiple root halos** (e.g. CTrees forest mode combines many
   `#tree` blocks into one SAGE tree, each contributing its own `Descendant == -1`
   halo at the final snapshot). When walking the progenitor branch for the evolution
   plots, always use the **most massive root** — `roots[argmax(Group_M_Crit200[roots])]`
   — not `roots[0]`. Using the first root selects an arbitrary satellite sub-tree
   and produces flat-zero merger rates even for cluster-mass forests.
5. **Use the exact same tree indices** for both the input and output columns. Never
   sample input and output independently.

### 3. Generate the seven plots

Read `.ai/skills/semantic-validation/references/plot_specifications.md` for per-plot axis specs, layout, and
filtering rules.

| # | Filename | Layout | X axis | Y axis | Mass bin rows |
| - | -------- | ------ | ------ | ------ | ------------- |
| 1 | `mah.pdf` | 3×3 | `SnapNum` | `Group_M_Crit200` | Yes |
| 2 | `merger_rate.pdf` | 3×3 | `SnapNum` | Number of progenitors | Yes |
| 3 | `angular_momentum.pdf` | 3×3 | `SnapNum` | `\|SubhaloSpin\|` | Yes |
| 4 | `hmf.pdf` | 1×3 | `Group_M_Crit200` | Count | No |
| 5 | `velocity_dist.pdf` | 1×3 | `\|SubhaloVel\|` | Count | No |
| 6 | `lifespan_dist.pdf` | 1×3 | Snapshots tracked | Count | No |
| 7 | `spatial_dist.pdf` | 1×3 | X position | Y position (hexbin) | No |

Column layout for all plots:
- **Column 1** (left): input (unconverted) data
- **Column 2** (centre): output (converted) data
- **Column 3** (right): relative difference `(output - input) / input`

See `.ai/skills/semantic-validation/references/relative_difference.md` for the exact relative difference formula,
axis label, and colour scale requirements.

### 4. Tree-walking constraint

All traversal of the progenitor chain (for evolution plots) must be **O(N)**.
The correct pattern using `FirstProgenitor` and `NextProgenitor`:

```python
p = FirstProgenitor[i]
while p != -1:
    # process progenitor p
    p = NextProgenitor[p]
```

See `.ai/skills/semantic-validation/references/on_tree_walking.md` for the full O(N) pattern library.

**Flag and refuse to proceed** if any tree-walking loop is O(N²) (i.e. any nested
loop that iterates over halos for each halo). Fix it before generating plots.

### 5. Save all plots

Save each plot to `assets/semantic_validation/<filename>`. Create the directory first:

```python
import os
os.makedirs("assets/semantic_validation", exist_ok=True)
```

Use `plot_utils.save_figure(fig, "assets/semantic_validation/<filename>")` for all plots.

After all seven plots are saved, invoke the `auditor` skill. Do not present results
to the user until the auditor has issued its verdict.

### 6. Explicit prohibitions

The following errors have occurred in past sessions and are explicitly forbidden:

1. **Do not** use the converted output data in the input (left) column.
2. **Do not** plot `SubhaloVMax` as the velocity distribution — use the modulus of
   `SubhaloVel` (`|SubhaloVel| = sqrt(Vx² + Vy² + Vz²)`).
3. **Do not** plot the dimensionless spin parameter λ as specific angular momentum —
   use `|SubhaloSpin|` (the magnitude of the specific angular momentum vector).
4. **Do not** call `plt.savefig()` or `plt.close()` directly — use `plot_utils.save_figure()`.
5. **Do not** use different halo samples for the input and output columns.
6. **Do not** begin Stage 3 without first ensuring the full conversion run completed
   successfully (output file exists and passes Check 1 file integrity).
7. **Do not** use O(N²) tree-walking — every progenitor traversal must use the
   `FirstProgenitor`/`NextProgenitor` linked-list pattern.
8. **Do not** rely on a single global `plt.style.use()` call to cover all figures.
   Each `_plot_*` function must call `plt.style.use("reference/sage_validation.mplstyle")` (project root)
   at its own start, because matplotlib resets style state between figures in
   non-interactive (Agg) mode. The style must also be applied before the global call
   in the main script, but that alone is not sufficient.
9. **Do not** omit the colorbar from the relative-difference column of the spatial
   distribution plot. The hexbin relative-difference panel must include a `plt.colorbar()`
   with a label (e.g. `"(out − in) / in"`) so the scale is visible.
10. **Do not** use the Stage 2 test conversion output as the `input_path` reference for
    ASCII or native binary input formats. Always point `input_path` to the original
    source data and pass the driver format ID as `input_format` (e.g.
    `input_format="ahf_mergetree_ascii"`). Using converted data in both columns
    defeats the purpose of semantic validation.
11. **Do not** use `roots[0]` to select the root halo for evolution plot traversal.
    Always use the most massive root: `roots[np.argmax(tree["Group_M_Crit200"][roots])]`.
    Using the first root produces flat-zero merger rates for any format that combines
    multiple sub-trees into one SAGE tree (e.g. CTrees forest mode).
