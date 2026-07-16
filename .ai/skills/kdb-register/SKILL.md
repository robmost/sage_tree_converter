---
name: kdb-register
description: Registers the session's findings in the KDB after a validated
             conversion. Use in Stage 4 - Path A adds a new driver and schema
             mapping for a previously unknown format; Path B patches an
             existing KDB entry the session proved incomplete or wrong. Both
             paths archive the session files.
---

# kdb-register

## Role

This skill closes a conversion session by making its findings durable. It has
two paths; pick exactly one, then run the shared closing steps:

- **Path A - new format** (the session started with no KDB match and produced
  a new driver in `assets/drivers/`): add the driver and schema mapping JSON
  to the KDB.
- **Path B - existing format** (the session started from a KDB match): patch
  the existing entry only where the session proved it incomplete or wrong. If
  nothing was wrong, no KDB change is made.

**Prerequisite for both paths:** Stage 3 completed successfully (G3 recorded
in `assets/session_state.json`).

## Stage Preamble

If the Stage 4 preamble has not already been output this session, output it now, verbatim, from AGENTS.md Section 15. Never re-output a preamble that has already been shown, and never paraphrase it.

## Path Convention

Two path prefixes are used in this skill:
- **`.ai/skills/kdb-register/references/<file>`** - files in this skill's own `references/` subfolder.
- **`reference/<file>` (project root)** - files in the project-root `reference/` directory (e.g. `reference/format_database_template.json`).

---

## Path A - New Format

### A1. Copy the finalised driver

```bash
cp assets/drivers/<format_id>.py conversion-engine/drivers/<format_id>.py
ls -lh conversion-engine/drivers/<format_id>.py
```

Do not modify the driver after copying. The version in `assets/drivers/` is the audited version.

### A2. Register the driver in the format registry

Open `conversion-engine/main_driver.py` and locate `FORMAT_REGISTRY` (a `dict[str, str]` mapping `format_id` strings to driver module **names**). Add the new entry:

```python
FORMAT_REGISTRY: dict[str, str] = {
    # ... existing entries ...
    "<format_id>": "<format_id>",
}
```

The value is the module filename without the `.py` extension. `_import_driver()` resolves the module dynamically via `importlib.import_module(f"drivers.{module_name}")` - do not add a static import. Do not alter any existing registry entries.

### A3. Write the schema mapping JSON

Create `format-database/<format_id>.json` following `reference/format_database_template.json` (project root) exactly. Populate all fields discovered during the session:

- `halo_finder`, `tree_tool`, `file_format` - exact identifiers used throughout the session
- `memory_multiplier` - format-aware value for the memory pre-check (3.0 for binary/HDF5 inputs, 12-15 for ASCII inputs; see AGENTS.md Section 8)
- `field_map` - complete field mapping table from the confirmed `assets/proposed_mapping_<format_id>.json`
- `unit_conversions` - all unit scaling factors applied in the driver
- `pointer_reconstruction` - method used (global ID links, scale-factor links, or pre-built)
- `caveats` - any known issues, edge cases, or format quirks discovered during validation

If any field in the template is not applicable, use `null`. Do not omit keys.

If writing via Python, always use `ensure_ascii=False` (without it, Python escapes every non-ASCII character to a `\uXXXX` sequence):

```python
import json
with open("format-database/<format_id>.json", "w") as f:
    json.dump(entry, f, indent=2, ensure_ascii=False)
```

After writing, validate:

```bash
$PYTHON_BIN -c "import json; json.load(open('format-database/<format_id>.json'))"
```

Then continue with the **Shared Closing Steps**.

---

## Path B - Existing Format

### B1. Present the diff

Before writing anything, show the user a structured diff of what the existing KDB entry contains versus what the session discovered. Use the format in `.ai/skills/kdb-register/references/diff_format_guide.md`.

The diff must cover:

- **Corrected fields**: fields that existed but had wrong values (e.g. incorrect unit scaling factor, wrong field name, incorrect pointer type)
- **New fields**: fields that were missing from the existing entry (e.g. newly discovered caveats, additional optional field mappings)
- **Unchanged fields**: list these briefly so the user can confirm no regressions

Example output format:

```text
KDB Update Diff - <format_id>
=============================

CORRECTED:
  field_map.Group_M_Crit200.unit_conversion_factor:  1e-10 -> 1e-9  (was wrong, fixed during test run)
  pointer_reconstruction.method:  "pre_built" -> "global_id_links"  (format uses IDs not pre-built indices)

NEW:
  caveats[+]:  "SubhaloSpin values are zero for satellite halos in this format version"

UNCHANGED:
  halo_finder, tree_tool, file_format, field_map.SnapNum, field_map.Descendant, ...
```

If the session found **no errors** in the existing entry, state that, skip B2
and B3, and continue with the Shared Closing Steps (`kdb_action` is
`"no_change"` and no conversation example is written).

### B2. Confirm with the user

```text
The above diff summarises the changes to format-database/<format_id>.json.
Please confirm:
  - Which corrected fields should be applied?  (type "all" or list by name)
  - Which new fields should be added?           (type "all" or list by name)
  - Are there any changes in the diff that should NOT be written?
```

Do not write any changes until the user responds. If the user selects a subset, apply only the confirmed subset.

### B3. Update the JSON in place

Read the existing `format-database/<format_id>.json`. Apply only the confirmed changes. Do not overwrite fields that were not in the confirmed diff.

```python
import json

with open("format-database/<format_id>.json") as f:
    entry = json.load(f)

# Apply only confirmed changes, e.g.:
entry["field_map"]["Group_M_Crit200"]["unit_conversion_factor"] = 1e-9

with open("format-database/<format_id>.json", "w") as f:
    json.dump(entry, f, indent=2, ensure_ascii=False)
```

**Encoding note:** always pass `ensure_ascii=False` to `json.dump()` so existing Unicode in the file is not corrupted.

After writing, validate:

```bash
$PYTHON_BIN -c "import json; json.load(open('format-database/<format_id>.json'))"
```

Then continue with the **Shared Closing Steps**.

---

## Shared Closing Steps

### S1. Write the conversation example

Skip this step only when Path B found no errors (`kdb_action` = `"no_change"`).

Create `conversation-examples/<format_id>_example_<DDMMYYYY>.json` (date = today's date in DDMMYYYY format) following the schema in `.ai/skills/kdb-register/references/conversation_example_schema.md`:

```json
{
  "format_id": "<format_id>",
  "session_date": "<DDMMYYYY>",
  "input_description": "<brief description of the input files>",
  "mapping_source": "web_discovery | kdb_match",
  "output_format": "lhalo_hdf5",
  "n_output_files": 1,
  "issues_encountered": ["<issue 1>", "<issue 2>"],
  "resolutions": ["<resolution 1>", "<resolution 2>"],
  "kdb_action": "new_driver | updated_entry",
  "outcome": "success"
}
```

Set `kdb_action` to `"new_driver"` (Path A) or `"updated_entry"` (Path B).
`output_format` and `n_output_files` record the G1 choices from
`assets/session_state.json`; they are session-level context and do not affect
the `format-database/*.json` entries. `issues_encountered` and `resolutions`
must be in the same order (each resolution corresponds to the issue at the
same index); use empty lists `[]` if no issues were encountered.

After writing, validate:

```bash
$PYTHON_BIN -c "import json; json.load(open('conversation-examples/<format_id>_example_<DDMMYYYY>.json'))"
```

### S2. Archive the session files

Read `dataset_name`, `base`, and `format_id` from `assets/session_state.json`
(`dataset_name` is a human-readable label, often equal to `base` - confirm
with the user if uncertain), then run:

```bash
bash scripts/archive_session.sh <dataset_name> <base> <format_id>
```

The script moves the Stage 2 test outputs and all session artefacts (including
`assets/session_state.json`) into `audits/<dataset_name>_audit-files_<HHMM-DDMMYYYY>/`
and prints its contents. The Stage 3 full conversion output in `output/` is the
final deliverable and is **not** moved. If the script reports an empty audit
directory, investigate before closing the session.

### S3. Completion

Confirm, as applicable to the path taken:

1. Path A: `conversion-engine/drivers/<format_id>.py` exists and `FORMAT_REGISTRY` includes the new entry.
2. `format-database/<format_id>.json` is valid JSON and reflects the confirmed values.
3. `conversation-examples/<format_id>_example_<DDMMYYYY>.json` is valid JSON (unless `no_change`).
4. The audit directory exists and contains the expected files.

Present the G4 close-out summary from AGENTS.md Section 3. G4 requires no reply; the session ends there.
