# Syntactic Check Procedures

Detailed pass conditions and expected output for each of the six checks.

All six checks are executed by `run_syntactic_checks.py` (this skill's
`scripts/` folder) - do not run them by hand. Use this file to understand what
a reported FAIL means and, via the per-check commands below, to inspect the
file while diagnosing one.

---

## Check 1 - File Integrity

**Command:**

```bash
h5dump -n <output.hdf5>
```

**Expected output (PASS):**

```text
HDF5 "<output.hdf5>" {
FILE_CONTENTS {
 group      /
 group      /Header
 dataset    /Header/TreeNHalos
 group      /Tree0
 dataset    /Tree0/Descendant
 ...
}
}
```

**Fallback (if h5dump unavailable):**

```bash
$PYTHON_BIN -c "import h5py; f = h5py.File('<output.hdf5>', 'r'); print(list(f.keys())); f.close()"
```

**PASS condition:** Command exits with status 0 and lists at least `Header` and one or more `Tree<X>` groups.

**FAIL condition:** Any error message, non-zero exit code, or no groups listed.

---

## Check 2 - Schema Compliance

**Mandatory fields** (must be present in every `Tree<X>/` group):

| Field | dtype | Shape |
| ----- | ----- | ----- |
| `Descendant` | int32 | (N,) |
| `FirstProgenitor` | int32 | (N,) |
| `NextProgenitor` | int32 | (N,) |
| `FirstHaloInFOFGroup` | int32 | (N,) |
| `NextHaloInFOFGroup` | int32 | (N,) |
| `SubhaloLen` | int32 | (N,) |
| `Group_M_Crit200` | float32 | (N,) |
| `SubhaloVMax` | float32 | (N,) |
| `SubhaloIDMostBound` | int64 | (N,) |
| `SnapNum` | int32 | (N,) |
| `SubhaloPos` | float32 | (N, 3) |
| `SubhaloVel` | float32 | (N, 3) |
| `SubhaloSpin` | float32 | (N, 3) |

**Header checks:**

- `Header.attrs["NtreesPerFile"]` == number of `Tree<X>` groups.
- `len(Header["TreeNHalos"])` == `Header.attrs["NtreesPerFile"]`.
- `sum(Header["TreeNHalos"])` == `Header.attrs["NhalosPerFile"]`.
- `Header["TreeNHalos"]` is a **dataset**, not an attribute.

**PASS condition:** All mandatory fields present in every tree group with correct dtype; all header checks pass.

**FAIL condition:** Any mandatory field missing; any field with wrong dtype; any header inconsistency.

---

## Check 3 - Pointer Integrity: Temporal

For each tree with N halos, for each halo i in [0, N-1]:

| Pointer field | Valid values | Snapshot constraint |
| ------------- | ------------ | ------------------- |
| `Descendant[i]` | -1 or [0, N-1] | If != -1: `SnapNum[Descendant[i]] > SnapNum[i]` |
| `FirstProgenitor[i]` | -1 or [0, N-1] | If != -1: `SnapNum[FirstProgenitor[i]] < SnapNum[i]` |
| `NextProgenitor[i]` | -1 or [0, N-1] | If != -1: `SnapNum[NextProgenitor[i]] < SnapNum[Descendant[i]]` (sibling progenitors share the same snapshot; the constraint is against their common descendant, not against `i`) |

**PASS condition:** All pointer values in valid range; all snapshot ordering constraints satisfied.

**FAIL condition:** Any pointer value outside [-1, N-1]; any progenitor at the same or later snapshot as its descendant; any descendant at the same or earlier snapshot.

---

## Check 4 - Pointer Integrity: Spatial

For each tree with N halos, for each halo i in [0, N-1]:

| Pointer field | Valid values | Snapshot constraint |
| ------------- | ------------ | ------------------- |
| `FirstHaloInFOFGroup[i]` | -1 or [0, N-1] | If != -1: `SnapNum[FirstHaloInFOFGroup[i]] == SnapNum[i]` |
| `NextHaloInFOFGroup[i]` | -1 or [0, N-1] | If != -1: `SnapNum[NextHaloInFOFGroup[i]] == SnapNum[i]` |

Additionally: if `FirstHaloInFOFGroup[i] == i`, this halo is the central (self-pointer).

**PASS condition:** All pointer values in valid range; no spatial pointer crosses a snapshot boundary.

**FAIL condition:** Any pointer value outside [-1, N-1]; any spatial pointer pointing to a halo at a different snapshot.

---

## Check 5 - Snapshot Consistency

For each halo in every tree: `0 <= SnapNum[i] < n_snapshots`.

`n_snapshots` is supplied via `--n-snapshots` argument. If unknown, report `max(SnapNum) + 1` as the inferred upper bound and note it was not independently verified.

**PASS condition:** All `SnapNum` values are non-negative integers within [0, n_snapshots - 1].

**FAIL condition:** Any `SnapNum < 0` or `SnapNum >= n_snapshots`.

---

## Check 6 - Property Consistency

| Field | Valid range | Notes |
| ----- | ----------- | ----- |
| `Group_M_Crit200` | [0, 1e6] in 10^10 Msun/h | Upper bound = 10^16 Msun/h, reasonable for any simulated halo |
| `SubhaloVel` magnitude | [0, 10000] km/s | 10,000 km/s ~ 3% of speed of light |
| `SubhaloVMax` | [0, 10000] km/s | Same physical upper bound |
| `SubhaloPos` | finite (no NaN/Inf) | Values must be real numbers |
| `Group_M_Crit200` | finite (no NaN/Inf) | No unphysical values |

**PASS condition:** All values within bounds; no NaN or Inf in any property field.

**FAIL condition:** Any value outside the specified range, or any NaN/Inf encountered.
