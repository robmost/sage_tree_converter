---
name: kdb-lookup
description: Searches the format-database/ KDB for a schema mapping that matches
             the input merger tree format. Use when a new input file has been
             identified and needs to be matched against known formats before any
             conversion begins.
---

# KDB Lookup

## Instructions

## Path Convention

- **`.ai/skills/kdb-lookup/references/<file>`** — files in this skill's own `references/` subfolder.
- **`format-database/`** — the project-root format database directory.

### 1. Inspect the input files

Before searching the KDB, identify the file type. Apply the file inspection rule: read only the minimum needed.

- **ASCII files:** `head -n 30 <file>` — record the comment character, column headers, and first data rows.
- **HDF5 files:** `h5dump -n <file>` — record the group and dataset structure only. Do not read dataset values unless a small sample is needed to identify a field (`h5dump -d <dataset> --start="[0]" --count="[5]"`).
- **Binary files:** `xxd <file> | head -4` — record the first 64 bytes (magic bytes and header fields).

From the inspection, determine:
- The halo finder (e.g. AHF, Rockstar, FOF+Subfind)
- The merger tree tool (e.g. MergerTree, Consistent Trees, LHaloTree, Gadget-4 built-in)
- The file format (ascii, binary-gadget1, binary-gadget2, hdf5)

If any of the three identifiers are uncertain, record them as uncertain and note what additional information is needed.

### 2. Scan format-database/ for a matching entry

Read every `.json` file in `format-database/`. For each entry, compare:
- `halo_finder` against the identified halo finder
- `tree_tool` against the identified tree tool
- `file_format` against the identified file format

A **full match** requires all three to agree (case-insensitive comparison is acceptable). Do not accept a two-out-of-three match silently.

If a **partial match** is found (two of three agree), flag it explicitly to the user:

```text
Partial match found: format-database/<entry>.json
  halo_finder: <value> — MATCH / MISMATCH
  tree_tool:   <value> — MATCH / MISMATCH
  file_format: <value> — MATCH / MISMATCH
I am treating this as NO MATCH. Please confirm or provide the missing identifier.
```

Wait for the user's response. If the user supplies the missing identifier and all three
criteria now agree, proceed with Step 3 (full match path). If the user cannot confirm
or the mismatch remains, proceed with Step 4 (no-match path, invoke web-discovery).

See `.ai/skills/kdb-lookup/references/matching_criteria.md` for the full match definition and edge cases.

### 3. On full match: present the mapping and request confirmation

If a full match is found:

1. Present the matched entry's `format_id`, `description`, `driver_module`, and all `known_caveats`.
2. Present the `field_map` as a readable table: SAGE field → source field → units → conversion expression.
3. Present the `pointer_logic` section.
4. State clearly: "This is the KDB match for your input format."
5. Ask the user to confirm (Gate G1 prompt from `AGENTS.md`).

Do not proceed to Stage 2 until the user confirms.

After the user confirms (G1 passed), copy the matched KDB entry to
`assets/proposed_mapping_<format_id>.json`:

```bash
cp format-database/<format_id>.json assets/proposed_mapping_<format_id>.json
```

This satisfies the Stage 2 entry condition (AGENTS.md §4) and ensures the confirmed
mapping is available for Stage 4 archiving.

### 4. On no match: report and hand off to web-discovery

If no full match is found after scanning all entries in `format-database/`:

```text
No matching KDB entry found for the identified format:
  halo_finder: <value>
  tree_tool:   <value>
  file_format: <value>

Proceeding to web discovery. I will now invoke the web-discovery skill
to search for external documentation on this format.
```

Then invoke the `web-discovery` skill.
