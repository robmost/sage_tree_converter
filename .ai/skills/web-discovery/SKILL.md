---
name: web-discovery
description: Searches the web for documentation on an unknown merger tree format.
             Use when kdb-lookup finds no matching format in the KDB and the input
             format must be identified from external sources.
---

# Web Discovery

## Instructions

This skill is invoked when `kdb-lookup` finds no full match in `format-database/`.
The goal is to locate sufficient external documentation to produce a complete schema
mapping that can be confirmed by the user at Gate G1.

## Path Convention

Two path prefixes are used in this skill:
- **`.ai/skills/web-discovery/references/<file>`** — files in this skill's own `references/` subfolder.
- **`reference/<file>` (project root)** — files in the project-root `reference/` directory (e.g. `reference/sage_lhalotree_hdf5_schema.md`).

### 1. Search strategy

Construct search queries combining:
- The halo finder name (e.g. "AHF", "Rockstar", "Gadget-4 FoF Subfind")
- The merger tree tool name (e.g. "MergerTree", "Consistent Trees", "LHaloTree")
- The file format (e.g. "ASCII output format", "HDF5 schema", "binary format")

Query forms to try (in priority order):
1. `"<halo_finder>" "<tree_tool>" output format columns`
2. `"<halo_finder>" merger tree file format documentation`
3. `site:github.com "<halo_finder>" "<tree_tool>"`

Source priority (highest to lowest) — see `.ai/skills/web-discovery/references/source_credibility.md`:
1. Official code repository documentation (README, wiki, doc/ directory)
2. Published papers describing the format (ADS, arXiv)
3. Reference implementations that read or write the format
4. Personal web pages or institutional pages of the authors
5. Forum posts, Stack Overflow, or secondary discussions

Stop searching once you have found a complete field list and a pointer semantics description from a Tier 1 or Tier 2 source.

### 2. Cross-reference against the SAGE schema

Once field information is found, read `reference/sage_lhalotree_hdf5_schema.md` (project root) and
for each mandatory SAGE field, identify the closest matching source field. Note:
- Unit differences that require scaling
- Fields that are absent in the input format (will use sentinel values)
- Fields whose definitions differ subtly (e.g. `Spin` as spin parameter vs. specific
  angular momentum vector — use the `schema-mapping` skill to resolve these)

### 3. Draft a candidate mapping

Invoke the `schema-mapping` skill for all field-level and pointer-level decisions.
Write the resulting mapping to `assets/proposed_mapping_<format_id>.json`, following
`reference/format_database_template.json` (project root) exactly. The `format_id` is
`<halo_finder_lower>_<tree_tool_lower>_<file_format_lower>` with underscores.

The draft must include:
- All top-level keys from the template
- An entry in `field_map` for every mandatory SAGE field
- A complete `pointer_logic` section describing how pointers are reconstructed
- At least one URL in `references`

### 4. Iterate with the user

Present the draft mapping to the user with a summary of:
- Which source(s) were used and their tier
- Which fields were found directly vs. inferred
- Which fields will use sentinel values and why
- Any ambiguities that require user confirmation

Incorporate user corrections, update `assets/proposed_mapping_<format_id>.json`, and
present again. Repeat until the user issues an explicit confirmation (Gate G1).
