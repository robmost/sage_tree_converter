# Validation Protocols: Ensuring Conversion Accuracy

The conversion of merger trees from any simulation format to SAGE's requirements must be verified at three distinct levels: Syntactic, Semantic, and Functional.

## 1. Syntactic Validation (Structural Correctness)

Ensures the output file is a correctly formatted SAGE tree (Binary or HDF5).

* **File Integrity:** Check that the generated file can be opened by standard tools (e.g., `h5dump` for HDF5). If `h5dump` is unavailable natively, fall back to using Python's `h5py` library to recursively dump and inspect the HDF5 structure.
* **Pointer Integrity:** Verify that all `FirstProgenitor`, `NextProgenitor`, and `Descendant` pointers point to valid halos within the same tree or snapshot.
* **Snapshot Consistency:** Ensure all halos have valid snapshot numbers within the expected range (e.g., 0 to $N$).

## 2. Semantic Validation (Physical Consistency)

Ensures the data values are physically meaningful and follow expected trends.

> [!CAUTION]
> **STRICT EXECUTION PROTOCOL:**
>
> 1. **Mandatory Scope:** ALL seven visualisations listed below MUST be generated during the full validation suite. Omission is forbidden. Generate placeholder plots if data is missing, and log the failure.
> 2. **File Naming & Locality:** `1_validation_<plot_identifier>_<name_of_the_dataset>.png`. Save ALL plots to the `output/` directory. Do NOT generate these plots for the small sample test run.
> 3. **Global Aesthetics:** All plots MUST include a descriptive title (e.g. `<plot_id>_<dataset_name>`), explicit x/y labels with units, and a legend. **CRITICAL:** For multi-panel grids (like 1x3 or 3x3), you MUST explicitly apply `.set_xlabel()` and `.set_ylabel()` to *every individual subplot axis* within loops. Do not assume figure-level labels are sufficient.
> 4. **Scaling Rules:** Any `logscale` requirement implicitly mandates safe zero-value handling (e.g., via `symlog` or masking). Use log/symlog scale where appropriate for Rel. Diff plots if the span is large.

### The 3-Panel Architecture Protocol

Every visualisation MUST be structured as a side-by-side comparison:

* Col 1: **Input Data** (Raw unchanged fields from original parser)
* Col 2: **Output SAGE Data** (Converted/Mapped data)
* Col 3: **Relative Difference** (`(Output - Input) / Input`)

**Sub-Architecture Rules:**

* **Evolution Lineplots:** 3x3 Grid (Rows: 5 most massive, 5 average mass, 5 least massive). Mass ranges are calculated/selected at the lowest available redshift. Use a distinct colour for each mass group. Plot lines, NOT distributions. The relative difference MUST be calculated for each halo individually and then averaged over the sample of halos.
* **Distribution Histograms:** 1x3 Grid. Use ALL halo data. Ensure adequate bins. Plot as **lineplots** (midpoints on x-axis, counts on y-axis) rather than bars/steps. Rel. Diff MUST be calculated for each bin individually. Evaluate distributions at the lowest available redshift. **CRITICAL FOR LIFESPAN:** Even though `lifespan` requires temporal branch tracing (like Evolution plots), it is a Histogram. You MUST calculate the branch depth for ALL root halos at the lowest redshift, NOT just the 15 sub-sampled halos.
* **Spatial Integrity (Hexbin):** 1x3 Grid. Col 1 & 2: Plot $X$ vs $Y$ positions using a Hexbin density map with logarithmic colour scaling (`bins='log'`). Col 3 (Rel. Diff): Plot a Hexbin where the X-axis is the halo's radial distance from the simulation box center, and the Y-axis is the Relative Difference of that radial distance. Ensure `bins='log'` is applied to prevent saturation.

### Required Visualisations Registry

| Plot Identifier | Type | X-Axis | Y-Axis | Scaling Rule |
| :--- | :--- | :--- | :--- | :--- |
| `mah` | Evolution | Snapshot | Mass {Units} | Log y-axis |
| `merger_rate` | Evolution | Snapshot | Progenitor Count | Linear |
| `spin` | Evolution | Snapshot | Spin Magnitude {Units} | Log y-axis |
| `velocity` | Histogram | Velocity {Units} | Halo Count | Log y-axis |
| `lifespan` | Histogram | Lifespan {Snapshots} | Halo Count | Log y-axis |
| `hmf` | Histogram | Mass {Units} | Halo Count | Log x-axis and Log y-axis |
| `spatial` | Hexbin | X position {Units} | Y position {Units} | Logarithmic (`bins='log'`) |

## 3. Functional Validation (SAGE Compatibility)

Ensures that SAGE can actually load and process the converted trees.

* **Small Sample Test:** Always generate a small test sample (e.g., the 100 most massive halos) before full conversion. **MEMORY CRITICAL:** When parsing huge raw inputs (especially `.dat` or `.txt` files) to extract this sample, you MUST use memory-efficient two-pass reading or iterators. Do NOT append massive string payloads into Python lists, as this will trigger an out-of-memory (OOM) freeze. The test conversion should be named `0_test_sage_tree_<name_of_the_dataset>.hdf5`.
* **SAGE Dry Run:** If SAGE is available in the environment, attempt to run it on the test sample. The test run should be named `0_test_sage_run_<name_of_the_dataset>.hdf5`.
* **Error Parsing:** If SAGE fails, analyse its error logs (e.g., `sage.log`) to identify missing fields or incorrect pointer structures.
* **Statistical Comparison:** If possible, compare the stellar mass function or halo mass function from a previous successful run with the results of the new conversion.

## 4. Automation Steps for the LLM

1. **Generate Validation Script:** Create a Python script that reads the converted tree and checks pointer integrity and physical bounds. When generating plotting validation scripts, you MUST strictly apply the global aesthetic style by including `plt.style.use('./assets/sage_validation.mplstyle')`. **CRITICAL PARITY RULE:** The plotting script MUST NOT simply dump raw input arrays against the converter's output. You MUST ensure the validation script applies *all* mathematical and structural normalisations (e.g., local-to-global pointer offsets, unit conversions, coordinate origin translations, sorting, and mass threshold filtering) that the master converter uses. The "Input Data" shown in the 3-panel plots MUST represent the physically and structurally normalised input data so that the Relative Difference accurately reflects conversion anomalies rather than raw formatting differences.
2. **Report Validation Results:** Present a summary of any warnings or errors found during the syntactic and semantic checks.
3. **Propose Fixes:** If validation fails, use the findings to adjust the mapping and rerun the test conversion.
