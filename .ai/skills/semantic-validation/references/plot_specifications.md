# Semantic Validation Plot Specifications

Per-plot axis specifications, layout rules, filtering, and labelling requirements.
All plots show the **converted output only** (no input or relative-difference column).
All plots use `reference/sage_validation.mplstyle`. All saving goes through
`plot_utils.save_figure()`.

---

## Per-mass-bin evolution plots (3x1)

Each figure has one panel per mass bin (3 rows, 1 column):

- **Rows**: top = top-5 most massive trees, middle = 5 median-mass trees,
  bottom = 5 least massive trees (mass > 0 at lowest-redshift snapshot).
- Each panel's title is its bin label ("Top 5", "Median 5", "Bottom 5").

For each row, the 5 trees in that mass bin are overlaid on the same axes (i.e. each
panel shows 5 curves, one per tree). Use a semi-transparent alpha (e.g. 0.6) so
overlapping curves are visible.

### Plot 1 - Mass Accretion History (`mah.pdf`)

| Property | Spec |
| -------- | ---- |
| X axis | `SnapNum` (integer snapshot index, ascending = later time) |
| Y axis | `Group_M_Crit200` in 10^10 Msun/h, log scale |
| Y limits | Auto, but enforce `ymin > 0` for log scale |

Walk each tree using `FirstProgenitor` to find the main progenitor branch:

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

### Plot 2 - Merger Rate (`merger_rate.pdf`)

| Property | Spec |
| -------- | ---- |
| X axis | `SnapNum` |
| Y axis | Number of progenitors at each snapshot (integer, linear scale) |

At each snapshot, count the number of halos that merge into the main branch halo -
the number of halos whose `Descendant` points to the main branch halo at that snapshot.

### Plot 3 - Specific Angular Momentum (`angular_momentum.pdf`)

| Property | Spec |
| -------- | ---- |
| X axis | `SnapNum` |
| Y axis | `\|SubhaloSpin\|` = `sqrt(Jx^2 + Jy^2 + Jz^2)` in (kpc/h)(km/s), log scale |

Walk the main progenitor branch of each selected tree. Plot `|SubhaloSpin|` at each
snapshot. **Do not plot the spin parameter lambda.**

---

## Distribution plots (single panel)

Each figure is a single panel of the converted output. Use all trees at the
lowest-redshift snapshot (after excluding mass <= 0 halos).

### Plot 4 - Halo Mass Function (`hmf.pdf`)

| Property | Spec |
| -------- | ---- |
| X axis | `log10(Group_M_Crit200)`, binned |
| Y axis | Count per bin (log scale) |
| Bins | 30 bins spanning the range of the data |
| Filtering | Exclude halos with `Group_M_Crit200 <= 0` |

### Plot 5 - Velocity Distribution (`velocity_dist.pdf`)

| Property | Spec |
| -------- | ---- |
| X axis | `\|SubhaloVel\|` = `sqrt(Vx^2 + Vy^2 + Vz^2)` in km/s, binned |
| Y axis | Count per bin |
| Bins | 30 bins from 0 to `max(\|SubhaloVel\|)` |

**Use `SubhaloVel` (3-vector), compute the modulus. Do NOT use `SubhaloVMax`.**

### Plot 6 - Lifespan Distribution (`lifespan_dist.pdf`)

| Property | Spec |
| -------- | ---- |
| X axis | Number of snapshots each halo is tracked across (integer) |
| Y axis | Count |
| Computation | For each root halo, count the number of distinct snapshots along its main progenitor branch |
| Bins | Integer bins from 1 to max lifespan |

### Plot 7 - Spatial Distribution (`spatial_dist.pdf`)

| Property | Spec |
| -------- | ---- |
| X axis | `SubhaloPos[:, 0]` (X position in kpc/h) |
| Y axis | `SubhaloPos[:, 1]` (Y position in kpc/h) |
| Plot type | `hexbin` with `gridsize=50`, `mincnt=1`, `cmap="viridis"` |
| Colour bar | Count, labelled |
| Filtering | Lowest-redshift snapshot only; exclude mass <= 0 halos |

---

## Axis and Label Standards

- All axis labels must include units in parentheses, e.g. `Group_M_Crit200 [10^10 Msun/h]`.
- Panel titles must appear as subplot titles (`ax.set_title()`), not as figure-level
  suptitles, so they remain visible when the figure is saved to PDF.
- Use `ax.set_xlabel()` and `ax.set_ylabel()` for all axes; do not leave axes unlabelled.
