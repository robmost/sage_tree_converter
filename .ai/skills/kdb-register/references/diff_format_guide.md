# KDB Diff Format Guide

When presenting KDB update diffs to the user, use a consistent structured format
so the user can quickly identify what will change and confirm or reject each item.

---

## Format

```text
KDB Update Diff - <format_id>
=============================

CORRECTED:
  <key.path>:  <old_value> -> <new_value>  (<one-line reason>)
  ...

NEW:
  <key.path>[+]:  <new_value>  (<one-line reason>)
  ...

DRIVER:
  <file>:<line>  <old_code> -> <new_code>  (<one-line reason>)
  ...

UNCHANGED:
  <list of top-level keys that were not touched>
```

The `DRIVER` section covers changes to the driver *code* rather than the KDB
JSON. A code fix has no JSON key path, so it is listed by file and line and
confirmed separately at B2 - it is the one part of the diff that is applied by
copying a file rather than editing JSON.

---

## Key Path Notation

Use dot notation to identify nested fields. For list appends use `[+]`.

| Example path | Meaning |
| --- | --- |
| `field_map.Group_M_Crit200.source_field` | `field_map` -> `Group_M_Crit200` object -> `source_field` |
| `pointer_reconstruction.method` | Top-level `pointer_reconstruction` object -> `method` |
| `caveats[+]` | Append a new item to the `caveats` list |
| `unit_conversions.mass.factor` | `unit_conversions` -> `mass` object -> `factor` |

---

## Example

```text
KDB Update Diff - ahf_mergertree_ascii
=======================================

CORRECTED:
  field_map.Group_M_Crit200.unit_conversion_factor:  1.0 -> 1e-10  (AHF outputs mass in M_sun/h, not 10^10 M_sun/h)
  pointer_reconstruction.method:  "pre_built" -> "global_id_links"  (format uses HaloID references, not pre-built indices)

NEW:
  caveats[+]:  "SubhaloSpin is zero for satellite halos in AHF v1.0.x"  (observed during semantic validation)
  field_map.SubhaloVMax.source_field[+]:  "Vmax"  (discovered during schema mapping; was absent from original entry)

DRIVER:
  drivers/ahf_mergertree_ascii.py:226  glob "*.AHF_croco" -> "*_croco"  (MergerTree's output prefix is run-configurable; the narrow glob matched 0 files and silently produced singleton trees)

UNCHANGED:
  halo_finder, tree_tool, file_format, field_map.SnapNum, field_map.Descendant,
  field_map.FirstProgenitor, field_map.NextProgenitor, field_map.FirstHaloInFOFGroup,
  field_map.NextHaloInFOFGroup, field_map.Np, field_map.Pos, field_map.Vel,
  unit_conversions.position, unit_conversions.velocity
```

---

## Rules

1. Always show CORRECTED, NEW, DRIVER, and UNCHANGED sections - even if empty. Use `(none)` for empty sections.
2. The reason for each CORRECTED or NEW item must be one line. If the reason is a test failure, cite the check number (e.g. "syntactic check 3 failed - pointer out of range").
3. Old values in CORRECTED must be the exact value from the current KDB file, not a paraphrase.
4. New values must be the exact value that will be written.
5. UNCHANGED lists top-level key names only - do not enumerate every sub-field.
6. Present the diff before writing anything. Do not write until the user confirms.
