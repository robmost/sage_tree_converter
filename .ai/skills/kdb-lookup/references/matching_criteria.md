# KDB Matching Criteria

## Full Match Definition

A KDB entry is a **full match** if and only if all three of the following agree with
the identified input format:

1. `halo_finder` — must match the detected halo finder exactly (case-insensitive).
2. `tree_tool` — must match the detected merger tree tool exactly (case-insensitive).
3. `file_format` — must match the detected file format exactly (case-insensitive).

A partial match (two of three) is **never** accepted silently. It must be flagged to
the user with a per-field breakdown.

## Halo Finder Identification Cues

| Halo Finder | Typical file signatures |
| ----------- | ----------------------- |
| AHF | Files named `*.AHF_halos`, `*.AHF_particles`, `*.AHF_substructure`; comment lines starting with `#`; columns often include `Mvir`, `Rvir`, `Xc`, `Yc`, `Zc`, `VXc`, `VYc`, `VZc` |
| Rockstar | Files named `halos_<N>.ascii` or `halos_<N>.bin`; `#Full-sky` header; column line starting with `#id` |
| FOF+Subfind (Gadget-2) | HDF5 with groups `/Header`, `/Group`, `/Subhalo`; attribute `NumPart_Total` in Header |
| FOF+Subfind (Gadget-4) | HDF5 with `/Header` attribute `NumFilesPerSnapshot`; or binary with Gadget-1/Gadget-2 block markers |

## Tree Tool Identification Cues

| Tree Tool | Typical signatures |
| --------- | ------------------ |
| MergerTree (AHF) | `*_mtree` (for the full progenitor list), `*_mtree_idx` (for just the main progenitor information), `*_croco` (for detailed progenitor information, including merit functions) ASCII file; the files match halo IDs, with potential snapshot skipping; structured as per-halo rows with progenitor IDs |
| Consistent Trees | `tree_<N>.dat` or `hlist_<scale>.list` ASCII files; `#scale(0)` style header; first data column is `scale` |
| LHaloTree | HDF5 or binary with groups named `Tree<N>`; datasets `Descendant`, `FirstProgenitor`, `NextProgenitor`, `FirstHaloInFOFGroup`, `NextHaloInFOFGroup` |
| Gadget-4 built-in | Binary `.tree` files or HDF5 with Gadget-4 group naming; documented in Gadget-4 source `mergertree.cc` |

## File Format Identification Cues

| Format | Detection method |
| ------ | ---------------- |
| `ascii` | First bytes are printable text; `file <path>` reports "ASCII text" |
| `hdf5` | Magic bytes `\x89HDF\r\n\x1a\n` at offset 0; `h5dump -n` succeeds |
| `binary-gadget1` | 4-byte little-endian block size at offset 0; no magic bytes; block structure alternates `[size][data][size]` |
| `binary-gadget2` | 8-byte block header with 4-byte tag and 4-byte size; tag is an ASCII string like `HEAD` |

## Handling Uncertain Identifiers

If an identifier cannot be determined from file inspection alone:

1. Report which identifier is uncertain and why.
2. List the cues that were checked and what was found.
3. Ask the user to confirm or supply the missing information before continuing the KDB scan.
4. Do not assume a value and proceed silently.

## Multiple Full Matches

If more than one KDB entry satisfies all three criteria (should be rare, since the
naming convention makes entries unique), present all matches to the user and ask
them to select the correct one before proceeding.
