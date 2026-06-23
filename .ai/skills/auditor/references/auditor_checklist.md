# Auditor Checklist

10-item checklist for the independent audit of the semantic validation plots and code.
The plots are output-only (the converted data; no input or relative-difference column).
Each item has an explicit PASS condition. Any deviation from the PASS condition is a FAIL.

---

| # | Item | PASS condition |
| - | ---- | -------------- |
| 1 | mplstyle applied before first figure | `plt.style.use("reference/sage_validation.mplstyle")` is called before any `plt.subplots()` or `plt.figure()` call in the plotting code. |
| 2 | Halos with mass <= 0 excluded before sampling | Before selecting mass bins or computing distributions, halos with `Group_M_Crit200 <= 0` at the lowest-redshift snapshot are filtered out. No such halo appears in any plot. |
| 3 | MAH uses Group_M_Crit200 | The mass accretion history (mah.pdf) plots `Group_M_Crit200` on the y axis. It does not use `Group_M_Mean200`, `Group_M_TopHat200`, or any other mass field. |
| 4 | Velocity distribution uses SubhaloVel modulus | velocity_dist.pdf plots the magnitude `sqrt(Vx^2 + Vy^2 + Vz^2)` of `SubhaloVel`. It does not plot `SubhaloVMax` or any component of `SubhaloVel` individually. |
| 5 | Angular momentum uses SubhaloSpin vector magnitude | angular_momentum.pdf plots `\|SubhaloSpin\| = sqrt(Jx^2 + Jy^2 + Jz^2)`. It does not plot the dimensionless spin parameter lambda or any scalar spin field. |
| 6 | All 7 plots present in assets/semantic_validation/ | The following files all exist and are non-empty: `mah.pdf`, `merger_rate.pdf`, `angular_momentum.pdf`, `hmf.pdf`, `velocity_dist.pdf`, `lifespan_dist.pdf`, `spatial_dist.pdf`. |
| 7 | All tree-walking is O(N) | The plotting code contains no nested loop where both loops iterate over halos (i.e. no `for i in range(N): for j in range(N)` pattern). Progenitor traversal uses `FirstProgenitor`/`NextProgenitor` linked-list walks. |
| 8 | No direct plt.savefig() or plt.close() calls | The plotting code does not call `plt.savefig()` or `plt.close()` directly. All saving and closing goes through `plot_utils.save_figure()`. |
| 9 | All plots use the registered mplstyle | `plt.style.use()` is called with the path to `reference/sage_validation.mplstyle` before the first figure in every plotting script or module. The style is not overridden with inline `rcParams` after this call. |
| 10 | Axis labels are consistent with loader-applied unit normalisations | For every plot, read the loader(s) used to produce the data (e.g. `_load_binary_trees`, `_load_trees`) and identify any unit scaling applied (e.g. `SubhaloPos x 1000`: Mpc/h -> kpc/h; `SubhaloSpin x 1000`: (Mpc/h)(km/s) -> (kpc/h)(km/s)). Every axis label that references a normalised field must reflect the post-normalisation unit, not the simulation's native unit. A label that names a unit inconsistent with the data as it exists at plot time is a FAIL. |

---

## How to verify each item

### Items 1, 8, 9 (code structure checks)

Read the plotting Python file(s) directly. Search for:

- `plt.style.use` - must appear before any figure creation call.
- `plt.savefig` - must not appear anywhere; only `plot_utils.save_figure`.
- `plt.close` - must not appear anywhere; only called inside `plot_utils.save_figure`.
- `rcParams` overrides after `plt.style.use` - flag any that contradict the style sheet.

### Item 2 (mass filtering)

Read the sample selection code. Verify that the filtering `Group_M_Crit200 > 0` is
applied before computing mass ranks or distributions.

### Items 3, 4, 5 (correct field usage)

Read the code that populates the y-axis data for each plot:

- Item 3: find where `mah.pdf` data is assembled. Confirm the variable comes from
  `Group_M_Crit200`, not any other mass dataset.
- Item 4: find where `velocity_dist.pdf` data is assembled. Confirm it uses
  `SubhaloVel` and applies `np.linalg.norm(..., axis=1)` (or equivalent).
- Item 5: find where `angular_momentum.pdf` data is assembled. Confirm it uses
  `SubhaloSpin` and applies the vector magnitude.

### Item 6 (all 7 files exist)

Run: `ls -lh assets/semantic_validation/` and confirm all 7 PDF filenames are present
with non-zero file size.

### Item 7 (O(N) tree walking)

Read all tree-walking loops in the plotting code. Flag any loop of the form:

```python
for i in range(len(halos)):
    for j in range(len(halos)):
```

or any list comprehension `[... for j in range(N) if condition_involving_halos[j]]`
inside a loop over `i` in `range(N)`.

### Item 10 (axis labels consistent with loader normalisations)

Read every loader function invoked by `generate_all_plots()` (currently `_load_binary_trees` and `_load_trees`). Record any scaling applied to fields:

- `_load_binary_trees`: `SubhaloPos` x1000 (Mpc/h -> kpc/h), `SubhaloSpin` x1000 ((Mpc/h)(km/s) -> (kpc/h)(km/s)).
- `_load_trees` (HDF5): fields are read as stored on disk; check the schema for on-disk units.

Then read every `set_xlabel` / `set_ylabel` / `set_title` call in the plotting code and confirm the unit string matches the post-normalisation unit. Flag any label whose unit string names the simulation's native unit instead of the normalised unit.
