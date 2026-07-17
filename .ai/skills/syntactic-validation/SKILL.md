---
name: syntactic-validation
description: Runs the six structural checks on a converted SAGE LHaloTree HDF5
             file. Use after any conversion run - test or full - to verify the
             output file is structurally correct before proceeding.
---

# Syntactic Validation

## Stage Preamble

If the Stage 2 preamble has not already been output this session, output it now, verbatim, from AGENTS.md Section 15. Never re-output a preamble that has already been shown, and never paraphrase it.

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
- **`.ai/skills/syntactic-validation/references/<file>`** - files in this skill's own `references/` subfolder.
- **`reference/<file>` (project root)** - files in the project-root `reference/` directory (e.g. `reference/sage_lhalotree_hdf5_schema.md`).

Run the deterministic script. It implements **all six checks**, including
Check 1 (file integrity, verified by opening the file with h5py). Do not
re-perform any check manually - the script is the procedure.

```bash
$PYTHON_BIN .ai/skills/syntactic-validation/scripts/run_syntactic_checks.py \
    --file <output_hdf5_path> \
    --n-snapshots <N>
```

The script exits with code 0 if all checks pass, non-zero otherwise. Each check
reports an explicit **PASS** or **FAIL** - there are no partial passes. Record
the results in `assets/validation_log.md`.

What each check verifies (for diagnosing a FAIL):

| # | Check | Verifies |
| - | ----- | -------- |
| 1 | File integrity | The file opens as valid HDF5. |
| 2 | Schema compliance | All mandatory fields in every `Tree<X>/` group with exact dtypes; no undocumented fields; `TreeNHalos` length and sum match the `NtreesPerFile` / `NhalosPerFile` header attributes. |
| 3 | Pointer integrity, temporal | `Descendant` / `FirstProgenitor` / `NextProgenitor` are `-1` or in-range, progenitors at earlier snapshots, descendants at later snapshots. |
| 4 | Pointer integrity, spatial | `FirstHaloInFOFGroup` / `NextHaloInFOFGroup` are `-1` or in-range and point within the same snapshot. |
| 5 | Snapshot consistency | Every `SnapNum` is in `[0, n_snapshots - 1]` (`--n-snapshots` enables the upper bound; without it only a lower-bound note is reported). |
| 6 | Property consistency | Masses in `[0, 1e6]` (10^10 Msun/h), velocity magnitudes below 10000 km/s, all values finite (no NaN/Inf). |

See `.ai/skills/syntactic-validation/references/check_procedures.md` for the full
pass conditions per check, and `.ai/skills/syntactic-validation/references/h5py_patterns.md`
for h5py patterns when diagnosing a failure.

---

### On any FAIL

1. Identify the root cause: is it a driver bug, a unit conversion error, or a
   pointer reconstruction error?
2. Fix the driver in `assets/drivers/<format_id>.py`.
3. Re-run the conversion.
4. Re-run **all six checks from Check 1**. Do not skip checks that previously passed.
5. Repeat until all six checks PASS.
