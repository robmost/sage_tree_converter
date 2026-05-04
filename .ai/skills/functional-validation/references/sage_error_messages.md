# Common SAGE Error Messages and Causes

When SAGE exits with a non-zero status, check `assets/sage_stdout.log` for these
common messages. Match the error, identify the cause, and apply the fix.

---

## Schema / HDF5 Errors

| Error message (partial) | Cause | Fix |
| ----------------------- | ----- | --- |
| `Could not open tree file` | Wrong path in `TreeName` parameter | Correct the path in `assets/test_sage_params.par` |
| `Error reading TreeNHalos` | `Header/TreeNHalos` is an attribute instead of a dataset, or is missing | Fix the driver to write `TreeNHalos` as an HDF5 dataset |
| `Field X not found in Tree0` | Mandatory SAGE field missing from the tree group | Add the missing field to the driver output |
| `Wrong number of trees` | `NtreesPerFile` attribute does not match the number of `Tree<X>` groups | Ensure the driver sets `NtreesPerFile` correctly |
| `hdf5 error` / `H5Dopen failed` | Dataset does not exist or has wrong name (case-sensitive) | Verify field names match exactly (e.g. `Group_M_Crit200` not `M_crit200`) |

## Dtype / Shape Errors

| Error message (partial) | Cause | Fix |
| ----------------------- | ----- | --- |
| `Wrong datatype for field X` | Dataset written with wrong HDF5 dtype (e.g. float64 instead of float32) | Cast to the correct dtype before writing: `arr.astype(np.float32)` |
| `Wrong shape for field X` | Vector field (Pos, SubhaloVel, SubhaloSpin) stored as (3, N) instead of (N, 3) | Transpose the array before writing |
| `MostBoundID must be int64` | MostBoundID written as int32 | Write as `arr.astype(np.int64)` |

## Pointer / Topology Errors

| Error message (partial) | Cause | Fix |
| ----------------------- | ----- | --- |
| `Invalid Descendant index` | Descendant pointer out of range or pointing to wrong snapshot | Re-run pointer reconstruction; verify temporal ordering |
| `Progenitor at wrong snapshot` | Progenitor halo is at the same or later snapshot than its descendant | Fix snapshot ordering in pointer reconstruction |
| `FOF group pointer crosses snapshot` | `FirstHaloInFOFGroup` or `NextHaloInFOFGroup` points to a different snapshot | Fix the FOF group chain builder to group halos by snapshot |

## Mass / Unit Errors

| Error message (partial) | Cause | Fix |
| ----------------------- | ----- | --- |
| `Unreasonable halo mass` | Mass not in 10¹⁰ M☉/h; typically off by 1e10 | Check unit conversion; apply `* 1e-10` if source is in M☉/h |
| `NaN or Inf in Group_M_Crit200` | Division by zero or log of zero in conversion | Check for halos with zero mass in the input and handle them |
| `Positions out of box` | Positions in kpc/h instead of Mpc/h | Apply `* 1e-3` unit conversion |

## SAGE Parameter File Errors

| Error message (partial) | Cause | Fix |
| ----------------------- | ----- | --- |
| `Unknown TreeType` | `TreeType` value not recognised | Use `lhalo_hdf5` (for LHaloTree HDF5 files). **Do not** use `lhalotree` — SAGE's HDF5 reader expects `lhalo_hdf5` |
| `Tag 'TreeExtension' not allowed` | `TreeExtension` key present in the parameter file — SAGE's `lhalo_hdf5` reader does not accept it | Remove the `TreeExtension` line from the parameter file entirely |
| `Can't open <TreeName>.<N>.hdf5` / `Could not open tree file` | SAGE appends `.<FileIndex>.hdf5` to `TreeName` when constructing the path; if the output file does not have this suffix it will not be found | Rename the output HDF5 to `<TreeName>.0.hdf5` before running SAGE, and set `SimulationDir` to the containing directory and `TreeName` to the base name without the `.0.hdf5` suffix |
| `Dataset 'Tree0/<field>' not found` | A mandatory dataset is present in the HDF5 but under a different name than SAGE expects | Check that all field names exactly match the schema (e.g. `SubhaloLen` not `Len`, `SubhaloIDMostBound` not `MostBoundID`, `SubhaloPos` not `Pos`). The SAGE `lhalo_hdf5` driver is case- and name-sensitive |
| `Output snapshot not in range` | `LastSnapShotNr` value exceeds the number of snapshots | Set `LastSnapShotNr` to `max(SnapNum)` from the test output file |
| `Could not create output directory` | `OutputDir` path does not exist | Create it with `mkdir -p assets/sage_test_output` |
| `Missing required parameter X` | Parameter not set in the `.par` file | Add the parameter with its default value; consult SAGE documentation |

## Diagnosing Unknown Errors

If the error is not in this table:

1. Read the full `assets/sage_stdout.log` — SAGE often prints the line number in
   its source code alongside the error.
2. Search the SAGE source repository for the exact error string to understand the
   context.
3. If the error is clearly in the HDF5 structure (wrong field name, dtype, shape),
   fix the driver. If it is in the SAGE parameter file, fix the parameter file.
4. After any fix to the driver, re-run syntactic validation before re-running SAGE.
