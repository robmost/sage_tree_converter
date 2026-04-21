# Semantic Evolution Rules (MAH, Merger Rate, Spin)

<!-- Sibling dependencies: global_semantic_rules.md, semantic_distribution_rules.md, audit_checklist.md -->

## 1. Sub-Architecture Rules

* **Evolution Lineplots:** 3x3 Grid (Rows: 5 most massive, 5 average mass, 5 least massive). Mass ranges are calculated/selected at the lowest available redshift. **CRITICAL:** For "least massive", you MUST explicitly filter out halos with mass $\le 0$ before selection. You MUST extract a unique ID (e.g., original `SubhaloIndex` or array position) for every plotted halo to populate the legends. If using array positions as a fallback, format the string clearly (e.g., `"Idx: 1542"`) so the user knows it is an index and not a native simulation ID. Use `sage_validation_utils.plot_3x3_evolution()` and pass these unique identifiers via the `halo_ids` argument.

## 2. Extraction & Parity Constraints

* **1:1 Topological Extraction & Memory Management:** Parse the output HDF5 first to identify the exact `OriginalID`s of the massive target roots at $z=0$. Then, perform a targeted, single-pass sweep of the raw ASCII input, extracting ONLY the progenitor branch halos matching those specific IDs.
* **Topological Confinement:** Always restrict topological branch tracing to a specific tree root ID (`Tree_root_ID` or equivalent). Do not traverse globally across the entire dataset.
* **Temporal Padding:** When plotting evolution branches (e.g. `mah`, `merger_rate`), if the output branch is missing snapshots compared to the input branch, you MUST pad the missing indices with `np.nan`, NEVER `0.0`.
* **Performance - Index-First Pattern:** When performing topological matching, build a local lookup dictionary for the current tree's indices once (e.g., mapping `SubhaloIndex` to array index), rather than using computationally expensive linear searches (like `np.where`) inside a halo iteration loop.
