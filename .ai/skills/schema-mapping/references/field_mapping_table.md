# Field Mapping Table

Per-field guidance for all mandatory SAGE LHaloTree fields.
For unit conversion factors, see `unit_conversion_factors.md`.
For pointer reconstruction, see `pointer_reconstruction.md`.

---

## Pointer Fields (reconstructed, not copied)

| SAGE field | Reconstruction | Notes |
| ---------- | -------------- | ----- |
| `Descendant` | See `pointer_reconstruction.md` | Index of the halo this halo merges into at the next snapshot. `-1` if z=0 root. |
| `FirstProgenitor` | See `pointer_reconstruction.md` | Index of the most massive progenitor. `-1` if leaf halo. |
| `NextProgenitor` | See `pointer_reconstruction.md` | Index of the next sibling progenitor of the same descendant. `-1` if none. |
| `FirstHaloInFOFGroup` | See `pointer_reconstruction.md` | Index of the central (most massive) halo in the same FOF group. Self-pointer for centrals. |
| `NextHaloInFOFGroup` | See `pointer_reconstruction.md` | Index of the next satellite in the FOF group chain. `-1` for the last halo. |

---

## Halo Property Fields

### `Len` — particle count

| Halo finder | Typical source field | Input units | Conversion |
| ----------- | -------------------- | ----------- | ---------- |
| AHF | `npart` | particles | Direct copy (scale_factor = 1) |
| Rockstar | `num_p` | particles | Direct copy |
| FOF+Subfind (Gadget-2) | `SubhaloLen` (HDF5) | particles | Direct copy |
| FOF+Subfind (Gadget-4) | `SubhaloLen` or `GroupLen` | particles | Direct copy |

---

### `Group_M_Crit200` — halo mass within R_200_crit

Always verify: is the mass defined using **critical** overdensity (not mean)?

| Halo finder | Typical source field | Input units | Conversion expression |
| ----------- | -------------------- | ----------- | --------------------- |
| AHF | `Mvir` | M☉/h | `source * 1e-10` |
| Rockstar | `Mvir` | M☉/h | `source * 1e-10` |
| FOF+Subfind (Gadget-2) | `Group_M_Crit200` | 10¹⁰ M☉/h | Direct copy |
| FOF+Subfind (Gadget-4) | `Group_M_Crit200` or `Group_M_Mean200` | 10¹⁰ M☉/h | Verify which overdensity. |

AHF `Mvir` uses a virial overdensity criterion; confirm it matches M_crit200 for the
cosmology used. If it does not, record this in `known_caveats`.

---

### `SubhaloVMax` — maximum circular velocity

**Must be** max(√(GM(\<r\>)/r)), not the velocity modulus.

| Halo finder | Typical source field | Input units | Notes |
| ----------- | -------------------- | ----------- | ----- |
| AHF | `Vmax` | km/s | Direct copy |
| Rockstar | `vmax` | km/s | Direct copy |
| FOF+Subfind | `SubhaloVmax` | km/s | Direct copy |

---

### `MostBoundID` — most-bound particle ID

| Halo finder | Typical source field | Notes |
| ----------- | -------------------- | ----- |
| AHF | Not typically output | Use sentinel -1 |
| Rockstar | `most_bound_id` | Direct copy as int64 |
| FOF+Subfind | `SubhaloIDMostbound` | Direct copy as int64 |

---

### `SnapNum` — snapshot index

| Halo finder | Typical source field | Notes |
| ----------- | -------------------- | ----- |
| AHF | Derived from filename or file structure | Verify zero-based |
| Rockstar (Consistent Trees) | `scale` column → mapped to snapshot index | Use the scale factor to snapshot index table from the simulation |
| FOF+Subfind | `SnapNum` attribute or derived from file index | Verify zero-based |

---

## Vector Fields

### `SubhaloPos` — comoving position [X, Y, Z] — **on-disk unit: kpc/h**

> SAGE's `read_tree_lhalo_hdf5.c` multiplies by 0.001 after reading. Write in **kpc/h**; SAGE recovers Mpc/h internally.

| Halo finder | Typical source fields | Input units | On-disk conversion |
| ----------- | --------------------- | ----------- | ------------------ |
| AHF | `Xc`, `Yc`, `Zc` | kpc/h | Direct copy (`source * 1`) |
| Rockstar | `x`, `y`, `z` | Mpc/h | `source * 1e3` |
| FOF+Subfind (binary LHaloTree) | `Pos` (shape N×3) | Mpc/h | `source * 1e3` |
| FOF+Subfind (Gadget HDF5) | `SubhaloPos` (shape N×3) | kpc/h | Direct copy (`source * 1`) |

---

### `SubhaloVel` — peculiar velocity [Vx, Vy, Vz] in km/s

| Halo finder | Typical source fields | Input units | Conversion |
| ----------- | --------------------- | ----------- | ---------- |
| AHF | `VXc`, `VYc`, `VZc` | km/s | Direct copy |
| Rockstar | `vx`, `vy`, `vz` | km/s | Direct copy |
| FOF+Subfind | `SubhaloVel` (shape N×3) | km/s | Direct copy |

---

### `SubhaloSpin` — specific angular momentum [Jx, Jy, Jz] — **on-disk unit: (kpc/h)(km/s)**

**This is specific angular momentum (J/M), not the dimensionless spin parameter λ.**

> SAGE's `read_tree_lhalo_hdf5.c` multiplies by 0.001 after reading. Write in **(kpc/h)(km/s)**; SAGE recovers (Mpc/h)(km/s) internally.

| Halo finder | Typical source fields | Input units | On-disk conversion |
| ----------- | --------------------- | ----------- | ------------------ |
| AHF | `Lx`, `Ly`, `Lz` | (kpc/h)(km/s) | Direct copy (`source * 1`) |
| Rockstar | `Jx`, `Jy`, `Jz` | M☉/h × Mpc/h × km/s | `source / Mvir * 1e3` (divide by mass → (Mpc/h)(km/s), then × 1000) |
| FOF+Subfind (binary LHaloTree) | `Spin` (shape N×3) | (Mpc/h)(km/s) | `source * 1e3` |
| FOF+Subfind (Gadget HDF5) | `SubhaloSpin` (shape N×3) | (kpc/h)(km/s) | Direct copy (`source * 1`) |

Note: Rockstar outputs total angular momentum, not specific. Divide by `Mvir` in
M☉/h to get specific angular momentum in (Mpc/h)(km/s), then multiply by 1000 for
the required on-disk (kpc/h)(km/s) storage. Verify units carefully.

---

## Optional Fields

| SAGE field | Sentinel | Notes |
| ---------- | -------- | ----- |
| `Group_M_Mean200` | `0.0` | Use sentinel if unavailable |
| `Group_M_TopHat200` | `0.0` | Use sentinel if unavailable |
| `SubhaloVelDisp` | `0.0` | Use sentinel if unavailable |
| `FileNr` | `-1` | Use sentinel if unavailable |
