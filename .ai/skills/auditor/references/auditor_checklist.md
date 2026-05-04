# Auditor Checklist

13-item checklist for the independent audit of semantic validation plots and code.
Each item has an explicit PASS condition. Any deviation from the PASS condition is a FAIL.

---

| # | Item | PASS condition |
| - | ---- | -------------- |
| 1 | mplstyle applied before first figure | `plt.style.use("reference/sage_validation.mplstyle")` is called before any `plt.subplots()` or `plt.figure()` call in the plotting code. |
| 2 | Same halo sample for input and output | The same set of tree indices is used to select halos from both the input file and the output file. There is no separate sampling call for input vs. output. |
| 3 | Halos with mass ≤ 0 excluded before sampling | Before selecting mass bins or computing distributions, halos with `Group_M_Crit200 <= 0` at the lowest-redshift snapshot are filtered out. No such halo appears in any plot. |
| 4 | MAH uses Group_M_Crit200 | The mass accretion history (mah.pdf) plots `Group_M_Crit200` on the y axis. It does not use `Group_M_Mean200`, `Group_M_TopHat200`, or any other mass field. |
| 5 | Velocity distribution uses SubhaloVel modulus | velocity_dist.pdf plots the magnitude `sqrt(Vx² + Vy² + Vz²)` of `SubhaloVel`. It does not plot `SubhaloVMax` or any component of `SubhaloVel` individually. |
| 6 | Angular momentum uses SubhaloSpin vector magnitude | angular_momentum.pdf plots `\|SubhaloSpin\| = sqrt(Jx² + Jy² + Jz²)`. It does not plot the dimensionless spin parameter λ or any scalar spin field. |
| 7 | Relative difference correctly computed and labelled | The third column of every plot shows `(output - input) / input`. The y-axis label reads "(output − input) / input" (or equivalent). A horizontal dashed line at y=0 is present on every relative difference panel. |
| 8 | All 7 plots present in assets/semantic_validation/ | The following files all exist and are non-empty: `mah.pdf`, `merger_rate.pdf`, `angular_momentum.pdf`, `hmf.pdf`, `velocity_dist.pdf`, `lifespan_dist.pdf`, `spatial_dist.pdf`. |
| 9 | All tree-walking is O(N) | The plotting code contains no nested loop where both loops iterate over halos (i.e. no `for i in range(N): for j in range(N)` pattern). Progenitor traversal uses `FirstProgenitor`/`NextProgenitor` linked-list walks. |
| 10 | No direct plt.savefig() or plt.close() calls | The plotting code does not call `plt.savefig()` or `plt.close()` directly. All saving and closing goes through `plot_utils.save_figure()`. |
| 11 | All plots use the registered mplstyle | `plt.style.use()` is called with the path to `reference/sage_validation.mplstyle` before the first figure in every plotting script or module. The style is not overridden with inline `rcParams` after this call. |
| 12 | Relative difference column has symmetric colour scale | For the hexbin spatial distribution plot (spatial_dist.pdf), the colour map for the relative difference panel is symmetric (vmin = -abs_max, vmax = +abs_max). For histogram relative difference panels, y-axis limits are symmetric around 0. |
| 13 | Axis labels are consistent with loader-applied unit normalisations | For every plot, read the loader(s) used to produce the data (e.g. `_load_binary_trees`, `_load_trees`) and identify any unit scaling applied (e.g. `SubhaloPos × 1000`: Mpc/h → kpc/h; `SubhaloSpin × 1000`: (Mpc/h)(km/s) → (kpc/h)(km/s)). Every axis label that references a normalised field must reflect the post-normalisation unit, not the simulation's native unit. A label that names a unit inconsistent with the data as it exists at plot time is a FAIL, regardless of whether the relative difference column is unaffected. |

---

## How to verify each item

### Items 1, 10, 11 (code structure checks)

Read the plotting Python file(s) directly. Search for:

- `plt.style.use` — must appear before any figure creation call.
- `plt.savefig` — must not appear anywhere; only `plot_utils.save_figure`.
- `plt.close` — must not appear anywhere; only called inside `plot_utils.save_figure`.
- `rcParams` overrides after `plt.style.use` — flag any that contradict the style sheet.

### Items 2, 3 (sample consistency)

Read the sample selection code. Verify that:

- Tree indices are computed once and stored in a variable that is reused for both
  the input file reader and the output file reader.
- The filtering `Group_M_Crit200 > 0` is applied before computing mass ranks.

### Items 4, 5, 6 (correct field usage)

Read the code that populates the y-axis data for each plot:

- Item 4: find where `mah.pdf` data is assembled. Confirm the variable comes from
  `Group_M_Crit200`, not any other mass dataset.
- Item 5: find where `velocity_dist.pdf` data is assembled. Confirm it uses
  `SubhaloVel` and applies `np.linalg.norm(..., axis=1)` (or equivalent).
- Item 6: find where `angular_momentum.pdf` data is assembled. Confirm it uses
  `SubhaloSpin` and applies the vector magnitude.

### Item 7 (relative difference formula and labelling)

Read the code for one representative relative difference panel. Confirm:

- Formula: `(output - input) / input` or equivalent.
- Zero-replacement: positions where input == 0 use NaN, not 0.
- Axis label contains "(output" and "input" and "/".
- `axhline(0, ...)` is called on every relative difference axis.

### Item 8 (all 7 files exist)

Run: `ls -lh assets/semantic_validation/` and confirm all 7 PDF filenames are present
with non-zero file size.

### Item 9 (O(N) tree walking)

Read all tree-walking loops in the plotting code. Flag any loop of the form:

```python
for i in range(len(halos)):
    for j in range(len(halos)):
```

or any list comprehension `[... for j in range(N) if condition_involving_halos[j]]`
inside a loop over `i` in `range(N)`.

### Item 12 (symmetric colour scale)

Read the hexbin plotting code for `spatial_dist.pdf`. Confirm:

- `vmin` and `vmax` are set explicitly and are negatives of each other.
- The colour map is a diverging map (e.g. `RdBu_r`, `coolwarm`, `bwr`).
For histogram panels, confirm `ylim` is set symmetrically (e.g. `ylim(-x, x)`).

### Item 13 (axis labels consistent with loader normalisations)

Read every loader function invoked by `generate_all_plots()` (currently `_load_binary_trees` and `_load_trees`). Record any scaling applied to fields:

- `_load_binary_trees`: `SubhaloPos` ×1000 (Mpc/h → kpc/h), `SubhaloSpin` ×1000 ((Mpc/h)(km/s) → (kpc/h)(km/s)).
- `_load_trees` (HDF5): fields are read as stored on disk; check the schema for on-disk units.

Then read every `set_xlabel` / `set_ylabel` / `set_title` call in the plotting code and confirm the unit string matches the post-normalisation unit. Flag any label whose unit string names the simulation's native unit instead of the normalised unit. This check applies to all plots, not only the spatial distribution.
