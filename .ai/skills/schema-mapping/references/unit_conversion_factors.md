# Unit Conversion Factors

Quick-reference table for the conversions most commonly needed when mapping
halo finder outputs to the SAGE LHaloTree HDF5 schema.

## Mass

| From | To | Factor |
| ---- | -- | ------ |
| M☉/h | 10¹⁰ M☉/h | × 1e-10 |
| M☉ | 10¹⁰ M☉/h (with h) | × h / 1e10 |
| 10¹⁰ M☉/h | M☉/h | × 1e10 |

Typical little-h value for cosmological simulations: h ≈ 0.67–0.73.
Always use the simulation's own h value; do not hardcode.

## Position (comoving)

### Source → on-disk conversion (SubhaloPos)

| From | To (on-disk target) | Factor |
| ---- | ------------------- | ------ |
| kpc/h | kpc/h | 1 (direct copy) |
| Mpc/h | **kpc/h** | × 1e3 |
| Mpc (no h) | kpc/h | × h × 1e3 |
| code units (Gadget, 1 c.u. = 1 kpc/h) | kpc/h | 1 (direct copy) |

> **On-disk target is kpc/h, not Mpc/h.** SAGE's `read_tree_lhalo_hdf5.c` multiplies `SubhaloPos` by 0.001 after reading, converting kpc/h → Mpc/h internally. Always write positions in kpc/h.

Note: always verify whether positions are comoving or physical. SAGE requires
comoving coordinates. If the input is physical, divide by (1 + z).

## Velocity

| From | To | Factor |
| ---- | -- | ------ |
| km/s | km/s | 1 (direct copy) |
| m/s | km/s | × 1e-3 |
| code units (Gadget, 1 c.u. ≈ 1 km/s) | km/s | 1 (verify simulation UNITVELOCITY_IN_CM_PER_S) |

Gadget velocity units: if `UNITVELOCITY_IN_CM_PER_S = 1e5`, code units = km/s.

## Specific Angular Momentum

### Source → on-disk conversion (SubhaloSpin)

| From | To (on-disk target) | Factor |
| ---- | ------------------- | ------ |
| (kpc/h)(km/s) | **(kpc/h)(km/s)** | 1 (direct copy) |
| (Mpc/h)(km/s) | **(kpc/h)(km/s)** | × 1e3 |
| Total J in M☉/h × Mpc/h × km/s | **(kpc/h)(km/s)** | ÷ (Mvir in M☉/h) then × 1e3 |

> **On-disk target is (kpc/h)(km/s), not (Mpc/h)(km/s).** SAGE's `read_tree_lhalo_hdf5.c` multiplies `SubhaloSpin` by 0.001 after reading, converting (kpc/h)(km/s) → (Mpc/h)(km/s) internally. Always write spin in (kpc/h)(km/s).

For Rockstar: `J` is total angular momentum in M☉/h × Mpc/h × km/s.
Specific angular momentum = `J / Mvir` (in (Mpc/h)(km/s)); then multiply by 1000 for on-disk storage.

## Particle Count

No conversion needed. `SubhaloLen` is an integer particle count; copy directly as int32.

## Snapshot Index

No physical unit. Must be a zero-based integer in [0, N_snapshots - 1].
If the input uses one-based indices, subtract 1.

## Python conversion expression examples

```python
# Mass: M_sun/h → 1e10 M_sun/h
Group_M_Crit200 = source_Mvir * 1e-10

# Position: Mpc/h → kpc/h (on-disk target for lhalo_hdf5)
SubhaloPos = source_pos_mpc_per_h * 1e3

# Position: kpc/h → kpc/h (already correct; direct copy)
SubhaloPos = source_pos_kpc_per_h  # no scaling needed

# Rockstar spin: total J → specific J, then → on-disk (kpc/h)(km/s)
SubhaloSpin = (source_J / source_Mvir) * 1e3  # J in Msun/h*Mpc/h*km/s, Mvir in Msun/h

# AHF spin: (kpc/h)(km/s) → (kpc/h)(km/s) (already correct; direct copy)
SubhaloSpin = source_L_kpc_per_h_km_per_s  # no scaling needed

# FOF+Subfind spin: (kpc/h)(km/s) → (kpc/h)(km/s) (already correct; direct copy)
SubhaloSpin = source_spin_kpc_per_h_km_per_s  # no scaling needed
```
