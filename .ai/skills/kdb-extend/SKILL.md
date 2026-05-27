---
name: kdb-extend
description: Adds a new format driver and schema mapping JSON to the KDB after a
             successful conversion of a previously unknown format. Use in Stage 4
             when the input format was not found in the KDB at session start.
---

# kdb-extend

## Role

This skill is invoked in Stage 4 when the input format was previously unknown and the session produced a working driver and confirmed schema mapping. It permanently extends the KDB so future sessions can find the format immediately.

**Prerequisite:** Stage 3 must have completed successfully (G3 passed). The driver at `assets/drivers/<format_id>.py` must have passed all syntactic and semantic validation checks.

---

## Stage Preamble

Output the following to the user verbatim before any other action:

```
Stage 4 — KDB Update
The conversion is validated. I'll register what we learned so this format is recognised immediately in future sessions.

  1. KDB action
       - new format      -> kdb-extend (add driver + JSON)
       - existing format -> kdb-update (patch entry)
  2. Archive session files
  3. Done
```

---

## Steps

## Path Convention

Two path prefixes are used in this skill:
- **`.ai/skills/kdb-extend/references/<file>`** — files in this skill's own `references/` subfolder.
- **`reference/<file>` (project root)** — files in the project-root `reference/` directory (e.g. `reference/format_database_template.json`).

### Step 1 — Copy the finalised driver

Copy the validated driver from the assets directory to the conversion engine:

```bash
cp assets/drivers/<format_id>.py conversion-engine/drivers/<format_id>.py
```

Confirm the file is present and non-empty after copying:

```bash
ls -lh conversion-engine/drivers/<format_id>.py
```

Do not modify the driver after copying. The version in `assets/drivers/` is the audited version.

---

### Step 2 — Register the driver in the format registry

Open `conversion-engine/main_driver.py` and locate `FORMAT_REGISTRY` (a `dict[str, str]` mapping `format_id` strings to driver module **names**). Add the new entry:

```python
FORMAT_REGISTRY: dict[str, str] = {
    # ... existing entries ...
    "<format_id>": "<format_id>",
}
```

The value is the module filename without the `.py` extension. `_import_driver()` resolves the module dynamically via `importlib.import_module(f"drivers.{module_name}")` — do not add a static import. Follow the exact naming convention already in the file. Do not alter any existing registry entries.

---

### Step 3 — Write the schema mapping JSON

Create `format-database/<format_id>.json` following `reference/format_database_template.json` (project root) exactly. Populate all fields discovered during the session:

- `halo_finder`, `tree_tool`, `file_format` — exact identifiers used throughout the session
- `field_map` — complete field mapping table from the confirmed `assets/proposed_mapping_<format_id>.json`
- `unit_conversions` — all unit scaling factors applied in the driver
- `pointer_reconstruction` — method used (global ID links, scale-factor links, or pre-built)
- `caveats` — any known issues, edge cases, or format quirks discovered during validation

If any field in the template is not applicable, use `null`. Do not omit keys.

If writing via Python, always use `ensure_ascii=False`:

```python
import json
with open("format-database/<format_id>.json", "w") as f:
    json.dump(entry, f, indent=2, ensure_ascii=False)
```

Without `ensure_ascii=False`, Python escapes every non-ASCII character to a `\uXXXX` sequence (e.g. `≈` → `≈`, `–` → `–`).

After writing, validate the JSON is well-formed:

```bash
$PYTHON_BIN -c "import json; json.load(open('format-database/<format_id>.json'))"
```

---

### Step 4 — Write the conversation example

Create `conversation-examples/<format_id>_example_<DDMMYYYY>.json` (date = today's date in DDMMYYYY format) following the schema in `.ai/skills/kdb-extend/references/conversation_example_schema.md`:

```json
{
  "format_id": "<format_id>",
  "session_date": "<DDMMYYYY>",
  "input_description": "<brief description of the input files>",
  "mapping_source": "web_discovery",
  "output_format": "lhalo_hdf5",
  "n_output_files": 1,
  "issues_encountered": ["<issue 1>", "<issue 2>", ...],
  "resolutions": ["<resolution 1>", "<resolution 2>", ...],
  "kdb_action": "new_driver",
  "outcome": "success"
}
```

`output_format` and `n_output_files` record the G1 choices made in this session. They are session-level context (the same format can be converted to different numbers of files for different datasets); the `format-database/*.json` KDB entries are not affected.

The `issues_encountered` and `resolutions` lists must be in the same order (each resolution corresponds to the issue at the same index). If no issues were encountered, use empty lists `[]`.

After writing, validate the JSON:

```bash
$PYTHON_BIN -c "import json; json.load(open('conversation-examples/<format_id>_example_<DDMMYYYY>.json'))"
```

---

### Step 5 — Create audit directory and archive conversion products

Determine the dataset name and construct the audit directory path:

```bash
DATASET_NAME=<dataset_name>   # human-readable label; often equals <base> (AGENTS.md §13) — confirm with the user if uncertain
TIMESTAMP=$(date +"%H%M-%d%m%Y")
AUDIT_DIR="audits/${DATASET_NAME}_audit-files_${TIMESTAMP}"
mkdir -p "$AUDIT_DIR"
```

Move Stage 2 test conversion products (HDF5 and binary cases):

```bash
mv assets/test_<base>_STC.0.hdf5  "$AUDIT_DIR/" 2>/dev/null || true
mv assets/test_<base>_STC.0        "$AUDIT_DIR/" 2>/dev/null || true
```

**IMPORTANT:** Stage 3 full conversion output (`output/<base>_STC.0.hdf5` and `output/<base>_STC.0`) remains in `output/` and is NOT moved to the audit directory. This is the final deliverable.

Move session artefacts from `assets/`:

```bash
mv assets/validation_log.md        "$AUDIT_DIR/" 2>/dev/null || true
mv assets/auditor_report.md        "$AUDIT_DIR/" 2>/dev/null || true
mv assets/test_sage_params.par     "$AUDIT_DIR/" 2>/dev/null || true
mv assets/sage_stdout.log          "$AUDIT_DIR/" 2>/dev/null || true
mv assets/sage_test_output         "$AUDIT_DIR/" 2>/dev/null || true
mv assets/semantic_validation      "$AUDIT_DIR/" 2>/dev/null || true
```

Move any snapshot list or other support files used during functional validation. These are
dataset-specific files written to `assets/` in Stage 2 (e.g. by the functional-validation
skill) and must be archived alongside the other Stage 2 products:

```bash
mv assets/*_snaplist.txt           "$AUDIT_DIR/" 2>/dev/null || true
mv assets/*_snaplist.dat           "$AUDIT_DIR/" 2>/dev/null || true
mv assets/*sim_config*.json        "$AUDIT_DIR/" 2>/dev/null || true
```

If the functional-validation skill placed the snaplist under a different name or extension,
check `assets/` for any remaining dataset-specific files before closing the session and move
them with the same pattern.

Archive the source driver (the production copy already lives in `conversion-engine/drivers/` after Step 1):

```bash
mv assets/drivers/<format_id>.py   "$AUDIT_DIR/" 2>/dev/null || true
```

Finally, remove any stale draft files that are no longer needed:

```bash
rm -f assets/proposed_mapping_<format_id>.json
rm -rf assets/drivers/__pycache__
```

The `|| true` guards prevent failure when a file was never produced (e.g. `sage_stdout.log` is absent when functional validation was skipped).

Confirm the audit directory is non-empty:

```bash
ls "$AUDIT_DIR"
```

---

## Completion

After all five steps complete:

1. Confirm `conversion-engine/drivers/<format_id>.py` exists.
2. Confirm the format registry in `conversion-engine/main_driver.py` includes the new entry.
3. Confirm `format-database/<format_id>.json` is valid JSON and non-empty.
4. Confirm `conversation-examples/<format_id>_example_<DDMMYYYY>.json` is valid JSON.
5. Confirm `$AUDIT_DIR` exists and contains the expected files.

Present a summary of what was written to the user and request confirmation (G4).
