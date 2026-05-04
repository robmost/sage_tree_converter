# Relative Difference Column

The third column of every semantic validation plot shows the relative difference
between the output (converted) and input (unconverted) data.

## Formula

```text
relative_difference = (output - input) / input
```

- Apply per data point (for evolution plots: per snapshot per tree) or per bin
  (for distribution plots: per histogram bin or hexbin cell).
- Where `input == 0`, set `relative_difference = NaN` and do not plot that point.
  Do not substitute 0 or any other value.

## Axis label

The y-axis label for the relative difference column must be exactly:

```text
(output − input) / input
```

(using the minus sign character −, not a hyphen, where possible in matplotlib).
Acceptable alternative: `(output - input) / input`.

## Colour scale for column 3

- **Evolution plots (3×3)**: use the same line colour as columns 1 and 2, but make the
  relative difference axis clearly separate. A horizontal dashed line at y=0 must be
  drawn on every relative difference panel.
- **Distribution/spatial plots (1×3)**:
  - For histograms: plot as a step histogram with a horizontal dashed line at y=0.
  - For hexbin spatial plot: use a symmetric diverging colour map (e.g. `RdBu_r`)
    centred at 0. The colour limits must be symmetric: `vmin = -abs_max`,
    `vmax = +abs_max` where `abs_max = max(|relative_difference|)` across all cells.
    Do not use an asymmetric colour scale.

## Y-axis limits for column 3

- For evolution and histogram plots: set `ylim` symmetrically around 0 using
  `abs_max = max(|relative_difference|)` (excluding NaN). Use `ylim(-abs_max * 1.1, abs_max * 1.1)`.
- If `abs_max == 0`, use `ylim(-0.1, 0.1)` as a fallback.

## Example (histogram)

```python
rel_diff = np.where(input_counts > 0,
                    (output_counts - input_counts) / input_counts,
                    np.nan)
abs_max = np.nanmax(np.abs(rel_diff))
if abs_max == 0 or np.isnan(abs_max):
    abs_max = 0.1
ax.step(bin_edges[:-1], rel_diff, where="post")
ax.axhline(0, color="black", linestyle="--", linewidth=0.8)
ax.set_ylim(-abs_max * 1.1, abs_max * 1.1)
ax.set_ylabel("(output − input) / input")
```
