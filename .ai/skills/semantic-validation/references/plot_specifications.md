# Semantic Validation Plot Specifications

Per-plot axis specifications, layout rules, filtering, and labelling requirements.
All plots use `reference/sage_validation.mplstyle`. All saving goes through
`plot_utils.save_figure()`.

---

## 3×3 Evolution Plots (mass bin rows)

Each 3×3 figure has:

- **Columns**: left = input, centre = output, right = relative difference
- **Rows**: top = top-5 most massive trees, middle = 5 median-mass trees,
  bottom = 5 least massive trees (mass > 0 at lowest-redshift snapshot)

For each row, the 5 trees in that mass bin are overlaid on the same axes (i.e. each
panel shows 5 curves, one per tree). Use a semi-transparent alpha (e.g. 0.6) so
overlapping curves are visible.

### Plot 1 — Mass Accretion History (`mah.pdf`)

| Property | Spec |
| -------- | ---- |
| X axis | `SnapNum` (integer snapshot index, ascending = later time) |
| Y axis | `Group_M_Crit200` in 10¹⁰ M☉/h, log scale |
| Y limits | Auto, but enforce `ymin > 0` for log scale |
| Column 3 Y axis | Relative difference (linear scale, symmetric around 0) |
| Title (column 1) | "Input — MAH" |
| Title (column 2) | "Output — MAH" |
| Title (column 3) | "Relative difference" |
| Row labels | "Top 5", "Median 5", "Bottom 5" (as y-axis labels on column 1) |

Walk each tree using `Descendant` to find the main progenitor branch:

```python
# Main progenitor branch of root halo r
branch_snaps, branch_masses = [], []
h = r
while h != -1:
    branch_snaps.append(SnapNum[h])
    branch_masses.append(Group_M_Crit200[h])
    h = FirstProgenitor[h]
```

This is O(depth) per tree, O(N) total.

### Plot 2 — Merger Rate (`merger_rate.pdf`)

| Property | Spec |
| -------- | ---- |
| X axis | `SnapNum` |
| Y axis | Number of progenitors at each snapshot (integer, linear scale) |
| Column 3 Y axis | Relative difference |

At each snapshot, count the number of halos that merge into the main branch halo.
This is `len(progenitors_at_snapshot)` — the number of halos whose `Descendant`
points to the main branch halo at that snapshot.

### Plot 3 — Specific Angular Momentum (`angular_momentum.pdf`)

| Property | Spec |
| -------- | ---- |
| X axis | `SnapNum` |
| Y axis | `\|SubhaloSpin\|` = `sqrt(Jx² + Jy² + Jz²)` in (Mpc/h)(km/s), log scale |
| Column 3 Y axis | Relative difference |

Walk the main progenitor branch of each selected tree. Plot `|SubhaloSpin|` at each
snapshot. **Do not plot the spin parameter λ.**

---

## 1×3 Distribution Plots

Each 1×3 figure has:

- **Column 1** (left): input histogram/hexbin
- **Column 2** (centre): output histogram/hexbin
- **Column 3** (right): relative difference per bin

Use all trees at the lowest-redshift snapshot (after excluding mass ≤ 0 halos).

### Plot 4 — Halo Mass Function (`hmf.pdf`)

| Property | Spec |
| -------- | ---- |
| X axis | `log10(Group_M_Crit200)`, binned |
| Y axis | Count per bin (log scale) |
| Bins | 30 bins spanning the range of the data |
| Column 3 Y axis | `(output_count - input_count) / input_count` per bin |
| Filtering | Exclude halos with `Group_M_Crit200 <= 0` |

### Plot 5 — Velocity Distribution (`velocity_dist.pdf`)

| Property | Spec |
| -------- | ---- |
| X axis | `\|SubhaloVel\|` = `sqrt(Vx² + Vy² + Vz²)` in km/s, binned |
| Y axis | Count per bin |
| Bins | 30 bins from 0 to `max(\|SubhaloVel\|)` |
| Column 3 Y axis | Relative difference per bin |

**Use `SubhaloVel` (3-vector), compute the modulus. Do NOT use `SubhaloVMax`.**

### Plot 6 — Lifespan Distribution (`lifespan_dist.pdf`)

| Property | Spec |
| -------- | ---- |
| X axis | Number of snapshots each halo is tracked across (integer) |
| Y axis | Count |
| Computation | For each root halo, count the number of distinct snapshots along its main progenitor branch |
| Bins | Integer bins from 1 to max lifespan |
| Column 3 Y axis | Relative difference per bin |

### Plot 7 — Spatial Distribution (`spatial_dist.pdf`)

| Property | Spec |
| -------- | ---- |
| X axis | `Pos[:, 0]` (X position in Mpc/h) |
| Y axis | `Pos[:, 1]` (Y position in Mpc/h) |
| Plot type | `hexbin` with `gridsize=50`, `mincnt=1` |
| Colour map | `viridis` for columns 1 and 2; symmetric diverging map (e.g. `RdBu_r`) for column 3 |
| Column 3 | Relative difference of hexbin counts per cell |
| Filtering | Lowest-redshift snapshot only; exclude mass ≤ 0 halos |

---

## Axis and Label Standards

- All axis labels must include units in parentheses, e.g. `Group_M_Crit200 [10¹⁰ M☉/h]`.
- The relative difference column (column 3) must always be labelled
  `(output - input) / input` on the y axis.
- Column titles must appear as subplot titles (`ax.set_title()`), not as figure-level
  suptitles, so they remain visible when the figure is saved to PDF.
- Use `ax.set_xlabel()` and `ax.set_ylabel()` for all axes; do not leave axes unlabelled.
