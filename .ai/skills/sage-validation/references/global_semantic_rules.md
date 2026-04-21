# Global Semantic Validation Execution Protocol

<!-- Sibling dependencies: semantic_evolution_rules.md, semantic_distribution_rules.md, audit_checklist.md -->

> [!CAUTION]
> **STRICT EXECUTION PROTOCOL:**
>
> 1. **Mandatory Scope:** ALL seven visualisations MUST be generated during the full validation suite (STATE 4). Omission is forbidden. Generate placeholder plots ONLY if the required physical data is truly absent from the source simulation (e.g., the simulation did not record spin). **CRITICAL ANTI-SHORTCUT RULE:** You MUST NOT generate placeholders simply because the data extraction (e.g., temporal branch-tracing via `FirstProgenitor` and `NextProgenitor` pointers for `mah`, `merger_rate`, `spin`, or `lifespan`) is algorithmically complex or computationally intensive. If the pointers and data exist, you MUST implement the full traversal logic. Script simplicity is never an excuse to bypass validation.
> 2. **File Naming & Locality:** `1_validation_<plot_identifier>_<name_of_the_dataset>.png`. Save ALL plots to the `output/` directory. (Note: The utility library handles this automatically; do not save manually).
> 3. **Test Sample Plotting Prohibition:** You MUST NOT generate any semantic plots for the small sample test run (STATE 3). Semantic validation requires the full temporal depth of the entire dataset. Attempting to plot the test sample will result in degeneracies.
> 4. **Global Aesthetics & Utility Library:** All plots MUST include a descriptive title, explicit labels, and a legend. **CRITICAL:** You MUST use the `sage_validation_utils.py` library located in `.ai/skills/sage-validation/assets/`. Do NOT write raw Matplotlib subplot code for the 3-panel grids yourself. These utility functions automatically handle saving the image and closing the plot. **Do NOT call `plt.savefig()` or `plt.close()` in your generated script.**
> 5. **Scaling Rules:** Any `logscale` requirement implicitly mandates safe zero-value handling (e.g., via `symlog` or masking). The utility library handles this if passed `is_log_y=True`.
> 6. **Lowest Available Redshift:** All distribution plots and root halo selection for evolution plots MUST be evaluated strictly at the lowest available redshift (e.g., `SnapNum == max_snap`).
> 7. **Float32 Parity:** SAGE stores all physics fields as `float32`. When computing relative differences, both input and output arrays MUST be cast to `float32` before comparison to avoid spurious micro-residuals from `float64` precision. The utility library enforces this automatically.

## The 3-Panel Architecture Protocol

Every visualisation MUST be structured as a side-by-side comparison:

* Col 1: **Input Data** (Raw unchanged fields parsed **INDEPENDENTLY** from the original non-SAGE files via `np.fromfile` or similar. NEVER reconstruct Input by reverse-mathing the Output SAGE arrays).
* Col 2: **Output SAGE Data** (Converted/Mapped data extracted from the `0_full_sage_tree_*.hdf5` file).
* Col 3: **Relative Difference** (`(Output - Input) / Input`, handled automatically by `sage_validation_utils.py`).

## Performance Optimisation Guidelines

* **Persistent File Handles:** Open the SAGE HDF5 output file once at the start of the validation script and pass the handle down, rather than repeatedly opening and closing it inside tree-iteration loops.
