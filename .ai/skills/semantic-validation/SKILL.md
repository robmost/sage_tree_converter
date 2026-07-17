---
name: semantic-validation
description: Generates the seven mandatory semantic validation plots of the
             converted output merger trees. Use after a full conversion run in
             Stage 3 to assess whether the converted trees are physically plausible.
---

# Semantic Validation

## Instructions

## Stage Preamble

If the Stage 3 preamble has not already been output this session, output it now, verbatim, from AGENTS.md Section 15. Never re-output a preamble that has already been shown, and never paraphrase it.

## Path Convention

Two path prefixes are used in this skill:
- **`.ai/skills/semantic-validation/references/<file>`** - files in this skill's own `references/` subfolder.
- **`reference/<file>` (project root)** - files in the project-root `reference/` directory (e.g. `reference/sage_validation.mplstyle`).

This skill is invoked at the start of Stage 3, after the full conversion run completes.
The goal is to produce seven **output-only** plots of the converted merger trees -
absolute physical-plausibility diagnostics of the conversion result.

These plots are **not** a differential test of the conversion logic: the converter
cannot be validated against itself (the only independent reference would be a second,
separately-derived conversion). Conversion-logic correctness is established by the G1
schema-mapping review, syntactic validation, and functional (SAGE dry-run) validation.
Semantic validation answers a different question: *are the converted trees physically
sensible?*

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

### 2. Generate the plots

Run the CLI wrapper on the **converted output file** (there is no input column):

```bash
$PYTHON_BIN scripts/run_semantic_plots.py \
    --file output/<base>_STC.0.hdf5 \
    --output-format lhalo_hdf5
# Binary output: --file output/<base>_STC.0 --output-format lhalo_binary
# <base> comes from assets/session_state.json (AGENTS.md sections 13 and 17).
```

The wrapper applies the style sheet, calls `generate_all_plots()` from
`conversion-engine/validation/semantic.py`, and exits non-zero unless all
seven plots are produced. Do not re-implement the plotting inline.

`generate_all_plots()` handles the sampling internally:
1. Identifies the lowest-redshift snapshot (`SnapNum == max(SnapNum)` across all trees).
2. At that snapshot, collects all halos with `Group_M_Crit200 > 0` (excludes `<= 0`).
3. For the per-mass-bin evolution plots, selects three bins by per-tree maximum root mass:
   **Top-5**, **Median-5**, **Bottom-5**.
4. When walking a tree's progenitor branch it uses the **most massive root**
   (`roots[argmax(Group_M_Crit200[roots])]`), not `roots[0]` - a tree may have multiple
   `Descendant == -1` roots (e.g. CTrees forest mode), and the first is an arbitrary
   satellite sub-tree that produces flat-zero merger rates.

The binary loader normalises `SubhaloPos` (Mpc/h -> kpc/h, x1000) and `SubhaloSpin`
((Mpc/h)(km/s) -> (kpc/h)(km/s), x1000) so plotted units are consistent regardless of
output format.

### 3. The seven plots

Read `.ai/skills/semantic-validation/references/plot_specifications.md` for per-plot axis specs, layout, and
filtering rules.

| # | Filename | Layout | X axis | Y axis | Mass bin rows |
| - | -------- | ------ | ------ | ------ | ------------- |
| 1 | `mah.pdf` | 3x1 | `SnapNum` | `Group_M_Crit200` | Yes |
| 2 | `merger_rate.pdf` | 3x1 | `SnapNum` | Number of progenitors | Yes |
| 3 | `angular_momentum.pdf` | 3x1 | `SnapNum` | `\|SubhaloSpin\|` | Yes |
| 4 | `hmf.pdf` | 1x1 | `Group_M_Crit200` | Count | No |
| 5 | `velocity_dist.pdf` | 1x1 | `\|SubhaloVel\|` | Count | No |
| 6 | `lifespan_dist.pdf` | 1x1 | Snapshots tracked | Count | No |
| 7 | `spatial_dist.pdf` | 1x1 | X position | Y position (hexbin) | No |

Each plot shows the converted output only. The per-mass-bin plots (1-3) use one row per
bin (Top/Median/Bottom-5); the distribution plots (4-7) are single panels.

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

**Flag and refuse to proceed** if any tree-walking loop is O(N^2) (i.e. any nested
loop that iterates over halos for each halo). Fix it before generating plots.

### 5. Save all plots

Plots are saved to `assets/semantic_validation/<filename>` (the directory is created
automatically). Each `_plot_*` function saves via `plot_utils.save_figure()`.

After all seven plots are saved, invoke the `auditor` skill. Do not present results
to the user until the auditor has issued its verdict.

### 6. Explicit prohibitions

The following errors have occurred in past sessions and are explicitly forbidden:

1. **Do not** plot `SubhaloVMax` as the velocity distribution - use the modulus of
   `SubhaloVel` (`|SubhaloVel| = sqrt(Vx^2 + Vy^2 + Vz^2)`).
2. **Do not** plot the dimensionless spin parameter lambda as specific angular momentum -
   use `|SubhaloSpin|` (the magnitude of the specific angular momentum vector).
3. **Do not** call `plt.savefig()` or `plt.close()` directly - use `plot_utils.save_figure()`.
4. **Do not** begin Stage 3 without first ensuring the full conversion run completed
   successfully (output file exists and passes Check 1 file integrity).
5. **Do not** use O(N^2) tree-walking - every progenitor traversal must use the
   `FirstProgenitor`/`NextProgenitor` linked-list pattern.
6. **Do not** rely on a single global `plt.style.use()` call to cover all figures.
   Each `_plot_*` function must call `plt.style.use("reference/sage_validation.mplstyle")` (project root)
   at its own start. This is defence in depth: it keeps every plot function
   self-contained and correctly styled even when called in isolation or after
   other code has changed rcParams. The global call in the main script is still
   applied first, but is not sufficient on its own.
7. **Do not** use `roots[0]` to select the root halo for evolution plot traversal.
   Always use the most massive root: `roots[np.argmax(tree["Group_M_Crit200"][roots])]`.
   Using the first root produces flat-zero merger rates for any format that combines
   multiple sub-trees into one SAGE tree (e.g. CTrees forest mode).
