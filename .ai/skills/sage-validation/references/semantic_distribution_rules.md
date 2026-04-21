# Semantic Distribution Rules (HMF, Velocity, Lifespan, Spatial)

<!-- Sibling dependencies: global_semantic_rules.md, semantic_evolution_rules.md, audit_checklist.md -->

## 1. Sub-Architecture Rules

* **Distribution Histograms:** 1x3 Grid. Use ALL halo data. Evaluate distributions strictly at the lowest available redshift. **CRITICAL FOR LIFESPAN:** Even though `lifespan` requires temporal branch tracing, it is a Histogram. You MUST calculate the branch depth for ALL root halos at the lowest redshift. Use `sage_validation_utils.plot_1x3_histogram()`.
* **Spatial Integrity (Hexbin):** 1x3 Grid. Col 1 & 2: Plot $X$ vs $Y$ positions. Col 3 (Rel. Diff): Radial distance diff. Use `sage_validation_utils.plot_1x3_hexbin()`.

## 2. Extraction & Parity Constraints

* **1:1 Topological Extraction & Memory Management:** You MUST evaluate the entirety of both datasets. To prevent memory failure, you MUST use generator functions or chunked reading (e.g., `pandas` chunks). Pre-calculate the bin edges globally, read the input in chunks, compute `np.histogram` or hexbin arrays immediately, and add them to a running total.
* **Topological Match Enforcement:** You MUST enforce strict 1:1 cross-referencing. When comparing an input subset to the output (e.g., if limiting extraction for speed testing), you MUST filter the output HDF5 using `OriginalID` to guarantee you are extracting identical physical structures in the exact same array order as the input. If the arrays lengths mismatch, the comparison mathematically fails.
* **Performance - Vectorised Accumulation:** Instead of appending massive numbers of values to standard Python lists and histogramming at the end, prefer vectorised `numpy` operations or compute partial array chunks on the fly to minimise list-append overhead.
