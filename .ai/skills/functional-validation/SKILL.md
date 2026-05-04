---
name: functional-validation
description: Runs a SAGE dry run on a converted test file to validate functional
             correctness. Use after syntactic validation passes, if SAGE_BINARY_PATH
             is set in .env.
---

# Functional Validation

## Instructions

## Path Convention

- **`.ai/skills/functional-validation/references/<file>`** — files in this skill's own `references/` subfolder.

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

Record this in the validation log and proceed to Gate G2 without running SAGE.
Do not treat this as a FAIL.

### 2. Extract the snapshot scale-factor list

**This step is mandatory.** SAGE rejects an empty `FileWithSnapList` with a fatal
error. Do not skip this step even if a snap list file appears to be unavailable.

Run a streaming scan of the input data file to collect all unique `(snap_idx, scale_factor)` pairs and write them to `assets/<dataset>_snaplist.txt`, one scale factor per line ordered by snap_idx ascending:

```bash
$PYTHON_BIN - <<'EOF'
import sys
snap_to_scale = {}
with open("<input_dat_file>", "r") as fh:
    for raw in fh:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 32:
            continue
        try:
            scale = float(parts[0])   # column 0 = scale factor
            snap  = int(float(parts[31]))  # column 31 = snap_idx
        except ValueError:
            continue
        snap_to_scale.setdefault(snap, scale)
snaps = sorted(snap_to_scale)
print(f"Found {len(snaps)} snapshots: {snaps[0]}–{snaps[-1]}", file=sys.stderr)
with open("assets/<dataset>_snaplist.txt", "w") as out:
    for s in snaps:
        out.write(f"{snap_to_scale[s]:.8f}\n")
EOF
```

Column indices above apply to Rockstar/Consistent Trees ASCII. For other formats:

- **Other ASCII formats (AHF, plain Consistent Trees variants):** identify the
  scale-factor and snap-index columns from the driver's column map and adjust
  `parts[0]` and `parts[31]` accordingly.
- **Binary LHaloTree input (e.g., Subfind/Millennium):** there are no ASCII columns.
  Extract `SnapNum` values from tree 0 of the converted output, then pair each unique
  snapshot index with its scale factor from simulation metadata (e.g., a `snaplist.txt`
  or `snap_times.txt` file in the input directory, or a cosmological parameter file):

  ```bash
  $PYTHON_BIN - <<'EOF'
  import h5py, sys
  snap_to_scale = {}
  # Load scale factors from the simulation's own snap list
  with open("<sim_dir>/snap_times.txt") as sf:
      scales = [float(l) for l in sf if l.strip()]
  with h5py.File("assets/test_<base>_STC.0.hdf5", "r") as f:
      snaps = set(f["Tree0"]["SnapNum"][:].tolist())
  for s in sorted(snaps):
      snap_to_scale[s] = scales[s]
  with open("assets/<dataset>_snaplist.txt", "w") as out:
      for s in sorted(snap_to_scale):
          out.write(f"{snap_to_scale[s]:.8f}\n")
  EOF
  ```

  If no external snap list exists, check the input directory for `snap_times.txt`,
  `output_list.txt`, or a Gadget parameter file with `TimeOfFirstSnapshot` /
  `TimeBetSnapshot` entries. If none are found, flag this to the user before continuing.

### 3. Generate a minimal SAGE parameter file

Write a parameter file to `assets/test_sage_params.par` using the template from
`.ai/skills/functional-validation/references/sage_parameter_template.md`. Fill in all placeholders for the current
simulation. **Use the correct `TreeType` for the output format:**

| Output format | SAGE parameter | File extension read by SAGE |
|---|---|---|
| `lhalo_hdf5` | `TreeType = lhalo_hdf5` | `.hdf5` (set `TreeExtension = .hdf5`) |
| `lhalo_binary` | `TreeType = lhalo_binary` | none (leave `TreeExtension` unset or empty) |

**Stage 2 output naming (mandatory).** See AGENTS.md §13 for the canonical `<base>` derivation rule and the input directory enforcement guard. The test conversion must have been run with the path below; if the conversion was run with a different path, re-run it with the correct path before proceeding.

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
units of 10¹⁰ M☉/h (same value used by the driver).

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
5. Re-run the conversion:
   ```bash
   $PYTHON_BIN conversion-engine/main_driver.py \
       --input <...> \
       --output assets/test_<base>_STC.0[.hdf5] \
       --output-format [lhalo_hdf5|lhalo_binary] \
       --n-trees 100
   ```
6. Re-run syntactic validation (all six checks).
7. If syntactic validation passes, re-run SAGE from step 3.
8. Repeat until SAGE exits with status 0.

### 6. PASS condition

SAGE exits with status 0 **and** no error messages appear in `assets/sage_stdout.log`
or any log files SAGE produces.

Record in the validation log:
```text
Functional validation: PASS
SAGE exit code: 0
```
