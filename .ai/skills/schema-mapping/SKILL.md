---
name: schema-mapping
description: Provides field-level guidance for mapping input merger tree fields to
             the SAGE LHaloTree schema (HDF5 or binary). Use during web discovery or
             KDB entry creation when individual field mappings, unit conversions, or
             pointer reconstruction decisions need to be made.
---

# Schema Mapping

## Instructions

This skill is invoked within `web-discovery` or `kdb-extend` when individual field
mappings, unit conversions, or pointer reconstructions need to be decided.

## Path Convention

Two path prefixes are used in this skill:
- **`.ai/skills/schema-mapping/references/<file>`** — files in this skill's own `references/` subfolder.
- **`reference/<file>` (project root)** — files in the project-root `reference/` directory (e.g. `reference/sage_lhalotree_hdf5_schema.md`).

### 1. Unit conventions (mandatory)

All output values must be in these units — no exceptions:

| Quantity | On-disk unit | SAGE internal unit after read |
| -------- | ------------ | ----------------------------- |
| Masses | 10¹⁰ M☉/h | 10¹⁰ M☉/h |
| Positions (`SubhaloPos`) | **kpc/h** | Mpc/h (SAGE multiplies × 0.001) |
| Velocities | km/s (physical peculiar) | km/s |
| Specific angular momentum (`SubhaloSpin`) | **(kpc/h)(km/s)** | (Mpc/h)(km/s) (SAGE multiplies × 0.001) |
| Snapshot index | unitless integer, zero-based | — |
| Particle IDs | unitless integer | — |

> **`SubhaloPos` and `SubhaloSpin` must always be written in kpc/h and (kpc/h)(km/s)** regardless of output format. The output writer handles the format-specific difference:
> - **`lhalo_hdf5`:** `hdf5_writer` stores values as-is; SAGE's `read_tree_lhalo_hdf5.c` multiplies by 0.001 post-read (kpc/h → Mpc/h internally).
> - **`lhalo_binary`:** `binary_writer` divides both by 1000 internally before struct-packing; the binary reader uses the stored Mpc/h values as-is.
>
> **Do not apply the ÷ 1000 conversion in the driver.** Every driver must pre-scale source values by × 1000 to reach kpc/h and (kpc/h)(km/s); the writer takes it from there.

For conversion factors see `.ai/skills/schema-mapping/references/unit_conversion_factors.md`.

### 2. Per-field guidance

For each SAGE field, read `.ai/skills/schema-mapping/references/field_mapping_table.md`, which lists:
- Common source field names by halo finder
- Typical input units
- Required output unit and the standard conversion expression

Apply the conversion expression from that table. If the input units differ from the
typical case, compute the appropriate scale factor analytically and record it in
`conversion_expr`.

### 3. Pointer reconstruction

Pointer fields (`Descendant`, `FirstProgenitor`, `NextProgenitor`,
`FirstHaloInFOFGroup`, `NextHaloInFOFGroup`) are never copied directly from the
input. They must be reconstructed as integer indices into the flat per-tree halo array.

The reconstruction method depends on how the input format encodes links:
- **Global halo ID links** — use a dictionary mapping `halo_id → flat_index`.
- **Scale-factor-indexed links** — group halos by snapshot, build a per-snapshot
  index map, then follow the link across the snapshot boundary.
- **Pre-built LHaloTree pointers** — the input already has integer indices; verify
  they are tree-local (not file-global) before copying.

See `.ai/skills/schema-mapping/references/pointer_reconstruction.md` for worked examples of each case.

All reconstruction algorithms must be O(N) or O(N log N). O(N²) is not acceptable.

### 4. Ambiguous field policy

Three fields have definitions that vary across formats. Apply these rules exactly:

**`SubhaloSpin`** — This is the **specific angular momentum vector** [Jx, Jy, Jz]
in units of (Mpc/h)(km/s), i.e. angular momentum per unit mass. It is **not** the
dimensionless spin parameter λ (Bullock et al. 2001 definition). If the input
provides λ, it cannot be directly mapped to `SubhaloSpin`; flag this to the user and
record the caveat in `known_caveats`.

**`SubhaloVMax`** — This is the maximum circular velocity:
max(√(GM(<r>)/r)) over all radii. It is **not** the velocity modulus
|v| = √(Vx² + Vy² + Vz²). If the input provides |v| instead of Vmax, flag to user.

**`SubhaloIDMostBound`** — The particle ID of the most bound particle. If unavailable in
the input format, use sentinel value `-1` (int64). This is always acceptable.

### 5. Missing field policy

For any mandatory SAGE field with no corresponding input field:

1. Look up the sentinel value in `reference/sage_lhalotree_hdf5_schema.md` (project root, Section 3.4).
2. Record the field in `field_map` with:
   - `source_field`: `null`
   - `conversion_expr`: `null`
   - `notes`: `"Not available in input format. Using sentinel value <value>."`
3. Flag the missing field to the user with a brief explanation.
4. Do not silently omit a mandatory field from the `field_map`. An omission means the
   driver will not write the field at all, causing SAGE to abort.
