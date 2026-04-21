# The Semantic Validation Audit Checklist

<!-- Sibling dependencies: global_semantic_rules.md, semantic_evolution_rules.md, semantic_distribution_rules.md -->

> [!CAUTION]
> **ANTI-SYCOPHANCY DIRECTIVE:**
> When acting as the Auditor, you MUST assume the generated code is flawed. You are forbidden from simply answering "Yes" to these checklist items. For every item, you MUST explicitly cite the **exact line number(s)** and the **exact code snippet** that satisfies the requirement. If you cannot point to the exact line of code that explicitly performs the required action, the script **FAILS** the audit.

Before executing any semantic validation script, you must verify the following:

## 1. Independent Input Extraction

- [ ] **Check:** Does the script read the raw source files directly (using `np.fromfile()`, `h5py` on original files, etc.) instead of reading the converted SAGE HDF5 output and doing math to recreate the "Input" arrays?
- **Auditor Requirement:** Cite the exact lines where the original non-SAGE files are opened and parsed.

## 2. Zero-Mass Filtering

- [ ] **Check:** When selecting halos based on mass (e.g. for the Evolution plots' "least massive" row), does the script explicitly filter out halos with exactly `0.0` mass ($M \le 0.0$) before sorting and selecting?
- **Auditor Requirement:** Cite the exact line where `mask = mass > 0.0` (or equivalent) is applied to the candidate halos.

## 3. Lowest Available Redshift Filtering

- [ ] **Check:** For all distribution plots (Histograms, Spatial Hexbins) and when selecting root halos for Evolution plots, is the data explicitly restricted to the lowest available redshift (e.g. `SnapNum == 63` or the maximum snapshot)?
- **Auditor Requirement:** Cite the exact line where `snapnum == max_snap` (or equivalent) is enforced before accumulating the data arrays.

## 4. Proper Utility Function Usage

- [ ] **Check:** Does the script use the hardened plotting functions from `sage_validation_utils.py` (e.g., `plot_3x3_evolution()`, `plot_1x3_histogram()`) rather than attempting to write raw Matplotlib subplot code and calculating the relative differences manually?
- **Auditor Requirement:** Cite the exact import statement and the exact line where the utility functions are called.

## 5. Topological Match Enforcement & Performance

- [ ] **Check:** For massive datasets where a limited subset of the input was extracted for speed, does the script explicitly use `OriginalID` to filter the HDF5 output arrays so that ONLY identical physical structures are extracted?
- **Auditor Requirement:** Cite the lines where `OriginalID` from the output is checked against the parsed input IDs (`if orig_id not in inp_z0_ids: continue`).
- [ ] **Check:** Does the script rebuild the output arrays in the EXACT point-to-point order of the input array to prevent random misalignments when feeding data to the Hexbin or relative difference math?
- **Auditor Requirement:** Cite the lines mapping the filtered output data back into the sequence of the `inp_z0` array.
- [ ] **Check:** Does the script use performant extraction algorithms like `pandas` chunks or generator streams, and O(1) dictionary lookups (`desc_to_progs = defaultdict(list)`) rather than computationally crushing O(N^2) list comprehensions?
- **Auditor Requirement:** Cite the line where the `desc_to_progs` dictionary (or equivalent O(1) mechanism) is built.

## 6. Data Parity & Precision

- [ ] **Check:** Does the script explicitly enforce **Unit Scaling Parity** (e.g., if SAGE expects masses in $10^{10} M_{\odot}/h$, does the validation script multiply the SAGE output back by $10^{10}$ before comparing against the raw input)?
- **Auditor Requirement:** Cite the line where the output data array is scaled back to match input units.
- [ ] **Check:** Does the script enforce **Physical Definition Parity**, especially for `Spin`? SAGE expects a 3-component Specific Angular Momentum vector ($j = L/M$), NOT the scalar dimensionless Bullock Spin parameter. If the input format lacks a 3D vector, is a fallback (e.g., zero array) used and warned about?
- **Auditor Requirement:** Cite the lines handling the `Spin` array.
- [ ] **Check:** When plotting `merger_rate` or other evolution branches, are missing temporal snapshots padded with `np.nan` instead of exactly `0.0`?
- **Auditor Requirement:** Cite the lines padding missing branch snapshots with `np.nan`.
- [ ] **Check:** Is topological branch tracing strictly confined by a root tree ID (e.g. `Tree_root_ID` or `TreeDescendant`), preventing the script from accidentally tracing globally across multiple independent trees?
- **Auditor Requirement:** Cite the condition that restricts traversal to a specific tree structure.

## 7. Redundant File Operations

- [ ] **Check:** Does the script explicitly AVOID calling `plt.savefig()` or `plt.close()` after invoking functions from `sage_validation_utils.py`?
- **Auditor Requirement:** Confirm that there are no `savefig` calls in the main script loop that would overwrite the utility's output, citing the lines immediately following the utility function calls to prove they are absent.

***

**Audit Failure Protocol:**
If *any* of the above checks fail or lack an explicit line-number citation, you MUST halt, explain the failure, discard the script, and regenerate a new, compliant semantic validation script. You may only execute the script if it passes all checks perfectly.
