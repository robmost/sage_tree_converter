---
name: functional-validation
description: Runs a SAGE dry run on a converted test file to validate functional
             correctness. Use after syntactic validation passes, if SAGE_BINARY_PATH
             is set in .env.
---

# Functional Validation

## Instructions

## Path Convention

- **`.ai/skills/functional-validation/references/<file>`** - files in this skill's own `references/` subfolder.

This skill is invoked in Stage 2, after syntactic validation passes.

### 1. Check for SAGE_BINARY_PATH

Read `SAGE_BINARY_PATH` from `.env`:

```bash
grep -E '^SAGE_BINARY_PATH=' .env | cut -d= -f2-
```

If the variable is absent, empty, or commented out:

```text
Functional validation: NOT RUN
Reason: SAGE_BINARY_PATH not set in .env. Skipping functional validation.
```

Record this in `assets/validation_log.md` and proceed to Gate G2 without running SAGE.
Do not treat this as a FAIL.

**Running inside Docker or Apptainer:** if `SAGE_BINARY_PATH` is set but the binary
is not accessible inside the container, functional validation is also reported as
`NOT RUN` (not `FAIL`). To enable it, bind-mount the SAGE binary directory - see
`README.md` Section SAGE Binary for Functional Validation.

### 2. Extract the snapshot scale-factor list

**This step is mandatory.** SAGE rejects an empty `FileWithSnapList` with a fatal
error. Do not skip this step even if a snap list file appears to be unavailable.

Use the checked-in script - do not write an ad-hoc scan:

- **ASCII inputs** (Rockstar/Consistent Trees and similar column formats):

  ```bash
  $PYTHON_BIN scripts/extract_snaplist.py ascii \
      --input <input_dat_file> \
      --out assets/<dataset>_snaplist.txt
  ```

  The defaults (`--scale-col 0 --snap-col 31`) match Rockstar/Consistent Trees.
  For other ASCII formats (e.g. AHF), identify the scale-factor and snap-index
  columns from the driver's column map and pass `--scale-col` / `--snap-col`.

- **Binary LHaloTree input** (e.g. Subfind/Millennium - no ASCII columns): pair
  the converted output's `SnapNum` values with the simulation's own scale list
  (`snap_times.txt`, `output_list.txt`, or similar in the input directory):

  ```bash
  $PYTHON_BIN scripts/extract_snaplist.py hdf5-output \
      --output-file assets/test_<base>_STC.0.hdf5 \
      --scales-file <sim_dir>/snap_times.txt \
      --out assets/<dataset>_snaplist.txt
  ```

  If no external scale list exists, check the input directory for a Gadget
  parameter file with `TimeOfFirstSnapshot` / `TimeBetSnapshot` entries. If
  none are found, flag this to the user before continuing.

### 3. Generate a minimal SAGE parameter file

Write a parameter file to `assets/test_sage_params.par` using the template from
`.ai/skills/functional-validation/references/sage_parameter_template.md`. Fill in all placeholders for the current
simulation. **Use the correct `TreeType` for the output format:**

| Output format | SAGE parameter | File extension read by SAGE |
|---|---|---|
| `lhalo_hdf5` | `TreeType = lhalo_hdf5` | `.hdf5` (set `TreeExtension = .hdf5`) |
| `lhalo_binary` | `TreeType = lhalo_binary` | none (leave `TreeExtension` unset or empty) |

**Stage 2 output naming (mandatory).** See AGENTS.md Section 13 for the canonical `<base>` derivation rule and the input directory enforcement guard. The test conversion must have been run with the path below; if the conversion was run with a different path, re-run it with the correct path before proceeding.

| Output format | CLI flags |
| ------------- | --------- |
| `lhalo_hdf5`   | `--output assets/test_<base>_STC.0.hdf5 --output-format lhalo_hdf5` |
| `lhalo_binary` | `--output assets/test_<base>_STC.0      --output-format lhalo_binary` |

**Multi-file naming requirement.** SAGE appends `.<N>.hdf5` (HDF5) or `.<N>` (binary)
to `TreeName` when opening files. Set `TreeName = test_<base>_STC` (strip the suffix).
Set `FirstFile = 0` and `LastFile = 0` for a single-file run.

**Binary particle_mass requirement.** For `lhalo_binary`, the binary file contains no
particle mass field. SAGE reads `PartMass` from the parameter file instead. Ensure the
`PartMass` line in `assets/test_sage_params.par` is set to the correct value in
units of 10^10 Msun/h (same value used by the driver). The value comes from
`--sim-config` (key: `particle_mass_msun_per_h`, converted to 10^10 Msun/h) or the
driver's auto-detection/default.

Create the output directory:
```bash
mkdir -p assets/sage_test_output
```

### 4. Run SAGE

```bash
$SAGE_BINARY_PATH assets/test_sage_params.par > assets/sage_stdout.log 2>&1
```

Record the exit code:
```bash
echo "SAGE exit code: $?"
```

Capture both stdout and any log file SAGE produces (look for files matching
`assets/sage_test_output/*.log` or similar).

### 5. On non-zero exit: diagnose and fix

1. Read `assets/sage_stdout.log` and any SAGE log files produced.
2. Look up the error in `.ai/skills/functional-validation/references/sage_error_messages.md`.
3. Identify whether the error is caused by:
   - A schema violation in the output HDF5 (wrong field name, wrong dtype, missing field)
   - A unit error (mass in wrong units, positions in wrong units)
   - A pointer error (invalid index, cross-snapshot pointer)
   - A SAGE parameter file error (wrong path, wrong tree type)
4. Fix the driver in `assets/drivers/<format_id>.py` or the parameter file.
5. Re-run the test conversion. **Use the invocation that matches where the
   driver lives:**
   - **Draft driver in `assets/drivers/`** (new format, not yet registered in
     `FORMAT_REGISTRY`): invoke `convert()` as a library function exactly as in
     `driver-authoring` SKILL.md Section 9. Do not go through `main_driver.py` -
     it cannot resolve an unregistered format.
   - **Registered driver in `conversion-engine/drivers/`:**
     ```bash
     $PYTHON_BIN conversion-engine/main_driver.py \
         --input <...> \
         --output assets/test_<base>_STC.0[.hdf5] \
         --format <format_id> \
         --output-format [lhalo_hdf5|lhalo_binary] \
         --n-trees 100
     ```
6. Re-run syntactic validation (all six checks).
7. If syntactic validation passes, re-run SAGE (step 4).
8. Repeat until SAGE exits with status 0.

### 6. PASS condition

SAGE exits with status 0 **and** no error messages appear in `assets/sage_stdout.log`
or any log files SAGE produces.

Record in `assets/validation_log.md`:
```text
Functional validation: PASS
SAGE exit code: 0
```
