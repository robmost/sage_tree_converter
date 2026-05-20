---
name: syntactic-validation
description: Runs the six structural checks on a converted SAGE LHaloTree HDF5
             file. Use after any conversion run — test or full — to verify the
             output file is structurally correct before proceeding.
---

# Syntactic Validation

## Stage Preamble

If the Stage 2 preamble has not already been output this session (i.e., `driver-authoring` was not read first), output the following verbatim now:

```
Stage 2 — Test Engine
I'll run a test conversion on ~100 trees and validate the output structurally.

  1. Driver check
       - exists  -> proceed to step 2
       - missing -> author driver -> proceed to step 2
  2. Test conversion (~100 trees)
  3. Syntactic validation (6 checks)
  4. Functional validation
       - SAGE binary set -> run SAGE dry-run
       - not set         -> skip
  5. [G2] Confirm test validation
```

## Format Dispatch

Determine the output format from the conversion run, then follow the appropriate path:

**`lhalo_hdf5` output** (file ends in `.hdf5`): run all six checks below via `run_syntactic_checks.py`. Continue reading this skill.

**`lhalo_binary` output** (no `.hdf5` extension, e.g. `test_<base>_STC.0`): run the binary check script instead and skip the six HDF5 checks:

```bash
$PYTHON_BIN .ai/skills/syntactic-validation/scripts/run_binary_checks.py \
    --file <output_binary_path> \
    --n-snapshots <N>
```

The binary script implements five checks: `file_readable`, `header_consistency`, `file_size_consistency`, `first_tree_pointers`, `first_tree_snapnums`. It exits with code 0 if all five pass. Record the result and proceed to Gate G2 once all five checks PASS.

---

## Instructions (lhalo_hdf5 only)

## Path Convention

Two path prefixes are used in this skill:
- **`.ai/skills/syntactic-validation/references/<file>`** — files in this skill's own `references/` subfolder.
- **`reference/<file>` (project root)** — files in the project-root `reference/` directory (e.g. `reference/sage_lhalotree_hdf5_schema.md`).

Run all six checks in order. Each check produces an explicit **PASS** or **FAIL**.
There are no partial passes. Record each result in `assets/validation_log.md`.

Run the deterministic script first:

```bash
$PYTHON_BIN .ai/skills/syntactic-validation/scripts/run_syntactic_checks.py \
    --file <output_hdf5_path> \
    --n-snapshots <N>
```

The script implements checks 2–6. Check 1 (file integrity) is done manually as
described below. The script exits with code 0 if all checks pass, non-zero otherwise.

See `.ai/skills/syntactic-validation/references/check_procedures.md` for the full pass conditions and expected output
for each check. See `.ai/skills/syntactic-validation/references/h5py_patterns.md` for Python code patterns.

---

### Check 1 — File Integrity

*Applies to `lhalo_hdf5` only.* For `lhalo_binary`, use `run_binary_checks.py` (see Format Dispatch above).

**Method:** Run `h5dump -n <file>`. If `h5dump` is not available, fall back to
opening the file with `$PYTHON_BIN -c "import h5py; h5py.File('<file>', 'r').close()"`.

**PASS:** The file opens without error and the root groups are listed.
**FAIL:** Any error opening the file (corrupt, incomplete, wrong format).

---

### Check 2 — Schema Compliance

**Method:** Compare all datasets in each `Tree<X>/` group against the mandatory
field list in `reference/sage_lhalotree_hdf5_schema.md` (project root). Also verify:
- `Header/TreeNHalos` exists as a dataset (not an attribute).
- `len(Header/TreeNHalos) == Header.attrs["NtreesPerFile"]`.
- `sum(Header/TreeNHalos) == Header.attrs["NhalosPerFile"]`.

**PASS:** All mandatory fields present in every tree group; no undocumented extra
fields; `TreeNHalos` length and sum match header attributes.
**FAIL:** Any mandatory field missing, any undocumented field present, or any
header attribute inconsistency.

Mandatory fields: `Descendant`, `FirstProgenitor`, `NextProgenitor`,
`FirstHaloInFOFGroup`, `NextHaloInFOFGroup`, `SubhaloLen`, `Group_M_Crit200`,
`SubhaloVMax`, `SubhaloIDMostBound`, `SnapNum`, `SubhaloPos`, `SubhaloVel`, `SubhaloSpin`.

---

### Check 3 — Pointer Integrity: Temporal

**Method:** For every halo in every tree, verify:
- `FirstProgenitor[i]` is `-1` or in `[0, N-1]`.
- `NextProgenitor[i]` is `-1` or in `[0, N-1]`.
- `Descendant[i]` is `-1` or in `[0, N-1]`.
- If `FirstProgenitor[i] != -1`: `SnapNum[FirstProgenitor[i]] < SnapNum[i]`.
- If `NextProgenitor[i] != -1`: `SnapNum[NextProgenitor[i]] < SnapNum[i]` (same
  snapshot as `FirstProgenitor`'s snapshot is also acceptable if it is strictly
  less than i's snapshot).
- If `Descendant[i] != -1`: `SnapNum[Descendant[i]] > SnapNum[i]`.

**PASS:** All constraints satisfied for every halo in every tree.
**FAIL:** Any out-of-range index or any snapshot ordering violation.

---

### Check 4 — Pointer Integrity: Spatial

**Method:** For every halo in every tree, verify:
- `FirstHaloInFOFGroup[i]` is `-1` or in `[0, N-1]`.
- `NextHaloInFOFGroup[i]` is `-1` or in `[0, N-1]`.
- If `FirstHaloInFOFGroup[i] != -1`: `SnapNum[FirstHaloInFOFGroup[i]] == SnapNum[i]`.
- If `NextHaloInFOFGroup[i] != -1`: `SnapNum[NextHaloInFOFGroup[i]] == SnapNum[i]`.

**PASS:** All constraints satisfied.
**FAIL:** Any out-of-range index or any cross-snapshot spatial link.

---

### Check 5 — Snapshot Consistency

**Method:** For every halo in every tree, verify `SnapNum[i]` is in
`[0, n_snapshots - 1]` where `n_snapshots` is provided via `--n-snapshots`.

If `--n-snapshots` is not known, use `max(SnapNum)` over all trees as a lower bound
and report a note that the upper bound was not verified.

**PASS:** All `SnapNum` values are non-negative integers within the valid range.
**FAIL:** Any `SnapNum` value is negative or exceeds `n_snapshots - 1`.

---

### Check 6 — Property Consistency

**Method:** For every halo in every tree, verify:
- `Group_M_Crit200[i]` is in `[0.0, 1e6]` (units: 10¹⁰ M☉/h).
- `|SubhaloVel[i]|` is in `[0, 10000]` km/s (physically reasonable upper bound).
- `|SubhaloVMax[i]|` is in `[0, 10000]` km/s.
- `SubhaloPos[i, :]` values are finite (not NaN or Inf).
- `Group_M_Crit200[i]` is finite (not NaN or Inf).

**PASS:** All values within physically reasonable bounds; no NaN or Inf.
**FAIL:** Any value outside bounds or any NaN/Inf.

---

### On any FAIL

1. Identify the root cause: is it a driver bug, a unit conversion error, or a
   pointer reconstruction error?
2. Fix the driver in `assets/drivers/<format_id>.py`.
3. Re-run the conversion.
4. Re-run **all six checks from Check 1**. Do not skip checks that previously passed.
5. Repeat until all six checks PASS.
