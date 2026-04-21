# Syntactic & Functional Validation Rules

<!-- Sibling dependencies: sage_hdf5_schema.md -->

## 1. Syntactic Validation (Structural Correctness)

* **File Integrity:** Check that the generated file can be opened by standard tools (e.g., `h5dump` for HDF5). If `h5dump` is unavailable natively, fall back to using Python's `h5py` library to recursively dump and inspect the HDF5 structure.
* **Schema Compliance:** Verify that all output HDF5 data explicitly maps to the datasets listed in `references/sage_hdf5_schema.md` using the LHaloTree naming convention, and that the root attributes (`Ntrees`, `TotNHalos`) and groups (`/Tree<X>/`) are properly defined.
* **Pointer Integrity:** Verify that all `FirstProgenitor`, `NextProgenitor`, and `Descendant` pointers point to valid halos within the same tree or snapshot.
* **Snapshot Consistency:** Ensure all halos have valid snapshot numbers within the expected range (e.g., 0 to $N$).

## 2. Functional Validation (SAGE Compatibility)

* **Small Sample Test:** Always generate a small test sample (e.g., the 100 most massive halos) before full conversion. **MEMORY CRITICAL:** When parsing huge raw inputs (especially `.dat` or `.txt` files) to extract this sample, you MUST use memory-efficient two-pass reading or iterators. Do NOT append massive string payloads into Python lists, as this will trigger an out-of-memory (OOM) freeze. The test conversion should be named `0_test_sage_tree_<name_of_the_dataset>.hdf5`.
* **SAGE Dry Run:** If SAGE is available in the environment, attempt to run it on the test sample. The test run should be named `0_test_sage_run_<name_of_the_dataset>.hdf5`.
* **Full Dataset Conversion:** Once the test sample is successfully validated, execute the conversion on the full dataset. The final output file MUST strictly be named `0_full_sage_tree_<name_of_the_dataset>.hdf5`.
* **Error Parsing:** If SAGE fails, analyse its error logs (e.g., `sage.log`) to identify missing fields or incorrect pointer structures.
* **Statistical Comparison:** If possible, compare the stellar mass function or halo mass function from a previous successful run with the results of the new conversion.
