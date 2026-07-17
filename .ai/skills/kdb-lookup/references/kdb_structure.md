# KDB Entry Structure

Each file in `format-database/` is a JSON following `reference/format_database_template.json`.
The top-level keys and their meanings are:

| Key | Type | Description |
| --- | ---- | ----------- |
| `format_id` | string | Unique identifier, e.g. `ahf_mergetree_ascii`. Naming convention: `<halo_finder>_<tree_tool>_<file_format>` in lowercase with underscores. |
| `description` | string | Human-readable description of the input format. |
| `halo_finder` | string | One of: `AHF`, `Rockstar`, `FOF+Subfind (Gadget-2)`, `FOF+Subfind (Gadget-4)`. |
| `tree_tool` | string | One of: `MergerTree`, `Consistent Trees`, `LHaloTree`, `Gadget-4 built-in`. |
| `file_format` | string | One of: `ascii`, `binary-gadget1`, `binary-gadget2`, `hdf5`. |
| `driver_module` | string | Filename of the corresponding driver in `conversion-engine/drivers/`, e.g. `ahf_mergetree_ascii.py`. |
| `memory_multiplier` | number | Format-aware peak-memory multiplier used by `scripts/estimate_output.py` (3.0 for binary/HDF5 inputs, 12-15 for ASCII inputs). Overridden by the `SAGE_MEMORY_MULTIPLIER` environment variable. |
| `references` | array | URLs or paper citations for the format's documentation. |
| `field_map` | object | One entry per SAGE LHaloTree field. Each entry has: `source_field`, `source_units`, `target_units`, `scale_factor`, `conversion_expr`, `notes`. |
| `pointer_logic` | object | Description of how temporal and spatial pointers are encoded in this format, with per-pointer-field explanations. |
| `known_caveats` | array | List of known edge cases, deviations, or ambiguities in this format's LHaloTree mapping. |

## field_map entry structure

```json
"<sage_field_name>": {
  "source_field":    "column/dataset name in the input file, or 'derived'",
  "source_units":    "units of the input field",
  "target_units":    "units required by SAGE",
  "scale_factor":    number or null,
  "conversion_expr": "Python expression or null",
  "notes":           "any relevant remarks"
}
```

For pointer fields (Descendant, FirstProgenitor, NextProgenitor, FirstHaloInFOFGroup,
NextHaloInFOFGroup), `source_field` is typically `"derived"` and `conversion_expr` is
`"see pointer_logic"`. The actual reconstruction logic is described in `pointer_logic`.

## Registered format_id values

These are the entries currently in `format-database/` (always confirm against
the actual directory contents - this list is illustrative, the directory is
authoritative):

- `ahf_mergetree_ascii` - AHF halo finder, MergerTree tool, ASCII output
- `rockstar_consistent_trees_ascii` - Rockstar halo finder, Consistent Trees tool, ASCII output
- `subfind_lhalotree_binary` - FOF+Subfind (Gadget-2), LHaloTree tool, binary output
- `subfind_gadget4_hdf5` - FOF+Subfind (Gadget-4), built-in tool, HDF5 output
