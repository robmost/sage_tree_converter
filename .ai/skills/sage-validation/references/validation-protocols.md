# Validation Protocols: Ensuring Conversion Accuracy

The conversion of merger trees from any simulation format to SAGE's requirements must be verified at three distinct levels: Syntactic, Semantic, and Functional.

## 1. Syntactic Validation (Structural Correctness)

Ensures the output file is a correctly formatted SAGE tree (Binary or HDF5) according to the strict rules in `references/sage_hdf5_schema.md`.

* **File Integrity:** Check that the generated file can be opened by standard tools (e.g., `h5dump` for HDF5). If `h5dump` is unavailable natively, fall back to using Python's `h5py` library to recursively dump and inspect the HDF5 structure.
* **Schema Compliance:** Verify that all output HDF5 data explicitly maps to the datasets listed in `references/sage_hdf5_schema.md` using the LHaloTree naming convention, and that the root attributes (`Ntrees`, `TotNHalos`) and groups (`/Tree<X>/`) are properly defined.
* **Pointer Integrity:** Verify that all `FirstProgenitor`, `NextProgenitor`, and `Descendant` pointers point to valid halos within the same tree or snapshot.
* **Snapshot Consistency:** Ensure all halos have valid snapshot numbers within the expected range (e.g., 0 to $N$).

## 2. Semantic Validation (Physical Consistency)

Ensures the data values are physically meaningful and follow expected trends.

> [!CAUTION]
> **STRICT EXECUTION PROTOCOL:**
>
> 1. **Mandatory Scope:** ALL seven visualisations listed below MUST be generated during the full validation suite (STATE 4). Omission is forbidden. Generate placeholder plots ONLY if the required physical data is truly absent from the source simulation (e.g., the simulation did not record spin). **CRITICAL ANTI-SHORTCUT RULE:** You MUST NOT generate placeholders simply because the data extraction (e.g., temporal branch-tracing via `FirstProgenitor` and `NextProgenitor` pointers for `mah`, `merger_rate`, `spin`, or `lifespan`) is algorithmically complex or computationally intensive. If the pointers and data exist, you MUST implement the full traversal logic. Script simplicity is never an excuse to bypass validation.
> 2. **File Naming & Locality:** `1_validation_<plot_identifier>_<name_of_the_dataset>.png`. Save ALL plots to the `output/` directory.
> 3. **Test Sample Plotting Prohibition:** You MUST NOT generate any semantic plots for the small sample test run (STATE 3). Semantic validation requires the full temporal depth of the entire dataset. Attempting to plot the test sample will result in degeneracies (like a static lifespan).
> 4. **Global Aesthetics & Utility Library:** All plots MUST include a descriptive title, explicit labels, and a legend. **CRITICAL:** You MUST use the `sage_validation_utils.py` library located in `.ai/skills/sage-validation/assets/` to generate all 3-panel plots (`plot_3x3_evolution`, `plot_1x3_histogram`, `plot_1x3_hexbin`). Do NOT write raw Matplotlib subplot code for the 3-panel grids yourself.
> 5. **Scaling Rules:** Any `logscale` requirement implicitly mandates safe zero-value handling (e.g., via `symlog` or masking). The utility library handles this if passed `is_log_y=True`.

### The 3-Panel Architecture Protocol

Every visualisation MUST be structured as a side-by-side comparison:

* Col 1: **Input Data** (Raw unchanged fields parsed **INDEPENDENTLY** from the original non-SAGE files via `np.fromfile` or similar. NEVER reconstruct Input by reverse-mathing the Output SAGE arrays).
* Col 2: **Output SAGE Data** (Converted/Mapped data extracted from the `0_full_sage_tree_*.hdf5` file).
* Col 3: **Relative Difference** (`(Output - Input) / Input`, handled automatically by `sage_validation_utils.py`).

**Sub-Architecture Rules:**

* **Evolution Lineplots:** 3x3 Grid (Rows: 5 most massive, 5 average mass, 5 least massive). Mass ranges are calculated/selected at the lowest available redshift. **CRITICAL:** For "least massive", you MUST explicitly filter out halos with mass $\le 0$ before selection. You MUST extract a unique ID (e.g., original `SubhaloIndex` or array position) for every plotted halo to populate the legends. If using array positions as a fallback, format the string clearly (e.g., `"Idx: 1542"`) so the user knows it is an index and not a native simulation ID. Use `sage_validation_utils.plot_3x3_evolution()` and pass these unique identifiers via the `halo_ids` argument.
* **Distribution Histograms:** 1x3 Grid. Use ALL halo data. Evaluate distributions strictly at the lowest available redshift. **CRITICAL FOR LIFESPAN:** Even though `lifespan` requires temporal branch tracing, it is a Histogram. You MUST calculate the branch depth for ALL root halos at the lowest redshift. Use `sage_validation_utils.plot_1x3_histogram()`.
* **Spatial Integrity (Hexbin):** 1x3 Grid. Col 1 & 2: Plot $X$ vs $Y$ positions. Col 3 (Rel. Diff): Radial distance diff. Use `sage_validation_utils.plot_1x3_hexbin()`.

### Data Parity Constraints

When writing the validation scripts, you must ensure perfect parity between the raw Input and SAGE Output:

* **1:1 Topological Extraction & Memory Management:** For massive datasets, you MUST NOT load the entire dataset into RAM. However, the SAGE guidelines mandate testing the *entire* distribution. You MUST resolve this by:
    1. **For Evolution Plots:** Parse the output HDF5 first to identify the exact `OriginalID`s of the massive target roots at $z=0$. Then, perform a targeted, single-pass sweep of the raw ASCII input, extracting ONLY the progenitor branch halos matching those specific IDs.
    2. **For Histograms & Hexbins:** You MUST evaluate the entirety of both datasets. To prevent memory failure, you MUST use generator functions or chunked reading (e.g., `pandas` chunks). Pre-calculate the bin edges globally, read the input in chunks, compute `np.histogram` or hexbin arrays immediately, and add them to a running total.
    3. **Topological Match Enforcement:** You MUST enforce strict 1:1 cross-referencing. When comparing an input subset to the output (e.g., if limiting extraction for speed testing), you MUST filter the output HDF5 using `OriginalID` to guarantee you are extracting identical physical structures in the exact same array order as the input. If the arrays lengths mismatch, the comparison mathematically fails.
* **Unit Scaling:** If SAGE requires a specific unit (e.g. Mass $\times 10^{10} M_{\odot}/h$), you MUST mathematically scale the SAGE output back to the raw input units before calculating the relative difference.
* **Physical Definitions (Spin):** The SAGE `Spin` array is mathematically a **3-component Specific Angular Momentum vector** ($j = L/M$), NOT the scalar dimensionless Bullock Spin parameter. When validating `spin`, you MUST calculate the magnitude of the $j$ vector. If the input format lacks angular momentum, do not attempt to compare it against a dimensionless parameter; issue a warning and use a zero array fallback.
* **Temporal Padding:** When plotting evolution branches (e.g. `mah`, `merger_rate`), if the output branch is missing snapshots compared to the input branch, you MUST pad the missing indices with `np.nan`, NEVER `0.0`.
* **Topological Confinement:** Always restrict topological branch tracing to a specific tree root ID (`Tree_root_ID` or equivalent). Do not traverse globally across the entire dataset.

### Required Visualisations Registry

| Plot Identifier | Type | X-Axis | Y-Axis | Scaling Rule |
| :--- | :--- | :--- | :--- | :--- |
| `mah` | Evolution | Snapshot | Mass {Units} | Log y-axis |
| `merger_rate` | Evolution | Snapshot | Progenitor Count | Linear |
| `spin` | Evolution | Snapshot | Specific Angular Momentum Magnitude ($|j|$) | Log y-axis |
| `velocity` | Histogram | Velocity Modulus (sqrt(vx^2+vy^2+vz^2), NOT Vmax) {Units} | Halo Count | Log y-axis |
| `lifespan` | Histogram | Lifespan {Snapshots} | Halo Count | Log y-axis |
| `hmf` | Histogram | Mass {Units} | Halo Count | Log x-axis and Log y-axis |
| `spatial` | Hexbin | X position {Units} | Y position {Units} | Logarithmic (`bins='log'`) |

## 3. Functional Validation (SAGE Compatibility)

Ensures that SAGE can actually load and process the converted trees.

* **Small Sample Test:** Always generate a small test sample (e.g., the 100 most massive halos) before full conversion. **MEMORY CRITICAL:** When parsing huge raw inputs (especially `.dat` or `.txt` files) to extract this sample, you MUST use memory-efficient two-pass reading or iterators. Do NOT append massive string payloads into Python lists, as this will trigger an out-of-memory (OOM) freeze. The test conversion should be named `0_test_sage_tree_<name_of_the_dataset>.hdf5`.
* **SAGE Dry Run:** If SAGE is available in the environment, attempt to run it on the test sample. The test run should be named `0_test_sage_run_<name_of_the_dataset>.hdf5`.
* **Full Dataset Conversion:** Once the test sample is successfully validated, execute the conversion on the full dataset. The final output file MUST strictly be named `0_full_sage_tree_<name_of_the_dataset>.hdf5`.
* **Error Parsing:** If SAGE fails, analyse its error logs (e.g., `sage.log`) to identify missing fields or incorrect pointer structures.
* **Statistical Comparison:** If possible, compare the stellar mass function or halo mass function from a previous successful run with the results of the new conversion.

## 4. Automation Steps for the LLM

1. **Generate Validation Script:** Create a Python script that reads the converted tree and checks physical bounds. When generating plotting validation scripts, you MUST strictly apply the global aesthetic style by including `plt.style.use('.ai/skills/sage-validation/assets/sage_validation.mplstyle')` and use the plotting functions from `.ai/skills/sage-validation/assets/sage_validation_utils.py`. You MUST autonomously architect the script to enforce the 1:1 topological extraction via `OriginalID` filtering, O(1) dictionary lookups for branches, and memory-safe extraction (e.g., chunked `pandas` or generators) to adhere to the strict data parity and memory rules.
2. **The Persona-Shift Audit (CRITICAL):** Before executing any semantic validation script, you MUST halt and adopt the "Auditor" persona. Read `.ai/skills/sage-validation/references/audit_checklist.md` and explicitly review your generated script against it. If the audit fails, discard the script and write it again.
3. **Report Validation Results:** Present a summary of any warnings or errors found during the syntactic and semantic checks.
4. **Programmatic Data Checkup (CRITICAL):** DO NOT rely on visual OCR inspection of generated plot images. You MUST programmatically validate the data arrays *during* the execution of the semantic validation scripts, before saving the figures. This includes: asserting `np.any(np.isnan(data))` is false, ensuring log-scale arrays do not contain exact zeros (which indicates unhandled invalid halos), and checking that data bounds (min/max) are physically plausible. If an anomaly is detected, flag it, inform the user, and **EXPLICITLY ask** if they want you to action the anomaly. If authorized, investigate the root cause, create any auxiliary diagnostic files in `output/intermediates/`, fix the mapping/code, regenerate the validation, and document all debugging steps taken in the validation log.
5. **Resource & Runtime Warnings:** If you detect (e.g., via existing memory checks, file size analysis, or total tree count) that the conversion or semantic validation process will be exceptionally time-consuming or memory-intensive, you MUST warn the user *before* proceeding with the execution. Present the estimated scale of the operation and explicitly ask for their authorization to proceed with the full dataset.
6. **Propose Fixes:** If validation fails, use the findings to adjust the mapping and rerun the test conversion.
