---
name: kdb-update
description: Updates an existing KDB schema mapping JSON with new information
             discovered during a conversion session. Use in Stage 4 when the input
             format was found in the KDB but the session revealed missing or
             incorrect information in the existing entry.
---

# kdb-update

## Role

This skill is invoked in Stage 4 when the session started with a KDB match but the conversion revealed that the existing entry was incomplete or incorrect. It updates the KDB in a targeted, auditable way — preserving correct fields and correcting only what the session proved wrong.

**Prerequisite:** Stage 3 must have completed successfully (G3 passed). The existing KDB entry at `format-database/<format_id>.json` must have been read and compared against session findings.

---

## Steps

## Path Convention

Two path prefixes are used in this skill:
- **`.ai/skills/kdb-update/references/<file>`** — files in this skill's own `references/` subfolder.
- **`format-database/<file>`** — the project-root format database directory.

### Step 1 — Present the diff

Before writing anything, show the user a structured diff of what the existing KDB entry contains versus what the session discovered. Use the format in `.ai/skills/kdb-update/references/diff_format_guide.md`.

The diff must cover:

- **Corrected fields**: fields that existed but had wrong values (e.g. incorrect unit scaling factor, wrong field name, incorrect pointer type)
- **New fields**: fields that were missing from the existing entry (e.g. newly discovered caveats, additional optional field mappings)
- **Unchanged fields**: list these briefly so the user can confirm no regressions

Example output format:

```text
KDB Update Diff — <format_id>
=============================

CORRECTED:
  field_map.Group_M_Crit200.unit_conversion_factor:  1e-10 → 1e-9  (was wrong, fixed during test run)
  pointer_reconstruction.method:  "pre_built" → "global_id_links"  (format uses IDs not pre-built indices)

NEW:
  caveats[+]:  "SubhaloSpin values are zero for satellite halos in this format version"

UNCHANGED:
  halo_finder, tree_tool, file_format, field_map.SnapNum, field_map.Descendant, ...
```

---

### Step 2 — Confirm with the user

After presenting the diff, ask the user explicitly:

```text
The above diff summarises the changes to format-database/<format_id>.json.
Please confirm:
  - Which corrected fields should be applied?  (type "all" or list by name)
  - Which new fields should be added?           (type "all" or list by name)
  - Are there any changes in the diff that should NOT be written?
```

Do not write any changes until the user responds. If the user selects a subset, apply only the confirmed subset.

---

### Step 3 — Update the JSON in place

Read the existing `format-database/<format_id>.json`. Apply only the confirmed changes. Do not overwrite fields that were not in the confirmed diff.

Use a targeted update strategy:

```python
import json

with open("format-database/<format_id>.json") as f:
    entry = json.load(f)

# Apply only confirmed changes
entry["field_map"]["Group_M_Crit200"]["unit_conversion_factor"] = 1e-9
entry["pointer_reconstruction"]["method"] = "global_id_links"
entry["caveats"].append("SubhaloSpin values are zero for satellite halos in this format version")

with open("format-database/<format_id>.json", "w") as f:
    json.dump(entry, f, indent=2)
```

After writing, validate the JSON is well-formed and the updated fields match what was confirmed:

```bash
$PYTHON_BIN -c "import json; json.load(open('format-database/<format_id>.json'))"
```

---

### Step 4 — Record the update in the conversation example

Create `conversation-examples/<format_id>_example_<DDMMYYYY>.json` (date = today's date) following the schema in `.ai/skills/kdb-extend/references/conversation_example_schema.md`. Set `kdb_action` to `"updated_entry"` to distinguish this from a new-format session:

```json
{
  "format_id": "<format_id>",
  "session_date": "<DDMMYYYY>",
  "input_description": "<brief description of the input files>",
  "mapping_source": "kdb_match",
  "issues_encountered": ["<description of what was wrong in the existing entry>", ...],
  "resolutions": ["<what was corrected and how>", ...],
  "kdb_action": "updated_entry",
  "outcome": "success"
}
```

If the format was already in the KDB but the session found no errors (no update needed), set `kdb_action` to `"no_change"` and omit the conversation example write (no file needed).

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

1. Confirm `format-database/<format_id>.json` is valid JSON and contains the updated values.
2. Confirm `conversation-examples/<format_id>_example_<DDMMYYYY>.json` is valid JSON and `kdb_action` is `"updated_entry"`.
3. Confirm `$AUDIT_DIR` exists and contains the expected files.
4. Present a one-line summary of what was changed to the user and request confirmation (G4).
