# Conversation Example Schema

Each file in `conversation-examples/` documents a completed conversion session.
File naming convention: `<format_id>_example_<DDMMYYYY>.json`

---

## JSON Structure

```json
{
  "format_id": "string",
  "session_date": "DDMMYYYY",
  "input_description": "string",
  "mapping_source": "kdb_match | web_discovery | user_provided",
  "output_format": "lhalo_hdf5 | lhalo_binary",
  "n_output_files": 1,
  "issues_encountered": ["list of strings"],
  "resolutions": ["list of strings"],
  "kdb_action": "new_driver | updated_entry | no_change",
  "outcome": "success | partial | failed"
}
```

---

## Field Definitions

| Field | Type | Description |
| --- | --- | --- |
| `format_id` | string | Matches the KDB file name: `<halo_finder>_<tree_tool>_<file_format>` in lowercase with underscores. Example: `ahf_mergertree_ascii` |
| `session_date` | string | Date the session completed, in `DDMMYYYY` format. Example: `04052026` |
| `input_description` | string | One or two sentences describing the input files: halo finder, tree tool, file format, simulation code, number of trees/halos if known |
| `mapping_source` | enum | How the schema mapping was obtained: `kdb_match` (found in KDB), `web_discovery` (found via web search), `user_provided` (user supplied the mapping directly) |
| `output_format` | enum | The SAGE output format chosen at G1: `lhalo_hdf5` or `lhalo_binary` |
| `n_output_files` | integer | Number of output files chosen at G1 (≥ 1). Session-level; does not affect KDB entries. |
| `issues_encountered` | list of strings | Each entry is a distinct issue that caused a conversion failure or required a workaround. Use plain language. Order matches `resolutions`. |
| `resolutions` | list of strings | Each entry resolves the corresponding issue in `issues_encountered`. Must be the same length. If no issues, use `[]`. |
| `kdb_action` | enum | What was done to the KDB: `new_driver` (new format added), `updated_entry` (existing entry corrected), `no_change` (no KDB modification) |
| `outcome` | enum | `success` (all stages passed, G4 confirmed), `partial` (some stages passed but not all), `failed` (conversion unsuccessful) |

---

## Example — New Format Discovery

```json
{
  "format_id": "ahf_mergertree_ascii",
  "session_date": "04052026",
  "input_description": "AHF halo finder output with bundled MergerTree tool, ASCII format. Simulation of 512^3 particles in a 100 Mpc/h box. Approximately 50,000 trees.",
  "mapping_source": "web_discovery",
  "output_format": "lhalo_hdf5",
  "n_output_files": 1,
  "issues_encountered": [
    "AHF mass field is in M_sun/h, not 10^10 M_sun/h — required scaling by 1e-10",
    "Progenitor links use global halo IDs across snapshots, not tree-local indices — required O(N) hash map reconstruction"
  ],
  "resolutions": [
    "Applied mass_conversion_factor = 1e-10 in driver Group_M_Crit200 mapping",
    "Built id_to_idx dict over all halos in the tree; reconstructed FirstProgenitor/NextProgenitor from progenitor_id lists"
  ],
  "kdb_action": "new_driver",
  "outcome": "success"
}
```

---

## Notes

- `issues_encountered` and `resolutions` must have the same length. Each resolution must directly address the corresponding issue by index.
- If the same issue occurred multiple times (e.g. a unit error in two different fields), create one entry per occurrence, not a combined entry.
- Do not include issues that were identified and resolved before the first conversion attempt (e.g. obvious typos in the parameter file). Only include issues that caused a test run to fail.
- The conversation example is written once at the end of Stage 4. Do not update it after it is written unless the kdb-register skill (Path B) is invoked in a later session.
