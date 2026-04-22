# Global Semantic Validation Execution Protocol

> [!CAUTION]
> **STRICT EXECUTION PROTOCOL:**
>
> 1. **Mandatory Scope:** You MUST generate all 7 visualisations (refer to `SKILL.md` for the list). Omission is forbidden. Generate placeholder plots ONLY if the required physical data is truly absent from the source simulation (e.g., the simulation did not record spin). **CRITICAL ANTI-SHORTCUT RULE:** You MUST NOT generate placeholders simply because the data extraction is algorithmically complex. If the pointers and data exist, you MUST implement the full traversal logic.
> 2. **File Naming & Locality:** `1_validation_<plot_identifier>_<name_of_the_dataset>.png`. Save ALL plots to the `output/` directory.
> 3. **Test Sample Plotting Prohibition:** You MUST NOT generate any semantic plots for the small sample test run (STATE 3).
> 4. **Global Aesthetics & Utility Library:** All plots MUST include a descriptive title, explicit labels, and a legend. **CRITICAL:** You MUST use the `sage_validation_utils.py` library. Do NOT write raw Matplotlib subplot code for the 3-panel grids yourself. **Do NOT call `plt.savefig()` or `plt.close()` in your generated script.**
> 5. **Adversarial Audit:** Before execution, you MUST adopt the Auditor persona and perform an adversarial review. You MUST explicitly look for evidence of "cheating" (e.g., deriving Input from Output) and cite the exact lines of code that prove independence.
> 6. **Scaling Rules:** Any `logscale` requirement implicitly mandates safe zero-value handling (e.g., via `symlog` or masking). The utility library handles this if passed `is_log_y=True`.
> 7. **Lowest Available Redshift:** All distribution plots and root halo selection for evolution plots MUST be evaluated strictly at the lowest available redshift (e.g., `SnapNum == max_snap`).
> 8. **Float32 Parity:** SAGE stores all physics fields as `float32`. When computing relative differences, both input and output arrays MUST be cast to `float32` before comparison to avoid spurious micro-residuals from `float64` precision. The utility library enforces this automatically.
> 9. **Completeness Enforcement:** At the very end of your script, you MUST call `sage_validation_utils.verify_completeness(dataset_name)`. This will raise an exception and fail the script if any of the 7 plots are missing.

## The 3-Panel Architecture Protocol

Every visualisation MUST be structured as a side-by-side comparison:

* Col 1: **Input Data** (Raw unchanged fields parsed **INDEPENDENTLY** from the original non-SAGE files via `np.fromfile` or similar. NEVER reconstruct Input by reverse-mathing the Output SAGE arrays).
* Col 2: **Output SAGE Data** (Converted/Mapped data extracted from the `0_full_sage_tree_*.hdf5` file).
* Col 3: **Relative Difference** (`(Output - Input) / Input`, handled automatically by `sage_validation_utils.py`).

## Performance Optimisation Guidelines

* **Persistent File Handles:** Open the SAGE HDF5 output file once at the start of the validation script and pass the handle down, rather than repeatedly opening and closing it inside tree-iteration loops.
* **Progress Indicators:** Any loop iterating over trees or root halos (e.g., branch tracing for lifespan or MAH) MUST use the `tqdm` library to provide a terminal progress bar. This ensures visibility into the execution of time-intensive traversal logic.
