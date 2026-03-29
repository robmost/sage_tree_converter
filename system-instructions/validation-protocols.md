# Validation Protocols: Ensuring Conversion Accuracy

The conversion of merger trees from any simulation format to SAGE's requirements must be verified at three distinct levels: Syntactic, Semantic, and Functional.

## 1. Syntactic Validation (Structural Correctness)

Ensures the output file is a correctly formatted SAGE tree (Binary or HDF5).

* **File Integrity:** Check that the generated file can be opened by standard tools (e.g., `h5dump` for HDF5).
* **Pointer Integrity:** Verify that all `FirstProgenitor`, `NextProgenitor`, and `Descendant` pointers point to valid halos within the same tree or snapshot.
* **Snapshot Consistency:** Ensure all halos have valid snapshot numbers within the expected range (e.g., 0 to $N$).

## 2. Semantic Validation (Physical Consistency)

Ensures the data values are physically meaningful and follow expected trends.

* **Mass Growth:** Verify that subhalos generally increase in mass as they evolve (allowing for some tidal stripping).
* **Velocity Distributions:** Check that velocities are within typical cosmological ranges (e.g., 0 to 5000 km/s).
* **Spatial Integrity:** Confirm that halos in a tree are spatially clustered and don't "jump" across the simulation volume (unless wrapping at box boundaries).
* **Unit Conversion Check:** Compare the mass/position distribution of a small sample against the original simulation documentation.

## 3. Functional Validation (SAGE Compatibility)

Ensures that SAGE can actually load and process the converted trees.

* **Small Sample Test:** Always generate a small test sample (e.g., the 100 most massive halos) before full conversion.
* **SAGE Dry Run:** If SAGE is available in the environment, attempt to run it on the test sample.
* **Error Parsing:** If SAGE fails, analyze its error logs (e.g., `sage.log`) to identify missing fields or incorrect pointer structures.
* **Statistical Comparison:** If possible, compare the stellar mass function or halo mass function from a previous successful run with the results of the new conversion.

---

## 4. Automation Steps for the LLM

1. **Generate Validation Script:** Create a Python script that reads the converted tree and checks pointer integrity and physical bounds.
2. **Report Validation Results:** Present a summary of any warnings or errors found during the syntactic and semantic checks.
3. **Propose Fixes:** If validation fails, use the findings to adjust the mapping and rerun the test conversion.
